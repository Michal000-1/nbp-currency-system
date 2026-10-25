import asyncio
from datetime import date, timedelta
import httpx
import pytest
from fastapi import HTTPException
from app.services import nbp_api


@pytest.fixture
def cache_clock(monkeypatch):
    clock = [10_000.0]
    monkeypatch.setattr(nbp_api, "_cache", {})
    monkeypatch.setattr(nbp_api, "_current_rate_cache", {})
    monkeypatch.setattr(nbp_api, "monotonic", lambda: clock[0])
    return clock


def rate_payload(rate, effective_date):
    return {
        "currency": "dolar amerykański",
        "code": "USD",
        "rates": [{"mid": rate, "effectiveDate": effective_date}],
    }


def test_current_rate_refreshes_at_ttl_boundary(monkeypatch, cache_clock):
    published_rate = rate_payload(3.90, "2026-09-04")
    requests = []

    def handle_request(request):
        requests.append(request)
        return httpx.Response(200, json=published_rate)

    async def scenario():
        nonlocal published_rate
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request)
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)

            morning = await nbp_api.get_currency_rate("usd")
            assert morning.code == "USD"
            assert morning.rate == 3.90
            assert morning.date == date(2026, 9, 4)
            assert len(requests) == 1

            # NBP publishes a new rate during the same application day.
            published_rate = rate_payload(3.95, "2026-09-07")
            cache_clock[0] += nbp_api.CURRENT_RATE_CACHE_TTL_SECONDS - 1
            cached = await nbp_api.get_currency_rate("USD")
            assert cached == morning
            assert len(requests) == 1

            cache_clock[0] += 1
            refreshed = await nbp_api.get_currency_rate("USD")
            assert refreshed.rate == 3.95
            assert refreshed.date == date(2026, 9, 7)
            assert len(requests) == 2

            assert await nbp_api.get_currency_rate("usd") == refreshed
            assert len(requests) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("limit", [1, 2, 500])
def test_history_cache_evicts_first_inserted_entry_even_after_a_hit(monkeypatch, cache_clock, limit):
    monkeypatch.setattr(nbp_api, "HISTORY_CACHE_MAX_ENTRIES", limit)
    requests = []

    def handle_request(request):
        requests.append(request)
        day = request.url.path.rstrip("/").split("/")[-1]
        return httpx.Response(200, json={"currency": "dolar amerykański", "rates": [
            {"no": "test", "effectiveDate": day, "mid": 4.0},
        ]})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle_request)) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            first_day = date(2020, 1, 1)
            for index in range(limit):
                day = first_day + timedelta(days=index)
                await nbp_api.get_currency_rates_range("USD", day, day)
            first_key = next(iter(nbp_api._cache))
            await nbp_api.get_currency_rates_range("usd", first_day, first_day)
            assert len(requests) == limit
            assert next(iter(nbp_api._cache)) == first_key

            new_day = first_day + timedelta(days=limit)
            await nbp_api.get_currency_rates_range("USD", new_day, new_day)
            assert len(nbp_api._cache) == limit
            assert first_key not in nbp_api._cache
            assert list(nbp_api._cache)[-1] == f"USD_{new_day}_{new_day}"

            await nbp_api.get_currency_rates_range("USD", first_day, first_day)
            assert len(requests) == limit + 2
            assert len(nbp_api._cache) == limit

    asyncio.run(scenario())


@pytest.mark.parametrize("invalid_rate", [0, -1, "NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("history", [False, True], ids=["current", "history"])
def test_invalid_numeric_rate_returns_controlled_error_without_caching(
    monkeypatch, cache_clock, invalid_rate, history
):
    def handle_request(request):
        return httpx.Response(200, json={"currency": "dolar amerykański", "rates": [
            {"no": "test", "effectiveDate": "2024-01-02", "mid": invalid_rate},
        ]})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle_request)) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            with pytest.raises(HTTPException) as error:
                if history:
                    await nbp_api.get_currency_rates_range("USD", date(2024, 1, 2), date(2024, 1, 2))
                else:
                    await nbp_api.get_currency_rate("USD")
            assert error.value.status_code == 500
            assert error.value.detail == "Invalid response from NBP API"
            assert not nbp_api._cache
            assert not nbp_api._current_rate_cache

    asyncio.run(scenario())


