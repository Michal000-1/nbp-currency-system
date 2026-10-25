import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, call

import pytest
from fastapi import HTTPException

from app.models.analysis import EventDefinition, EventImpactRate, EventRatePoint
from app.services import analysis_service
from app.services.analysis_service import shift_business_days

@pytest.mark.parametrize(
    ("base_date", "direction", "expected_date"),
    [
        (date(2025, 4, 18), 1, date(2025, 4, 22)),
        (date(2025, 4, 22), -1, date(2025, 4, 18)),
        (date(2026, 4, 3), 1, date(2026, 4, 7)),
        (date(2026, 4, 7), -1, date(2026, 4, 3)),
    ],
    ids=["2025-forward", "2025-backward", "2026-forward", "2026-backward"],
)
def test_shift_business_days_skips_easter_monday(
    base_date, direction, expected_date
):
    # Easter Monday falls on April 21 in 2025 and April 6 in 2026.
    # Expected dates are explicit, independent of the function's holiday calendar.
    result = shift_business_days(base_date, 1, direction)

    assert result == expected_date


@pytest.mark.parametrize(
    ("base_date", "direction", "expected_date"),
    [
        (date(2024, 12, 24), 1, date(2024, 12, 27)),
        (date(2024, 12, 27), -1, date(2024, 12, 24)),
        (date(2026, 12, 23), 1, date(2026, 12, 28)),
        (date(2026, 12, 28), -1, date(2026, 12, 23)),
    ],
    ids=["2024-forward", "2024-backward", "2026-forward", "2026-backward"],
)
def test_shift_business_days_skips_christmas(base_date, direction, expected_date):
    # In 2024, December 25 and 26 are weekdays; Christmas Eve is still a workday.
    # In 2026, also skip Christmas Eve and the weekend after Christmas Day.
    result = shift_business_days(base_date, 1, direction)

    assert result == expected_date


@pytest.mark.parametrize(
    ("base_date", "direction", "expected_date"),
    [
        (date(2026, 2, 20), 1, date(2026, 2, 23)),
        (date(2026, 2, 23), -1, date(2026, 2, 20)),
    ],
    ids=["forward", "backward"],
)
def test_shift_business_days_skips_weekends(base_date, direction, expected_date):
    result = shift_business_days(base_date, 1, direction)

    assert result == expected_date


@pytest.mark.parametrize(
    ("base_date", "direction", "expected_date"),
    [
        (date(2025, 12, 31), 1, date(2026, 1, 2)),
        (date(2026, 1, 2), -1, date(2025, 12, 31)),
    ],
    ids=["forward", "backward"],
)
def test_shift_business_days_skips_new_year(base_date, direction, expected_date):
    result = shift_business_days(base_date, 1, direction)

    assert result == expected_date


@pytest.mark.parametrize(
    ("base_date", "direction", "expected_date"),
    [
        (date(2026, 4, 2), 1, date(2026, 4, 8)),
        (date(2026, 4, 8), -1, date(2026, 4, 2)),
    ],
    ids=["forward", "backward"],
)
def test_shift_business_days_counts_multiple_business_days(
    base_date, direction, expected_date
):
    result = shift_business_days(base_date, 3, direction)

    assert result == expected_date


@pytest.mark.parametrize("direction", [-1, 1], ids=["backward", "forward"])
@pytest.mark.parametrize(
    "base_date",
    [date(2026, 4, 3), date(2026, 4, 4), date(2026, 4, 6)],
    ids=["weekday", "weekend", "holiday"],
)
def test_shift_business_days_zero_returns_base_date(base_date, direction):
    assert shift_business_days(base_date, 0, direction) == base_date


@pytest.mark.parametrize("direction", [-2, 0, 2])
def test_shift_business_days_rejects_invalid_direction(direction):
    with pytest.raises(ValueError, match="Direction"):
        shift_business_days(date(2026, 4, 3), 1, direction)


@pytest.fixture
def events_for_analysis(monkeypatch):
    events = [
        EventDefinition(
            event_id="first", name="First event", event_date=date(2026, 1, 13)
        ),
        EventDefinition(
            event_id="middle", name="Middle event", event_date=date(2026, 2, 17)
        ),
        EventDefinition(
            event_id="last", name="Last event", event_date=date(2026, 3, 17)
        ),
    ]
    monkeypatch.setattr(analysis_service, "EVENTS", events)
    return events


@pytest.mark.parametrize(
    "missing_data_detail",
    [
        "No data found for selected range",
        "No rate on before event_date in selected range",
        "No rate on after event_date in selected range",
    ],
    ids=["no-range-data", "no-before-rate", "no-after-rate"],
)
def test_analyze_events_impact_skips_missing_data_and_keeps_other_events(
    monkeypatch, events_for_analysis, missing_data_detail
):
    successful_impacts = []
    for event in (events_for_analysis[0], events_for_analysis[2]):
        before_date = event.event_date - timedelta(days=1)
        after_date = event.event_date + timedelta(days=1)
        successful_impacts.append(
            EventImpactRate(
                code="USD",
                event_date=event.event_date,
                before_date=before_date,
                before_rate=4.0,
                after_date=after_date,
                after_rate=4.1,
                abs_change=0.1,
                pct_change=2.5,
                window_rates=[
                    EventRatePoint(date=before_date, rate=4.0),
                    EventRatePoint(date=after_date, rate=4.1),
                ],
            )
        )

    # Only the middle event lacks data. The real aggregation must continue.
    single_analysis = AsyncMock(
        side_effect=[
            successful_impacts[0],
            HTTPException(status_code=404, detail=missing_data_detail),
            successful_impacts[1],
        ]
    )
    monkeypatch.setattr(analysis_service, "analyze_event_impact", single_analysis)

    result = asyncio.run(analysis_service.analyze_events_impact("USD", 7))

    assert result.code == "USD"
    assert result.window_business_days == 7
    assert [item.event for item in result.events] == [
        events_for_analysis[0],
        events_for_analysis[2],
    ]
    assert single_analysis.await_args_list == [
        call("USD", event.event_date, 7, 7) for event in events_for_analysis
    ]


def test_analyze_events_impact_propagates_503_and_stops(
    monkeypatch, events_for_analysis
):
    single_analysis = AsyncMock(
        side_effect=HTTPException(status_code=503, detail="API unavailable")
    )
    monkeypatch.setattr(analysis_service, "analyze_event_impact", single_analysis)

    with pytest.raises(HTTPException) as error:
        asyncio.run(analysis_service.analyze_events_impact("USD", 7))

    assert error.value.status_code == 503
    assert error.value.detail == "API unavailable"
    single_analysis.assert_awaited_once_with(
        "USD", events_for_analysis[0].event_date, 7, 7
    )
