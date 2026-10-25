from pydantic import BaseModel, Field
from datetime import date

class Currency(BaseModel):
    currency: str
    code: str
    rate: float= Field(gt=0, allow_inf_nan=False)
    date: date

class CurrencyRateEntry(BaseModel):
    no: str
    effectiveDate: date
    mid: float = Field(gt=0, allow_inf_nan=False)

class CurrencyRateRange(BaseModel):
    currency: str
    code: str
    rates: list[CurrencyRateEntry]
