import httpx
import asyncio
import logging
from datetime import date, timedelta
from time import monotonic
from app.models.currency import Currency, CurrencyRateEntry, CurrencyRateRange
from app.services.validation import validate_date_range
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[CurrencyRateRange, float | None]] = {}
_current_rate_cache: dict[str, tuple[Currency, float]] = {}

NBP_API_URL = "https://api.nbp.pl/api/exchangerates/rates/A/"
NBP_MAX_REQUEST_DAYS = 93
CURRENT_RATE_CACHE_TTL_SECONDS = 5 * 60
HISTORY_CACHE_TTL_SECONDS = 5 * 60
HISTORY_CACHE_MAX_ENTRIES = 500

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

    cached = _current_rate_cache.get(code)
    if cached is not None:
        cached_rate, expires_at = cached
        if monotonic() < expires_at:
            logger.info(f"Cache hit for {code}")
            return cached_rate
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
            result = Currency(currency=currency, code=code, rate=rate, date=effective_date)

        except (KeyError, TypeError, IndexError, ValueError):
            raise HTTPException(status_code=500, detail="Invalid response from NBP API")

        _current_rate_cache[code] = (result, monotonic() + CURRENT_RATE_CACHE_TTL_SECONDS)
        logger.info(f"Cached {code} successfully")
        return result
    raise HTTPException(status_code=503, detail="API unavailable after retries")

async def get_currency_rates_range(code: str, start_date: date, end_date: date) -> CurrencyRateRange:
    validate_date_range(start_date, end_date)
    code = code.upper()

    cache_key = f"{code}_{start_date}_{end_date}"
    cached = _cache.get(cache_key)
    if cached is not None:
        cached_history, expires_at = cached
        if expires_at is None or monotonic() < expires_at:
            logger.info(f"Cache hit for {code}")
            return cached_history
    logger.info(f"Cache miss for {code}, fetching from NBP")

    # Capture this before fetching: the response can arrive after midnight.
    includes_today = end_date == date.today()
    currency = None
    rates_by_date: dict[date, CurrencyRateEntry] = {}
    chunk_start = start_date

    while chunk_start <= end_date:
        # Both boundary dates are included, so a 93-day chunk ends 92 days later.
        chunk_end = min(chunk_start + timedelta(days=NBP_MAX_REQUEST_DAYS - 1), end_date)
        chunk = await _fetch_currency_rates_chunk(code, chunk_start, chunk_end)
        if chunk is not None and chunk.rates:
            currency = chunk.currency
            rates_by_date.update((rate.effectiveDate, rate) for rate in chunk.rates)
        chunk_start = chunk_end + timedelta(days=1)

    if currency is None:
        # A 404 for one chunk can mean a weekend or holiday, not an unknown code.
        # Check the code only when the entire requested range has no rates.
        await get_currency_rate(code)
        raise HTTPException(status_code=404, detail="No data found for given range")

    result = CurrencyRateRange(
        currency=currency,
        code=code,
        rates=[rates_by_date[day] for day in sorted(rates_by_date)],
    )
    # Cache only after every chunk succeeds; errors must not save partial history.
    expires_at = monotonic() + HISTORY_CACHE_TTL_SECONDS if includes_today else None
    _cache[cache_key] = (result, expires_at)
    while len(_cache) > HISTORY_CACHE_MAX_ENTRIES:
        oldest_key = next(iter(_cache))
        del _cache[oldest_key]
    logger.info(f"Cached {code} successfully")
    return result


async def _fetch_currency_rates_chunk(
    code: str, start_date: date, end_date: date,
) -> CurrencyRateRange | None:
    """Fetch one NBP range, returning None when it has no published rates."""
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
                return None

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
            return CurrencyRateRange(currency=currency, code=code, rates=rates)

        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=500, detail="Invalid response from NBP API")

    raise HTTPException(status_code=503, detail="API unavailable after retries")
