from fastapi import APIRouter, Query
from datetime import date
from app.models.analysis import EventImpactRate, EventImpactResponse
from app.services.analysis_service import analyze_event_impact, analyze_events_impact

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