@pytest.fixture
def history_day(monkeypatch):
    today = [date(2026, 9, 21)]

    class FixedDate(date):
        @classmethod
        def today(cls):
            return today[0]

    monkeypatch.setattr(nbp_api, "date", FixedDate)
    monkeypatch.setattr("app.services.validation.date", FixedDate)
    return today


def history_payload(include_today=False):
    rates = [{"no": "test", "effectiveDate": "2026-09-18", "mid": 3.90}]
    if include_today:
        rates.append({"no": "test", "effectiveDate": "2026-09-21", "mid": 3.95})
    return {"currency": "dolar amerykański", "code": "USD", "rates": rates}


def test_today_history_refreshes_after_five_minutes(
    monkeypatch, cache_clock, history_day
):
    requests = []

    def handle_request(request):
        requests.append(request)
        # Expiration is measured from receipt, including time spent fetching.
        cache_clock[0] += 2
        return httpx.Response(200, json=history_payload(include_today=len(requests) > 1))

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request)
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            start, end = date(2026, 9, 18), history_day[0]

            morning = await nbp_api.get_currency_rates_range("usd", start, end)
            assert morning.code == "USD"
            assert [rate.effectiveDate for rate in morning.rates] == [date(2026, 9, 18)]

            cache_clock[0] += 299
            assert await nbp_api.get_currency_rates_range("USD", start, end) == morning
            assert len(requests) == 1

            cache_clock[0] += 1
            refreshed = await nbp_api.get_currency_rates_range("USD", start, end)
            assert [rate.effectiveDate for rate in refreshed.rates] == [
                date(2026, 9, 18), date(2026, 9, 21),
            ]
            assert refreshed.rates[-1].mid == 3.95
            assert len(requests) == 2

            cache_clock[0] += 299
            assert await nbp_api.get_currency_rates_range("usd", start, end) == refreshed
            assert len(requests) == 2
            cache_clock[0] += 1
            await nbp_api.get_currency_rates_range("USD", start, end)
            assert len(requests) == 3

    asyncio.run(scenario())


