"""
Time utility helpers shared across modules.
"""
from datetime import datetime, timezone
from typing import Optional

import pytz


def to_utc(dt: datetime, tz_name: str) -> datetime:
    """
    Convert a naive datetime (assumed to be in tz_name timezone) to UTC-aware datetime.
    If dt is already timezone-aware, convert directly to UTC.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    try:
        local_tz = pytz.timezone(tz_name)
        localized = local_tz.localize(dt, is_dst=None)
        return localized.astimezone(timezone.utc)
    except Exception:
        # Fall back: treat as UTC
        return dt.replace(tzinfo=timezone.utc)


def local_to_utc(dt: datetime, tz_name: str) -> datetime:
    """Alias for to_utc for clarity at call sites."""
    return to_utc(dt, tz_name)


def utc_to_local(dt_utc: datetime, tz_name: str) -> datetime:
    """Convert UTC-aware datetime to a specific local timezone."""
    local_tz = pytz.timezone(tz_name)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(local_tz)


def format_slot(start_utc: datetime, end_utc: datetime, tz_name: str) -> str:
    """
    Return a human-readable slot string in the given timezone.
    Example: "Monday, April 1 at 3:00 PM – 4:00 PM IST"
    """
    local_tz = pytz.timezone(tz_name)
    tzabbr = datetime.now(local_tz).strftime("%Z")
    start_local = utc_to_local(start_utc, tz_name)
    end_local = utc_to_local(end_utc, tz_name)
    date_str = start_local.strftime("%A, %B %-d")
    start_str = start_local.strftime("%-I:%M %p")
    end_str = end_local.strftime("%-I:%M %p")
    return f"{date_str} at {start_str} – {end_str} {tzabbr}"


def now_utc() -> datetime:
    """Return current time as UTC-aware datetime."""
    return datetime.now(timezone.utc)
