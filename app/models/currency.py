
from pydantic import BaseModel

class Currency(BaseModel):
    currency: str
    code: str
    rate: float
    date: str

class CurrencyRateEntry(BaseModel):
    no: str
    effectiveDate: str
    mid: float

class CurrencyRateRange(BaseModel):
    currency: str
    code: str
    rates: list[CurrencyRateEntry]
