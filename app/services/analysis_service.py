from datetime import date, timedelta
from fastapi import HTTPException
from app.models.analysis import EventImpactRate, EventRatePoint
from app.services.nbp_api import get_currency_rate, get_currency_rates_range

async def analyze_event_impact(code:str, event_date:date, days_before:int, days_after:int) -> EventImpactRate:

    if days_before == 0 and days_after == 0:
        raise HTTPException(status_code=400, detail="Days before or after cannot both be 0")

    start_date = event_date - timedelta(days=days_before)
    end_date = event_date + timedelta(days=days_after)

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
        d = date.fromisoformat(r.effectiveDate)
        points.append((d, r.mid))

    before_candidates = []
    after_candidates = []

    for d, rate in points:
        if d <= event_date:
            before_candidates.append((d, rate))
        if d >= event_date:
            after_candidates.append((d, rate))

    if not before_candidates:
        raise HTTPException(status_code=404, detail="No rate on before event_date in selected range")

    if not after_candidates:
        raise HTTPException(status_code=404, detail="No rate on after event_date in selected range")

    before_date, before_rate = before_candidates[-1]
    after_date, after_rate = after_candidates[0]

    abs_change_raw = after_rate - before_rate
    pct_change_raw = 0.0 if before_rate == 0 else (abs_change_raw / before_rate) * 100

    abs_change = round(abs_change_raw, 3)
    pct_change = round(pct_change_raw, 3)

    window_rates = [EventRatePoint(date=r.effectiveDate, rate=r.mid) for r in history.rates]

    return EventImpactRate(code=code.upper(), event_date=event_date.isoformat(), before_date=before_date.isoformat(), before_rate=before_rate,
                           after_date=after_date.isoformat(), after_rate=after_rate, pct_change=pct_change, window_rates=window_rates,
                           abs_change=abs_change)

