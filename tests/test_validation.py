from datetime import date
from unittest.mock import AsyncMock, call
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import nbp_api
from app.services.events import EVENTS


@pytest.fixture
def api(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 18)

    monkeypatch.setattr("app.services.validation.date", FixedDate)
    monkeypatch.setattr("app.services.nbp_api.date", FixedDate)
    monkeypatch.setattr(nbp_api, "_cache", {})
    monkeypatch.setattr(nbp_api, "_current_rate_cache", {})

    async def reply(url: str):
        parts = urlsplit(url).path.strip("/").split("/")
        dates = list(dict.fromkeys(parts[-2:])) if len(parts) == 7 else ["2026-09-18"]
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "currency": "test currency",
                "code": parts[4],
                "rates": [
                    {"no": "test", "effectiveDate": day, "mid": 4.0 + index / 10}
                    for index, day in enumerate(dates)
                ],
            },
        )

    with TestClient(app) as client:
        fetch = AsyncMock(side_effect=reply)
        monkeypatch.setattr(nbp_api.get_http_client(), "get", fetch)
        yield client, fetch


@pytest.mark.parametrize(
    ("start", "end", "detail"),
    [
        ("2024-03-01", "2024-02-28", "Start date cannot be later than end date"),
        ("2002-01-01", "2002-01-03", "Rates are available from 2002-01-02"),
        ("2026-09-01", "2026-09-19", "End date cannot be in the future"),
        ("2024-01-01", "2025-01-03", "Date range cannot exceed 367 days"),
    ],
)
def test_invalid_history_range_is_rejected_before_fetching(api, start, end, detail):
    client, fetch = api
    response = client.get(
        "/currencies/USD/history", params={"start_date": start, "end_date": end}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    fetch.assert_not_awaited()


def test_invalid_history_range_cannot_bypass_validation_using_cache(api, monkeypatch):
    client, fetch = api
    monkeypatch.setattr(nbp_api, "_cache", {"USD_2000-01-01_2000-01-02": object()})
    response = client.get(
        "/currencies/USD/history",
        params={"start_date": "2000-01-01", "end_date": "2000-01-02"},
    )
    assert response.status_code == 400
    fetch.assert_not_awaited()


@pytest.mark.parametrize(
    ("start", "end", "expected_ranges"),
    [
        ("2002-01-02", "2002-01-02", [("2002-01-02", "2002-01-02")]),
        # Exactly 367 days between the dates, fetched in four NBP requests.
        ("2024-01-01", "2025-01-02", [
            ("2024-01-01", "2024-04-02"),
            ("2024-04-03", "2024-07-04"),
            ("2024-07-05", "2024-10-05"),
            ("2024-10-06", "2025-01-02"),
        ]),
        ("2026-09-18", "2026-09-18", [("2026-09-18", "2026-09-18")]),
    ],
    ids=["earliest-date", "maximum-span", "today"],
)
def test_history_accepts_valid_boundaries(api, start, end, expected_ranges):
    client, fetch = api
    response = client.get(
        "/currencies/usd/history", params={"start_date": start, "end_date": end}
    )
    assert response.status_code == 200
    assert response.json()["code"] == "USD"
    expected_dates = sorted({day for bounds in expected_ranges for day in bounds})
    assert [rate["effectiveDate"] for rate in response.json()["rates"]] == expected_dates
    assert fetch.await_args_list == [
        call(f"{nbp_api.NBP_API_URL}USD/{chunk_start}/{chunk_end}")
        for chunk_start, chunk_end in expected_ranges
    ]


@pytest.mark.parametrize("code", ["US", "USDD", "U1D", "ąBC"])
@pytest.mark.parametrize("suffix", ["", "/history"])
def test_currency_routes_reject_invalid_code_without_fetching(api, code, suffix):
    client, fetch = api
    response = client.get(
        f"/currencies/{code}{suffix}",
        params={"start_date": "2024-01-02", "end_date": "2024-01-03"},
    )
    assert response.status_code == 422
    fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "event_date",
    ["0001-01-01", "2002-01-02", "2026-09-18", "9999-12-31"],
    ids=["date-underflow", "window-before-data", "window-in-future", "date-overflow"],
)
def test_event_rejects_unavailable_full_window_before_fetching(api, event_date):
    client, fetch = api
    response = client.get(
        "/analysis/event-impact",
        params={"code": "USD", "event_date": event_date, "days_before": 1, "days_after": 1},
    )
    assert response.status_code == 400
    fetch.assert_not_awaited()


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        ("/analysis/event-impact", {"event_date": "2024-01-04", "days_before": 10**9}),
        ("/analysis/event-impact", {"event_date": "2024-01-04", "days_after": 368}),
        ("/analysis/events-impact", {"window_business_days": 0}),
        ("/analysis/events-impact", {"window_business_days": 368}),
        ("/analysis/events-impact-compare", {"short_window": 0}),
        ("/analysis/events-impact-compare", {"short_window": 368}),
        ("/analysis/events-impact-compare", {"long_window": 368}),
    ],
)
def test_analysis_rejects_out_of_bounds_day_counts(api, endpoint, params):
    client, fetch = api
    response = client.get(endpoint, params={"code": "USD", **params})
    assert response.status_code == 422
    fetch.assert_not_awaited()


@pytest.mark.parametrize("long_window", [6, 7])
def test_compare_rejects_invalid_window_order_before_fetching(api, long_window):
    client, fetch = api
    response = client.get(
        "/analysis/events-impact-compare",
        params={"code": "USD", "short_window": 7, "long_window": long_window},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Long window must be greater than short window"}
    fetch.assert_not_awaited()


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        ("/analysis/event-impact", {"event_date": "2024-06-12", "days_before": 140, "days_after": 140}),
        ("/analysis/events-impact", {"window_business_days": 140}),
        ("/analysis/events-impact-compare", {"short_window": 7, "long_window": 140}),
    ],
)
def test_business_days_are_converted_before_checking_calendar_span(api, endpoint, params):
    client, fetch = api
    response = client.get(endpoint, params={"code": "USD", **params})
    assert response.status_code == 400
    assert response.json() == {"detail": "Date range cannot exceed 367 days"}
    fetch.assert_not_awaited()


def test_single_event_accepts_one_day_on_each_side(api):
    client, fetch = api
    response = client.get(
        "/analysis/event-impact",
        params={"code": "USD", "event_date": "2024-01-04", "days_before": 1, "days_after": 1},
    )
    assert response.status_code == 200
    assert response.json()["before_date"] == "2024-01-03"
    assert response.json()["after_date"] == "2024-01-05"
    fetch.assert_awaited_once()


def test_default_comparison_still_includes_all_configured_events(api):
    client, fetch = api
    response = client.get("/analysis/events-impact-compare", params={"code": "USD"})
    assert response.status_code == 200
    assert {row["event_id"] for row in response.json()} == {event.event_id for event in EVENTS}
    assert fetch.await_count == 2 * len(EVENTS)
