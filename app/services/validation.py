from datetime import date

from fastapi import HTTPException


MIN_RATE_DATE = date(2002, 1, 2)
# Limit of the application, measured as end_date - start_date
MAX_RANGE_DAYS = 367


def validate_date_range(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date cannot be later than end date")
    if start_date < MIN_RATE_DATE:
        raise HTTPException(status_code=400, detail="Rates are available from 2002-01-02")
    if end_date > date.today():
        raise HTTPException(status_code=400, detail="End date cannot be in the future")
    if (end_date - start_date).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days")


def validate_business_days(value: int, parameter: str) -> None:
    # A wider business-day window cannot fit in the allowed calendar range.
    if not 1 <= value <= MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"{parameter} must be between 1 and {MAX_RANGE_DAYS} business days",
        )
