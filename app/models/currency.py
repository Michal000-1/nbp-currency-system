from pydantic import BaseModel
from datetime import date

class Currency(BaseModel):
    currency: str
    code: str
    rate: float
    date: date

class CurrencyRateEntry(BaseModel):
    no: str
    effectiveDate: str
    mid: float

class CurrencyRateRange(BaseModel):
    currency: str
    code: str
    rates: list[CurrencyRateEntry]
