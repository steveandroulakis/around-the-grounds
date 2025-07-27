"""
Timezone utilities for consistent Pacific timezone handling across all parsers.

This module provides standardized timezone constants and helper functions to ensure
all parsers handle Pacific timezone (America/Los_Angeles) consistently, including
proper PST/PDT transitions.
"""

from datetime import datetime
from typing import Optional

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

# Pacific timezone constant that handles PST/PDT transitions automatically
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def now_in_pacific() -> datetime:
    """
    Get current datetime in Pacific timezone.

    Returns:
        Current datetime as timezone-aware datetime in Pacific timezone
    """
    return datetime.now(PACIFIC_TZ)


def now_in_pacific_naive() -> datetime:
    """
    Get current datetime in Pacific timezone as timezone-naive.

    This is useful for compatibility with existing timezone-naive data models
    while ensuring the time is calculated in Pacific timezone.

    Returns:
        Current datetime as timezone-naive datetime in Pacific time
    """
    return datetime.now(PACIFIC_TZ).replace(tzinfo=None)


def make_pacific_naive(naive_dt: datetime) -> datetime:
    """
    Assume a timezone-naive datetime is in Pacific time and return it as-is.

    This is used when we know a datetime should be interpreted as Pacific time
    but need it to remain timezone-naive for compatibility.

    Args:
        naive_dt: Timezone-naive datetime assumed to be in Pacific time

    Returns:
        The same datetime object (for consistency with data model)
    """
    return naive_dt


def utc_to_pacific_naive(utc_dt: datetime) -> datetime:
    """
    Convert a UTC datetime to Pacific timezone and return as timezone-naive.

    This handles the conversion from UTC to Pacific time (including PST/PDT
    transitions) and removes timezone info for compatibility with the data model.

    Args:
        utc_dt: UTC datetime (timezone-aware or naive)

    Returns:
        Timezone-naive datetime in Pacific time
    """
    if utc_dt.tzinfo is None:
        # Assume naive datetime is UTC
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))

    # Convert to Pacific timezone
    pacific_dt = utc_dt.astimezone(PACIFIC_TZ)

    # Return as timezone-naive for compatibility
    return pacific_dt.replace(tzinfo=None)


def parse_date_with_pacific_context(
    year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None
) -> datetime:
    """
    Create a date using Pacific timezone context for year/month/day calculations.

    This ensures that when parsers calculate current year or month for date parsing,
    they use Pacific timezone instead of system timezone.

    Args:
        year: Year (defaults to current year in Pacific timezone)
        month: Month (defaults to current month in Pacific timezone)
        day: Day (defaults to current day in Pacific timezone)

    Returns:
        Timezone-naive datetime with Pacific timezone context
    """
    current_pacific = now_in_pacific_naive()

    return datetime(
        year or current_pacific.year,
        month or current_pacific.month,
        day or current_pacific.day,
    )


def get_pacific_year() -> int:
    """Get current year in Pacific timezone."""
    return now_in_pacific_naive().year


def get_pacific_month() -> int:
    """Get current month in Pacific timezone."""
    return now_in_pacific_naive().month


def get_pacific_day() -> int:
    """Get current day in Pacific timezone."""
    return now_in_pacific_naive().day


def is_dst_transition_date(date: datetime) -> bool:
    """
    Check if a date is during a DST transition in Pacific timezone.

    This can be useful for testing edge cases around Spring Forward (PST->PDT)
    and Fall Back (PDT->PST) transitions.

    Args:
        date: Date to check

    Returns:
        True if the date is during a DST transition
    """
    # Create timezone-aware datetime for the date
    pacific_date = date.replace(tzinfo=PACIFIC_TZ)

    # Check if the timezone offset changes within a day
    start_of_day = pacific_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = pacific_date.replace(hour=23, minute=59, second=59, microsecond=0)

    return start_of_day.utcoffset() != end_of_day.utcoffset()


def format_time_with_timezone(dt: datetime, include_timezone: bool = True) -> str:
    """
    Format a datetime for display with optional timezone indicator.

    Args:
        dt: Datetime to format (assumed to be Pacific time if timezone-naive)
        include_timezone: Whether to include "PT" timezone indicator

    Returns:
        Formatted time string like "2:00 PM PT" or "2:00 PM"
    """
    time_str = dt.strftime("%I:%M %p").lstrip("0")  # Remove leading zero from hour

    if include_timezone:
        # Use "PT" as general Pacific Time indicator (covers both PST and PDT)
        time_str += " PT"

    return time_str
