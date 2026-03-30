import httpx
from datetime import date
from app.models.currency import Currency, CurrencyRateRange
from fastapi import HTTPException

NBP_API_URL = "https://api.nbp.pl/api/exchangerates/rates/A/"

async def get_currency_rate(code: str) -> Currency:
    code = code.upper()
    url = f"{NBP_API_URL}{code}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response  = await client.get(url)
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code if error.response else 500
        if status_code == 404:
            raise HTTPException(status_code=status_code, detail="Currency not found")
        raise HTTPException(status_code=status_code, detail="NBP API error")

    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="API unavailable")

    except (httpx.DecodingError, ValueError):
        raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    try:
        rate = data["rates"][0]["mid"]
        currency = data["currency"]
        effective_date = data["rates"][0]["effectiveDate"]
    except (KeyError, TypeError, IndexError):
        raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    return Currency(currency=currency, code=code, rate=rate, date=effective_date)

async def get_currency_rates_range(code: str, start_date: date, end_date: date) -> CurrencyRateRange:

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be later than end date")

    code = code.upper()
    url = f"{NBP_API_URL}{code}/{start_date}/{end_date}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code if error.response else 500
        if status_code == 404:
            raise HTTPException(status_code=status_code, detail="No data found for given range")
        raise HTTPException(status_code=status_code, detail="NBP API error")

    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="API unavailable")

    except (httpx.DecodingError, ValueError):
        raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    try:
        rates = data["rates"]
        currency = data["currency"]

    except (KeyError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    return CurrencyRateRange(currency=currency, code=code, rates=rates)



