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

def test_event_impact_both_days_zero_returns_400():
    response = client.get("/analysis/event-impact",
                          params={
                              "code": "USD",
                              "event_date": "2026-01-01",
                              "days_before": 0,
                              "days_after":0 })


    assert response.status_code == 400

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

def test_currency_valid_input_returns_200_with_mock():
    fake_response = {"currency": "dolar amerykański",
                     "code": "USD",
                     "rate": 3.72,
                     "date": "2026-01-01"}

    with patch("app.routers.currencies.get_currency_rate", new=AsyncMock(return_value=fake_response)):
        response = client.get("/currencies/USD")

        assert response.status_code == 200
        assert response.json()["code"] == "USD"
        assert response.json()["rate"] == 3.72
        assert response.json()["date"] == "2026-01-01"


def test_historical_valid_input_returns_200_with_mock():
    fake_response = {"currency": "dolar amerykański",
                     "code": "USD",
                     "rates": [{"no": "01/A/NBP/2026", "effectiveDate": "2026-01-01", "mid": 3.38},
                               {"no": "02/A/NBP/2026", "effectiveDate": "2026-01-02", "mid": 3.41},
                               {"no": "03/A/NBP/2026", "effectiveDate": "2026-01-03", "mid": 3.52}]}

    with patch("app.routers.currencies.get_currency_rates_range", new=AsyncMock(return_value=fake_response)):
        response = client.get("/currencies/USD/history",
                              params={"start_date": "2026-01-01", "end_date": "2026-12-31"})

        assert response.status_code == 200
        assert response.json()["code"] == "USD"
        assert response.json()["rates"][0]["no"] == "01/A/NBP/2026"
        assert len(response.json()["rates"]) == 3

