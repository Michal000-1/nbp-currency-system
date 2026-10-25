import asyncio
from contextlib import asynccontextmanager
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import httpx
import pytest
from fastapi import HTTPException

from app.services import nbp_api


@pytest.fixture
def history_api(monkeypatch):
    state = SimpleNamespace(
        today=date(2026, 9, 24), clock=10_000.0, requests=[], sleep=AsyncMock()
    )

    class FixedDate(date):
        @classmethod
        def today(cls):
            return state.today

    monkeypatch.setattr("app.services.nbp_api.date", FixedDate)
    monkeypatch.setattr("app.services.validation.date", FixedDate)
    monkeypatch.setattr("app.services.nbp_api.monotonic", lambda: state.clock)
    monkeypatch.setattr(nbp_api, "_cache", {})
    monkeypatch.setattr(nbp_api, "_current_rate_cache", {})
    monkeypatch.setattr("app.services.nbp_api.asyncio.sleep", state.sleep)

    @asynccontextmanager
    async def connect(handler):
        def capture(request):
            state.requests.append(request)
            return handler(request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(capture), timeout=5
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            yield

    return state, connect


def requested_range(request):
    start, end = request.url.path.rstrip("/").split("/")[-2:]
    return date.fromisoformat(start), date.fromisoformat(end)


def history_response(points):
    return httpx.Response(
        200,
        json={
            "currency": "dolar amerykański",
            "code": "USD",
            "rates": [
                {"no": "test", "effectiveDate": day.isoformat(), "mid": rate}
                for day, rate in points
            ],
        },
    )


@pytest.mark.parametrize(
    ("end", "expected_ranges", "expected_days"),
    [
        ("2024-01-01", [("2024-01-01", "2024-01-01")], 1),
        ("2024-04-02", [("2024-01-01", "2024-04-02")], 93),
        (
            "2024-04-03",
            [("2024-01-01", "2024-04-02"), ("2024-04-03", "2024-04-03")],
            94,
        ),
        (
            "2024-07-04",
            [("2024-01-01", "2024-04-02"), ("2024-04-03", "2024-07-04")],
            186,
        ),
        (
            "2024-07-05",
            [
                ("2024-01-01", "2024-04-02"),
                ("2024-04-03", "2024-07-04"),
                ("2024-07-05", "2024-07-05"),
            ],
            187,
        ),
        (
            "2025-01-02",
            [
                ("2024-01-01", "2024-04-02"),
                ("2024-04-03", "2024-07-04"),
                ("2024-07-05", "2024-10-05"),
                ("2024-10-06", "2025-01-02"),
            ],
            368,
        ),
    ],
    ids=["one-day", "93-days", "94-days", "186-days", "187-days", "maximum-span"],
)
def test_history_splits_inclusive_ranges_without_gaps_or_overlaps(
    history_api, end, expected_ranges, expected_days
):
    state, connect = history_api
    start, end_date = date(2024, 1, 1), date.fromisoformat(end)

    def handle_request(request):
        first, last = requested_range(request)
        # Synthetic daily observations make missing/duplicated boundaries visible.
        return history_response(
            (first + timedelta(days=offset), 4.0)
            for offset in range((last - first).days + 1)
        )

    async def scenario():
        async with connect(handle_request):
            result = await nbp_api.get_currency_rates_range("usd", start, end_date)
            assert result.code == "USD"
            assert [str(request.url) for request in state.requests] == [
                f"{nbp_api.NBP_API_URL}USD/{first}/{last}"
                for first, last in expected_ranges
            ]
            assert [point.effectiveDate for point in result.rates] == [
                start + timedelta(days=offset)
                for offset in range(expected_days)
            ]

            # Cache belongs to the complete user range, including after a long wait.
            state.clock += 24 * 60 * 60
            assert await nbp_api.get_currency_rates_range("USD", start, end_date) == result
            assert len(state.requests) == len(expected_ranges)

    asyncio.run(scenario())


def test_history_merges_sorts_and_deduplicates_publications(history_api):
    state, connect = history_api

    def handle_request(request):
        first, _ = requested_range(request)
        if first == date(2024, 1, 1):
            return history_response([
                (date(2024, 1, 3), 4.2),
                (date(2024, 1, 1), 4.0),
                (date(2024, 1, 3), 4.2),
            ])
        return history_response([(date(2024, 4, 3), 4.5)])

    async def scenario():
        async with connect(handle_request):
            result = await nbp_api.get_currency_rates_range(
                "USD", date(2024, 1, 1), date(2024, 4, 3)
            )
            assert result.currency == "dolar amerykański"
            assert [(point.effectiveDate, point.mid) for point in result.rates] == [
                (date(2024, 1, 1), 4.0), (date(2024, 1, 3), 4.2), (date(2024, 4, 3), 4.5)
            ]
            assert len(state.requests) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("missing_chunk", [0, 1], ids=["first-empty", "last-empty"])
def test_empty_chunk_does_not_discard_other_publications(history_api, missing_chunk):
    state, connect = history_api

    def handle_request(request):
        first, _ = requested_range(request)
        if len(state.requests) - 1 == missing_chunk:
            return httpx.Response(404)
        return history_response([(first, 4.1)])

    async def scenario():
        async with connect(handle_request):
            result = await nbp_api.get_currency_rates_range(
                "USD", date(2024, 1, 1), date(2024, 4, 3)
            )
            expected_date = date(2024, 4, 3) if missing_chunk == 0 else date(2024, 1, 1)
            assert [point.effectiveDate for point in result.rates] == [expected_date]
            assert len(state.requests) == 2  # No separate current-rate lookup.

    asyncio.run(scenario())


@pytest.mark.parametrize("unknown_currency", [False, True], ids=["no-data", "unknown"])
def test_all_empty_chunks_check_currency_once(history_api, unknown_currency):
    state, connect = history_api

    def handle_request(request):
        if str(request.url) == f"{nbp_api.NBP_API_URL}USD":
            if unknown_currency:
                return httpx.Response(404)
            return history_response([(state.today, 4.1)])
        return httpx.Response(404)

    async def scenario():
        async with connect(handle_request):
            with pytest.raises(HTTPException) as error:
                await nbp_api.get_currency_rates_range(
                    "USD", date(2024, 1, 1), date(2024, 4, 3)
                )
            assert error.value.status_code == 404
            assert error.value.detail == (
                "Currency not found" if unknown_currency else "No data found for given range"
            )
            assert [str(request.url) for request in state.requests] == [
                f"{nbp_api.NBP_API_URL}USD/2024-01-01/2024-04-02",
                f"{nbp_api.NBP_API_URL}USD/2024-04-03/2024-04-03",
                f"{nbp_api.NBP_API_URL}USD",
            ]
            assert not nbp_api._cache

    asyncio.run(scenario())


def test_failed_later_chunk_retries_without_caching_partial_history(history_api):
    state, connect = history_api
    unavailable = True

    def handle_request(request):
        first, _ = requested_range(request)
        if first == date(2024, 4, 3) and unavailable:
            return httpx.Response(503)
        return history_response([(first, 4.0)])

    async def scenario():
        nonlocal unavailable
        async with connect(handle_request):
            start, end = date(2024, 1, 1), date(2024, 4, 3)
            with pytest.raises(HTTPException) as error:
                await nbp_api.get_currency_rates_range("USD", start, end)
            assert error.value.status_code == 503
            assert not nbp_api._cache
            assert [requested_range(request)[0] for request in state.requests] == [
                start, end, end, end,
            ]
            assert state.sleep.await_args_list == [call(2), call(2)]

            unavailable = False
            recovered = await nbp_api.get_currency_rates_range("USD", start, end)
            assert [point.effectiveDate for point in recovered.rates] == [
                start, end,
            ]
            assert [requested_range(request)[0] for request in state.requests[4:]] == [
                start, end,
            ]
            assert await nbp_api.get_currency_rates_range("USD", start, end) == recovered
            assert len(state.requests) == 6

    asyncio.run(scenario())


def test_transient_timeout_retries_only_the_failed_chunk(history_api):
    state, connect = history_api

    def handle_request(request):
        first, _ = requested_range(request)
        if first == date(2024, 4, 3) and len(state.requests) < 4:
            raise httpx.ReadTimeout("NBP timed out", request=request)
        return history_response([(first, 4.0)])

    async def scenario():
        async with connect(handle_request):
            start, end = date(2024, 1, 1), date(2024, 4, 3)
            result = await nbp_api.get_currency_rates_range("USD", start, end)
            assert len(result.rates) == 2
            assert [requested_range(request)[0] for request in state.requests] == [
                start, end, end, end,
            ]
            assert state.sleep.await_args_list == [call(2), call(2)]

    asyncio.run(scenario())


def test_complete_history_cache_expires_even_if_midnight_passes_between_chunks(history_api):
    state, connect = history_api
    end = state.today
    start = end - timedelta(days=93)
    published_rate = 4.0

    def handle_request(request):
        _, last = requested_range(request)
        state.clock += 5  # TTL must start after receipt of the final chunk.
        if len(state.requests) == 1:
            state.today += timedelta(days=1)
        return history_response([(last, published_rate)])

    async def scenario():
        nonlocal published_rate
        async with connect(handle_request):
            initial = await nbp_api.get_currency_rates_range("USD", start, end)
            assert len(initial.rates) == 2
            assert len(state.requests) == 2

            published_rate = 4.1
            state.clock += nbp_api.HISTORY_CACHE_TTL_SECONDS - 1
            assert await nbp_api.get_currency_rates_range("USD", start, end) == initial
            assert len(state.requests) == 2

            state.clock += 1
            refreshed = await nbp_api.get_currency_rates_range("USD", start, end)
            assert [point.mid for point in refreshed.rates] == [4.1, 4.1]
            assert len(state.requests) == 4

            # On refresh the complete range was already historical.
            state.clock += 24 * 60 * 60
            assert await nbp_api.get_currency_rates_range("USD", start, end) == refreshed
            assert len(state.requests) == 4

    asyncio.run(scenario())
