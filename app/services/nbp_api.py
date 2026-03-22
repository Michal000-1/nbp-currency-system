import httpx
from datetime import date
from app.models.currency import Currency, CurrencyRateRange, CurrencyRateEntry
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
        raise HTTPException(status_code=status_code, detail=str(error))

    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="API unavailable")

    except (httpx.DecodingError, ValueError):
        raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    rate = data["rates"][0]["mid"]
    effective_date = data["rates"][0]["effectiveDate"]

    return Currency(currency=data["currency"], code=code, rate=rate, date=effective_date)

async def get_currency_rates_range(code: str, start_date: date, end_date: date) -> CurrencyRateRange:
    code=code.upper()
    url = f"{NBP_API_URL}{code}/{start_date}/{end_date}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code if error.response else 500
        raise HTTPException(status_code=status_code, detail=str(error))

    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="API unavailable")

    except (httpx.DecodingError, ValueError):
        raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    rates = data["rates"]

    return CurrencyRateRange(currency=data["currency"], code=code, rates=rates)



