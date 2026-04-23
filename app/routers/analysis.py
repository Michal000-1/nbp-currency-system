from fastapi import APIRouter, Query, HTTPException
from datetime import date
from app.models.analysis import EventImpactRate, EventImpactResponse, CompareEvents
from app.services.analysis_service import analyze_event_impact, analyze_events_impact

from app.services.pandas_analysis import build_events_dataframe, compare_windows

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/event-impact", response_model=EventImpactRate)
async def get_event_impact(code: str=Query(..., min_length=3, max_length=3, pattern="^[A-Za-z]{3}$"), event_date:date=Query(..., description="Enter a date in YYYY-MM-DD format"),
                           days_before: int=Query(7, ge=0),
                           days_after: int=Query(7, ge=0)):
    return await analyze_event_impact(code, event_date, days_before, days_after)

@router.get("/events-impact", response_model=EventImpactResponse)
async def get_all_events_impact(code: str=Query(..., min_length=3, max_length=3, pattern="^[A-Za-z]{3}$"),
                                window_business_days: int=Query(7, ge=1)):
    return await analyze_events_impact(code, window_business_days)

@router.get("/events-impact-compare", response_model=list[CompareEvents])
async def get_event_impact_compare(code: str=Query(..., min_length=3, max_length=3, pattern="^[A-Za-z]{3}$"),
                             short_window: int = Query(7, ge=1),
                             long_window: int = Query(21, ge=1)):

    if long_window <= short_window:
        raise HTTPException(status_code=400, detail="Long window must be greater than short window")

    short_response = await analyze_events_impact(code, short_window)
    long_response = await analyze_events_impact(code, long_window)

    df_week = build_events_dataframe(code, short_window, short_response.events)
    df_3weeks = build_events_dataframe(code, long_window, long_response.events)

    compared_df = compare_windows(df_week, df_3weeks)
    if compared_df.empty:
        return []

    compared_df = compared_df.rename(columns={
                                              "pct_change_week": "pct_change_short",
                                              "pct_change_3weeks": "pct_change_long",
                                              "abs_change_week": "abs_change_short",
                                              "abs_change_3weeks": "abs_change_long",
                                              "is_week_stronger_pct_change": "is_short_stronger_pct",
                                              })

    compared_df["code"] = code.upper()
    compared_df["short_window"] = short_window
    compared_df["long_window"] = long_window

    return compared_df.to_dict(orient="records")
