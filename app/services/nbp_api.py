import httpx
import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo
from app.models.currency import Currency, CurrencyRateRange
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_current_cache = {}
_range_cache = {}
ONE_DAY_TTL_SECONDS = 24 * 60 * 60

def cleanup_current_cache(today_key: str):
    removed = 0
    for key in list(_current_cache.keys()):
        if not key.endswith(today_key):
            del _current_cache[key]
            removed += 1
    if removed > 0:
        logger.info(f"Current cache removed {removed}")

def cleanup_range_cache(now):
    removed = 0
    for key in list(_range_cache.keys()):
        saved_at, _result = _range_cache[key]
        age_seconds = (now - saved_at).total_seconds()
        if age_seconds > ONE_DAY_TTL_SECONDS:
            del _range_cache[key]
            removed += 1

    if removed > 0:
        logger.info(f"Range cache removed {removed}")



NBP_API_URL = "https://api.nbp.pl/api/exchangerates/rates/A/"

WARSAW_TZ = ZoneInfo('Europe/Warsaw')

_client: httpx.AsyncClient | None = None

async def init_http_client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=5)
    return _client

async def close_http_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None

def get_http_client() -> httpx.AsyncClient:
    if _client is None:
        raise HTTPException(status_code=500, detail="HTTP client unavailable")
    return _client

async def get_currency_rate(code: str) -> Currency:
    code = code.upper()
    today_key = datetime.now(tz=WARSAW_TZ).date().isoformat()
    cache_key = f"{code}_{today_key}"
    cleanup_current_cache(today_key)

    if cache_key in _current_cache:
        logger.info(f"Cache hit for {code}")
        return _current_cache[cache_key]
    logger.info(f"Cache miss for {code}, fetching from NBP")

    url = f"{NBP_API_URL}{code}"
    max_tries = 3
    client = get_http_client()

    for attempt in range(max_tries):
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code if error.response else 500
            if status_code == 404:
                raise HTTPException(status_code=status_code, detail="Currency not found")

            if status_code in (500, 503) and attempt < max_tries - 1:
                logger.warning(f"Retry attempt {attempt + 1}/{max_tries} for {code}")
                await asyncio.sleep(2)
                continue
            raise HTTPException(status_code=status_code, detail="NBP API error")

        except httpx.RequestError:
            if attempt < max_tries -1:
                logger.warning(f"Retry attempt {attempt + 1}/{max_tries} for {code}")
                await asyncio.sleep(2)
                continue
            raise HTTPException(status_code=503, detail="API unavailable")

        except (httpx.DecodingError, ValueError):
            raise HTTPException(status_code=500, detail="Invalid response from NBP API")

        try:
            rate = data["rates"][0]["mid"]
            currency = data["currency"]
            effective_date = data["rates"][0]["effectiveDate"]

        except (KeyError, TypeError, IndexError):
            raise HTTPException(status_code=500, detail="Invalid response from NBP API")

        result = Currency(currency=currency, code=code, rate=rate, date=effective_date)
        _current_cache[cache_key] = result
        logger.info(f"Cached {code} successfully")
        return result
    raise HTTPException(status_code=503, detail="API unavailable after retries")

async def get_currency_rates_range(code: str, start_date: date, end_date: date) -> CurrencyRateRange:
    code = code.upper()
    cache_key = f"{code}_{start_date}_{end_date}"
    now = datetime.now(tz=WARSAW_TZ)
    cleanup_range_cache(now)

    if cache_key in _range_cache:
        logger.info(f"Cache hit for {code}")
        _saved_at, cached_result = _range_cache[cache_key]
        return cached_result
    logger.info(f"Cache miss for {code}, fetching from NBP")

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be later than end date")
    
    url = f"{NBP_API_URL}{code}/{start_date}/{end_date}"
    max_tries = 3
    client = get_http_client()

    for attempt in range(max_tries):
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code if error.response else 500
            if status_code == 404:
                try:
                    await get_currency_rate(code)
                except HTTPException as code_error:
                    if code_error.status_code == 404:
                        raise HTTPException(status_code=404, detail="Currency not found")
                    else:
                        raise code_error
                raise HTTPException(status_code=status_code, detail="No data found for given range")

            if status_code in (500, 503) and attempt < max_tries - 1:
                logger.warning(f"Retry attempt {attempt + 1}/{max_tries} for {code}")
                await asyncio.sleep(2)
                continue
            raise HTTPException(status_code=status_code, detail="NBP API error")

        except httpx.RequestError:
            if attempt < max_tries - 1:
                logger.warning(f"Retry attempt {attempt + 1}/{max_tries} for {code}")
                await asyncio.sleep(2)
                continue
            raise HTTPException(status_code=503, detail="API unavailable")

        except (httpx.DecodingError, ValueError):
            raise HTTPException(status_code=500, detail="Invalid response from NBP API")

        try:
            rates = data["rates"]
            currency = data["currency"]

        except (KeyError, TypeError):
            raise HTTPException(status_code=500, detail="Invalid response from NBP API")

        result = CurrencyRateRange(currency=currency, code=code, rates=rates)
        _range_cache[cache_key] = (now, result)
        logger.info(f"Cached {code} successfully")
        return result
    raise HTTPException(status_code=503, detail="API unavailable after retries")


