from pydantic import BaseModel
from datetime import date

class EventRatePoint(BaseModel):
    date: date
    rate: float

class EventImpactRate(BaseModel):
    code: str
    event_date: date
    before_date: date
    before_rate: float
    after_date:date
    after_rate: float
    abs_change: float
    pct_change: float
    window_rates: list[EventRatePoint]

class EventDefinition(BaseModel):
   event_id: str
   name: str
   event_date: date

class EventImpactItem(BaseModel):
    event: EventDefinition
    before_date: date
    before_rate: float
    after_date: date
    after_rate: float
    abs_change: float
    pct_change: float
    window_rates: list[EventRatePoint]

class EventImpactResponse(BaseModel):
    code: str
    window_business_days: int
    events: list[EventImpactItem]
