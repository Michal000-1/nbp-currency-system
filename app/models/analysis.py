from pydantic import BaseModel

class EventRatePoint(BaseModel):
    date: str
    rate: float

class EventImpactRate(BaseModel):
    code: str
    event_date:str
    before_date:str
    before_rate: float
    after_date:str
    after_rate: float
    abs_change: float
    pct_change: float
    window_rates: list[EventRatePoint]