def test_past_history_remains_cached(monkeypatch, cache_clock, history_day):
    requests = []

    def handle_request(request):
        requests.append(request)
        return httpx.Response(200, json=history_payload())

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request)
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            start = end = date(2026, 9, 18)
            history = await nbp_api.get_currency_rates_range("USD", start, end)

            cache_clock[0] += 24 * 60 * 60
            history_day[0] = date(2026, 9, 22)
            assert await nbp_api.get_currency_rates_range("usd", start, end) == history
            assert len(requests) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "midnight_during_fetch", [False, True], ids=["after-fetch", "during-fetch"]
)
def test_today_history_still_expires_after_midnight(
    monkeypatch, cache_clock, history_day, midnight_during_fetch
):
    requests = []

    def handle_request(request):
        requests.append(request)
        if midnight_during_fetch and len(requests) == 1:
            history_day[0] = date(2026, 9, 22)
        return httpx.Response(200, json=history_payload(include_today=len(requests) > 1))

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request)
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            start, end = date(2026, 9, 18), date(2026, 9, 21)
            incomplete = await nbp_api.get_currency_rates_range("USD", start, end)

            history_day[0] = date(2026, 9, 22)
            cache_clock[0] += 299
            assert await nbp_api.get_currency_rates_range("USD", start, end) == incomplete
            assert len(requests) == 1

            cache_clock[0] += 1
            refreshed = await nbp_api.get_currency_rates_range("USD", start, end)
            assert [rate.effectiveDate for rate in refreshed.rates] == [
                date(2026, 9, 18), date(2026, 9, 21),
            ]
            assert len(requests) == 2

            # The range fetched again on the next day is now fully historical.
            cache_clock[0] += 24 * 60 * 60
            history_day[0] = date(2026, 9, 23)
            assert await nbp_api.get_currency_rates_range("USD", start, end) == refreshed
            assert len(requests) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("response_status", "response_body", "expected_status"),
    [
        (502, {"error": "upstream unavailable"}, 502),
        (200, {"currency": "dolar amerykański"}, 500),
        (200, {
            "currency": "dolar amerykański",
            "rates": [{"no": "test", "effectiveDate": "data-data", "mid": 3.95}],
        }, 500),
        (200, {
            "currency": "dolar amerykański",
            "rates": [{"no": "test", "effectiveDate": "2026-02-30", "mid": 3.95}],
        }, 500),
    ],
    ids=["http-error", "missing-rates", "invalid-date-text", "impossible-date"],
)
def test_failed_history_refresh_does_not_extend_cache(
    monkeypatch, cache_clock, history_day, response_status, response_body, expected_status
):
    requests = []
    responses = [
        httpx.Response(200, json=history_payload()),
        httpx.Response(response_status, json=response_body),
        httpx.Response(200, json=history_payload(include_today=True)),
    ]

    def handle_request(request):
        requests.append(request)
        return responses[len(requests) - 1]

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request)
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            start, end = date(2026, 9, 18), history_day[0]
            await nbp_api.get_currency_rates_range("USD", start, end)
            cache_clock[0] += 300

            with pytest.raises(HTTPException) as error:
                await nbp_api.get_currency_rates_range("USD", start, end)
            assert error.value.status_code == expected_status
            assert len(requests) == 2

            recovered = await nbp_api.get_currency_rates_range("USD", start, end)
            assert [rate.effectiveDate for rate in recovered.rates] == [
                date(2026, 9, 18), date(2026, 9, 21),
            ]
            assert len(requests) == 3
            assert await nbp_api.get_currency_rates_range("USD", start, end) == recovered
            assert len(requests) == 3

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("response_status", "response_body", "expected_status"),
    [
        (502, {"error": "upstream unavailable"}, 502),
        (200, {"currency": "dolar amerykański", "rates": []}, 500),
        (200, rate_payload(3.95, "data-data"), 500),
        (200, rate_payload(3.95, "2026-02-30"), 500),
        (200, rate_payload("wrong-rate", "2026-09-07"), 500),
    ],
    ids=["http-error", "invalid-payload", "invalid-date-text", "impossible-date", "invalid-rate"],
)
def test_failed_refresh_does_not_extend_cache(
    monkeypatch, cache_clock, response_status, response_body, expected_status
):
    requests = []
    responses = [
        httpx.Response(200, json=rate_payload(3.90, "2026-09-04")),
        httpx.Response(response_status, json=response_body),
        httpx.Response(200, json=rate_payload(3.95, "2026-09-07")),
    ]

    def handle_request(request):
        requests.append(request)
        return responses[len(requests) - 1]

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle_request)
        ) as client:
            monkeypatch.setattr(nbp_api, "_client", client)
            await nbp_api.get_currency_rate("USD")
            cached_before_failure = nbp_api._current_rate_cache["USD"]
            cache_clock[0] += nbp_api.CURRENT_RATE_CACHE_TTL_SECONDS

            with pytest.raises(HTTPException) as error:
                await nbp_api.get_currency_rate("USD")
            assert error.value.status_code == expected_status
            assert error.value.detail == (
                "Invalid response from NBP API" if expected_status == 500 else "NBP API error"
            )
            assert nbp_api._current_rate_cache["USD"] == cached_before_failure
            assert len(requests) == 2

            cache_clock[0] += 1
            recovered = await nbp_api.get_currency_rate("USD")
            assert recovered.rate == 3.95
            assert recovered.date == date(2026, 9, 7)
            assert len(requests) == 3

            assert await nbp_api.get_currency_rate("USD") == recovered
            assert len(requests) == 3

    asyncio.run(scenario())
