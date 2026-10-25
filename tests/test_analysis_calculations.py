import asyncio
from datetime import date
from unittest.mock import AsyncMock, call

import pytest

from app.models.analysis import EventDefinition
from app.models.currency import CurrencyRateRange
from app.services import analysis_service


def make_history(rates: list[tuple[str, float]]) -> CurrencyRateRange:
    return CurrencyRateRange(
        currency="dolar amerykański",
        code="USD",
        rates=[
            {"no": "test", "effectiveDate": day, "mid": rate}
            for day, rate in rates
        ],
    )


@pytest.mark.parametrize(
    ("before_rate", "after_rate", "expected_change", "expected_pct"),
    [
        (4.0, 4.1, 0.1, 2.5),
        (4.0, 3.9, -0.1, -2.5),
        (4.0, 4.0, 0.0, 0.0),
        (4.1, 4.0, -0.1, -2.439),
        (3.0, 3.1004, 0.1, 3.347),
        (3.0, 2.8996, -0.1, -3.347),
    ],
    ids=[
        "increase",
        "decrease",
        "unchanged",
        "percentage-relative-to-before-rate",
        "round-increase-after-calculating-percentage",
        "round-decrease-after-calculating-percentage",
    ],
)
def test_event_impact_calculates_signed_changes(
    monkeypatch, before_rate, after_rate, expected_change, expected_pct
):
    # Expected results are fixed examples, independent of the production formula.
    get_history = AsyncMock(
        return_value=make_history(
            [("2024-06-11", before_rate), ("2024-06-13", after_rate)]
        )
    )
    monkeypatch.setattr(analysis_service, "get_currency_rates_range", get_history)

    result = asyncio.run(
        analysis_service.analyze_event_impact("USD", date(2024, 6, 12), 1, 1)
    )

    assert (result.abs_change, result.pct_change) == pytest.approx(
        (expected_change, expected_pct), rel=0, abs=1e-9
    )
    assert result.before_rate == before_rate
    assert result.after_rate == after_rate
    get_history.assert_awaited_once_with(
        "USD", date(2024, 6, 11), date(2024, 6, 13)
    )


def test_event_impact_uses_closest_before_and_last_after_rate(monkeypatch):
    # Unsorted data includes an older baseline, an early after-rate and the event
    # day itself. None of those three rates should determine the reported change.
    get_history = AsyncMock(
        return_value=make_history(
            [
                ("2024-06-14", 4.1),
                ("2024-06-12", 9.0),
                ("2024-06-11", 4.0),
                ("2024-06-13", 3.0),
                ("2024-06-10", 8.0),
            ]
        )
    )
    monkeypatch.setattr(analysis_service, "get_currency_rates_range", get_history)

    result = asyncio.run(
        analysis_service.analyze_event_impact("USD", date(2024, 6, 12), 2, 2)
    )

    assert (result.before_date, result.before_rate) == (date(2024, 6, 11), 4.0)
    assert (result.after_date, result.after_rate) == (date(2024, 6, 14), 4.1)
    assert (result.abs_change, result.pct_change) == pytest.approx(
        (0.1, 2.5), rel=0, abs=1e-9
    )


@pytest.mark.parametrize(
    (
        "short_rate", "long_rate", "short_change", "long_change",
        "short_pct", "long_pct", "stronger_pct", "short_stronger_abs",
    ),
    [
        (4.2, 4.1, 0.2, 0.1, 5.0, 2.5, "short", True),
        (4.1, 4.2, 0.1, 0.2, 2.5, 5.0, "long", False),
        (3.8, 4.1, -0.2, 0.1, -5.0, 2.5, "short", True),
        (4.1, 3.8, 0.1, -0.2, 2.5, -5.0, "long", False),
        (4.1, 3.9, 0.1, -0.1, 2.5, -2.5, "equal", False),
        (4.1, 4.1, 0.1, 0.1, 2.5, 2.5, "equal", False),
        (4.0, 4.0, 0.0, 0.0, 0.0, 0.0, "equal", False),
        (4.0, 4.1, 0.0, 0.1, 0.0, 2.5, "long", False),
        (3.9, 4.0, -0.1, 0.0, -2.5, 0.0, "short", True),
    ],
    ids=[
        "short-stronger-increase",
        "long-stronger-increase",
        "short-stronger-decrease",
        "long-stronger-decrease",
        "equal-opposite-directions",
        "equal-same-direction",
        "both-unchanged",
        "short-unchanged",
        "long-unchanged",
    ],
)
def test_event_comparison_calculates_both_windows(
    monkeypatch, short_rate, long_rate, short_change, long_change,
    short_pct, long_pct, stronger_pct, short_stronger_abs,
):
    event = EventDefinition(
        event_id="example", name="Example event", event_date=date(2024, 6, 12)
    )
    monkeypatch.setattr(analysis_service, "EVENTS", [event])
    rates = [
        ("2024-06-07", 8.0),
        ("2024-06-11", 4.0),
        ("2024-06-12", 9.0),
        ("2024-06-13", short_rate),
        ("2024-06-17", long_rate),
    ]

    async def history_for_range(code, start_date, end_date):
        return make_history(
            [
                (day, rate) for day, rate in rates
                if start_date <= date.fromisoformat(day) <= end_date
            ]
        )

    # Both windows use the same source series. Run real calculations, aggregation,
    # DataFrame comparison and response mapping; only the NBP data is substituted.
    get_history = AsyncMock(side_effect=history_for_range)
    monkeypatch.setattr(analysis_service, "get_currency_rates_range", get_history)

    results = asyncio.run(analysis_service.get_events_impact_compare("USD", 1, 3))

    assert len(results) == 1
    result = results[0]
    assert result.code == "USD"
    assert (result.event_id, result.event_name) == (event.event_id, event.name)
    assert (result.short_window, result.long_window) == (1, 3)
    assert (
        result.abs_change_short, result.abs_change_long,
        result.pct_change_short, result.pct_change_long,
    ) == pytest.approx(
        (short_change, long_change, short_pct, long_pct), rel=0, abs=1e-9
    )
    assert result.is_short_stronger_pct == stronger_pct
    assert result.is_short_stronger_abs is short_stronger_abs
    assert get_history.await_args_list == [
        call("USD", date(2024, 6, 11), date(2024, 6, 13)),
        call("USD", date(2024, 6, 7), date(2024, 6, 17)),
    ]
