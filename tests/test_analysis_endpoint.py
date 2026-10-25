import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import AsyncMock, patch

client = TestClient(app)

def test_event_impact_negative_days_returns_422():
    response = client.get("/analysis/event-impact",
                          params={
                              "code": "USD",
                              "event_date": "2026-01-01",
                              "days_before": -1,
                              "days_after": 3})

    assert response.status_code == 422

@pytest.mark.parametrize(("days_before", "days_after"), [(0, 0), (0, 3), (3, 0)])
def test_event_impact_zero_days_returns_422(days_before, days_after):
    response = client.get("/analysis/event-impact",
                          params={
                              "code": "USD",
                              "event_date": "2026-01-01",
                              "days_before": days_before,
                              "days_after": days_after })


    assert response.status_code == 422

def test_event_impact_invalid_format_code_returns_422():
    response = client.get("/analysis/event-impact",
                          params={
                              "code": "USDDD",
                              "event_date": "2026-01-01",
                              "days_before": 3,
                              "days_after": 3 })

    assert response.status_code == 422


def test_event_impact_valid_input_returns_200_with_mock():

    fake_response = {"code": "USD",
                     "event_date": "2026-01-01",
                     "before_date": "2025-12-31",
                     "before_rate": 4.22,
                     "after_date": "2026-01-02",
                     "after_rate": 4.09,
                     "abs_change": -0.13,
                     "pct_change": -3.08,
                     "window_rates": [{"date": "2026-01-01", "rate": 4.10}]}

    with patch("app.routers.analysis.analyze_event_impact", new=AsyncMock(return_value=fake_response)):
        response = client.get("/analysis/event-impact",
                              params={
                                    "code": "USD",
                                    "event_date": "2026-01-01",
                                    "days_before": 3,
                                    "days_after": 3
                                })
        assert response.status_code == 200
        assert response.json()["code"] == "USD"
        assert "window_rates" in response.json()


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        (
            "/analysis/events-impact",
            {"code": "ZZZ", "window_business_days": 7},
        ),
        (
            "/analysis/events-impact-compare",
            {"code": "ZZZ", "short_window": 7, "long_window": 21},
        ),
    ],
    ids=["all-events", "compare-events"],
)
def test_events_impact_unknown_currency_returns_404(monkeypatch, endpoint, params):
    # Keep the real analysis functions; replace only the NBP service calls.
    get_history = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Currency not found")
    )
    get_current_rate = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Currency not found")
    )
    monkeypatch.setattr("app.services.analysis_service.get_currency_rates_range", get_history)
    monkeypatch.setattr("app.services.analysis_service.get_currency_rate", get_current_rate)

    response = client.get(endpoint, params=params)

    assert response.status_code == 404
    assert response.json() == {"detail": "Currency not found"}
    # An invalid currency must stop the analysis at the first event.
    get_history.assert_awaited_once()
    get_current_rate.assert_awaited_once_with("ZZZ")
