from datetime import date, timedelta
from fastapi import HTTPException
from app.models.analysis import EventImpactRate, EventRatePoint, EventImpactResponse, EventImpactItem
from app.services.nbp_api import get_currency_rate, get_currency_rates_range
from app.services.events import EVENTS
from app.services.pandas_analysis import build_events_dataframe, compare_windows
from app.services.validation import validate_business_days, validate_date_range
from app.models.analysis import CompareEvents
import holidays

PL_HOLIDAYS = holidays.country_holidays("PL")

def shift_business_days(base_date: date, business_days: int, direction: int) -> date:

    if direction not in (-1, 1):
        raise ValueError("Direction must be in (-1, 1)")
    if business_days == 0:
        return base_date

    current = base_date
    moved = 0

    while moved < business_days:
        current = current + timedelta(days=direction)
        if current.weekday() < 5 and current not in PL_HOLIDAYS:
            moved = moved + 1

    return current

def get_event_date_range(event_date: date, days_before: int, days_after: int) -> tuple[date, date]:
    validate_business_days(days_before, "Days before")
    validate_business_days(days_after, "Days after")
    validate_date_range(event_date, event_date)

    start_date = shift_business_days(event_date, days_before, -1)
    end_date = shift_business_days(event_date, days_after, 1)
    validate_date_range(start_date, end_date)
    return start_date, end_date


async def analyze_event_impact(code:str, event_date:date, days_before:int, days_after:int) -> EventImpactRate:
    """Analyses the impact of a single event on the exchange rate within a given business day window.
    Determines the 'before' rate as the closest available rate prior to the event date,
    and the 'after' rate as the last available rate in the window. Calculates the nominal change (abs_change) and percentage change (pct_change),
    and returns the full set of rates from the analysed window."""

    code = code.upper()

    start_date, end_date = get_event_date_range(event_date, days_before, days_after)

    try:
        history = await get_currency_rates_range(code, start_date, end_date)
    except HTTPException as error:
        if error.status_code != 404:
            raise error

        try:
            await get_currency_rate(code)
        except HTTPException as code_error:
            if code_error.status_code == 404:
                raise HTTPException(status_code=404, detail="Currency not found")
            raise code_error

        raise HTTPException(status_code=404, detail="No data found for selected range")

    points = []
    for r in history.rates:
        d = r.effectiveDate
        points.append((d, r.mid))
    points.sort(key=lambda point: point[0])

    before_candidates = []
    after_candidates = []

    for d, rate in points:
        if d < event_date:
            before_candidates.append((d, rate))
        if d > event_date:
            after_candidates.append((d, rate))

    if not before_candidates:
        raise HTTPException(status_code=404, detail="No rate on before event_date in selected range")

    if not after_candidates:
        raise HTTPException(status_code=404, detail="No rate on after event_date in selected range")

    before_date, before_rate = before_candidates[-1]
    after_date, after_rate = after_candidates[-1]

    abs_change_raw = after_rate - before_rate
    pct_change_raw = 0.0 if before_rate == 0 else (abs_change_raw / before_rate) * 100

    abs_change = round(abs_change_raw, 3)
    pct_change = round(pct_change_raw, 3)

    window_rates = [EventRatePoint(date=r.effectiveDate, rate=r.mid) for r in history.rates]

    return EventImpactRate(code=code, event_date=event_date, before_date=before_date, before_rate=before_rate,
                           after_date=after_date, after_rate=after_rate, pct_change=pct_change, window_rates=window_rates,
                           abs_change=abs_change)


async def analyze_events_impact(code:str, window_business_days: int) -> EventImpactResponse:
    """Analyses the impact of all predefined events for a given currency and business-day window.
    Runs single-event impact analysis for each event from the EVENTS list, skips events with unavailable data (404),
    and returns a combined response containing per-event metrics and window rates."""

    code = code.upper()

    validate_business_days(window_business_days, "Window business days")

    # Check every requested window before starting any NBP requests.
    for event in EVENTS:
        get_event_date_range(event.event_date, window_business_days, window_business_days)

    items: list[EventImpactItem] = []

    for event in EVENTS:
        try:
            impact_rate = await analyze_event_impact(code, event.event_date, window_business_days, window_business_days)
        except HTTPException as error:
            if error.status_code == 404 and error.detail == "Currency not found":
                raise HTTPException(status_code=404, detail="Currency not found")
            if error.status_code == 404:
                continue
            raise error

        item = EventImpactItem(event=event, before_date=impact_rate.before_date ,before_rate=impact_rate.before_rate, after_date=impact_rate.after_date, after_rate=impact_rate.after_rate,
                        abs_change=impact_rate.abs_change, pct_change=impact_rate.pct_change, window_rates=impact_rate.window_rates,)
        items.append(item)

    return EventImpactResponse(code=code, window_business_days=window_business_days ,events=items)


async def get_events_impact_compare(code: str, short_window: int, long_window: int) -> list[CompareEvents]:

    validate_business_days(short_window, "Short window")
    validate_business_days(long_window, "Long window")
    if long_window <= short_window:
        raise HTTPException(status_code=400, detail="Long window must be greater than short window")

    # The short window is contained in the long one. Validate the long one first
    # so an invalid comparison never starts fetching the short-window data.
    for event in EVENTS:
        get_event_date_range(event.event_date, long_window, long_window)

    short_response = await analyze_events_impact(code, short_window)
    long_response = await analyze_events_impact(code, long_window)

    df_short = build_events_dataframe(code, short_window, short_response.events)
    df_long = build_events_dataframe(code, long_window, long_response.events)

    compared_df = compare_windows(df_short, df_long)

    if compared_df.empty:
        return []

    compared_df = compared_df.rename(columns={
                                              "pct_change_week": "pct_change_short",
                                              "pct_change_3weeks": "pct_change_long",
                                              "abs_change_week": "abs_change_short",
                                              "abs_change_3weeks": "abs_change_long",
                                              "is_week_stronger_pct_change": "is_short_stronger_pct",
                                              "is_week_stronger_abs_change": "is_short_stronger_abs",
                                              })
    compared_df["code"] = code.upper()
    compared_df["short_window"] = short_window
    compared_df["long_window"] = long_window

    rows = compared_df.to_dict(orient="records")

    return [CompareEvents(**row) for row in rows]




