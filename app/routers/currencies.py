from fastapi import APIRouter
from datetime import date
from app.models.currency import Currency
from app.services.nbp_api import get_currency_rate, get_currency_rates_range
from app.models.currency import CurrencyRateRange


router = APIRouter(prefix="/currencies", tags=["currencies"])

@router.get("/{code}/history", response_model=CurrencyRateRange)

async def get_currency_history(code: str, start_date: date, end_date: date):
    return await get_currency_rates_range(code, start_date, end_date)

@router.get("/{code}", response_model=Currency)

async def get_currency(code: str):
    return await get_currency_rate(code)







