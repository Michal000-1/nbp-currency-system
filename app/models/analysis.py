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

class CompareEvents(BaseModel):
    code: str
    event_id: str
    short_window: int
    long_window: int
    event_name: str
    pct_change_short: float
    pct_change_long: float
    abs_change_short: float
    abs_change_long: float
    is_short_stronger_pct: str
