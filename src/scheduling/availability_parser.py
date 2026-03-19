"""
Availability Parser.

Extracts structured time slots from free-form email text using:
  1. LLM (primary) — returns JSON list of { start, end } objects
  2. dateparser + parsedatetime (secondary) — for regex/NL date extraction
  3. Returns empty list if nothing can be found (caller handles gracefully)

All extracted datetimes are normalized to UTC.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional

import dateparser
import parsedatetime

import config
from src.llm.llm_client import prompt
from src.utils.time_utils import to_utc, local_to_utc

logger = logging.getLogger(__name__)

TimeSlot = Tuple[datetime, datetime]

_SYSTEM_PROMPT = """You are a time-slot extraction engine for a scheduling assistant.

Given an email body, extract ALL proposed time slots the sender is available.
Return a JSON array (and only JSON, no prose) in this format:
[
  {"start": "YYYY-MM-DD HH:MM", "end": "YYYY-MM-DD HH:MM", "timezone": "Asia/Kolkata"},
  ...
]

Rules:
- If only a start time is mentioned, assume a 1-hour slot.
- For vague terms: "morning" = 09:00–12:00, "afternoon" = 13:00–17:00, "evening" = 17:00–20:00.
- If no timezone is mentioned, use the timezone in the system context.
- If no year is mentioned, use the current year.
- If no specific date (just "Monday") use the NEXT occurrence of that weekday.
- Return [] if no time slots can be found.
- Return ONLY valid JSON, no markdown, no explanation.
"""


def parse_slots(email_body: str, reference_tz: str = None) -> List[TimeSlot]:
    """
    Extract time slots from an email body string.
    Returns list of (start_utc, end_utc) tuples.
    """
    tz = reference_tz or config.CALENDAR_TIMEZONE
    system = _SYSTEM_PROMPT + f"\nCurrent timezone context: {tz}."

    # ── LLM extraction (primary) ──────────────────────────────────────────────
    slots = _llm_extract(system, email_body, tz)
    if slots:
        logger.info(f"LLM extracted {len(slots)} slot(s).")
        return slots

    # ── dateparser + parsedatetime fallback ───────────────────────────────────
    logger.info("LLM extraction returned nothing — using dateparser fallback.")
    slots = _dateparser_extract(email_body, tz)
    logger.info(f"Dateparser extracted {len(slots)} slot(s).")
    return slots


def _llm_extract(system: str, body: str, tz: str) -> List[TimeSlot]:
    try:
        raw = prompt(system, body[:2000])
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not json_match:
            return []
        data = json.loads(json_match.group())
        slots = []
        for item in data:
            start_str = item.get("start", "")
            end_str = item.get("end", "")
            item_tz = item.get("timezone", tz)
            start = _parse_dt(start_str, item_tz)
            end = _parse_dt(end_str, item_tz)
            if start and end and end > start:
                slots.append((to_utc(start, item_tz), to_utc(end, item_tz)))
            elif start:
                # default 1-hour slot
                slots.append((to_utc(start, item_tz), to_utc(start + timedelta(hours=1), item_tz)))
        return slots
    except Exception as e:
        logger.warning(f"LLM slot extraction failed: {e}")
        return []


def _parse_dt(value: str, tz_name: str) -> Optional[datetime]:
    """Parse a datetime string into a naive datetime."""
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
        return dt
    except ValueError:
        pass
    parsed = dateparser.parse(value, settings={"TIMEZONE": tz_name, "RETURN_AS_TIMEZONE_AWARE": False})
    return parsed


def _dateparser_extract(body: str, tz: str) -> List[TimeSlot]:
    """
    Fallback: use parsedatetime to find date-like phrases and build 1-hour slots.
    """
    cal = parsedatetime.Calendar()
    now = datetime.now()

    # Find candidate date strings using a loose regex
    candidates = re.findall(
        r"(?:(?:next|this)?\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"|(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        r"|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"
        r"|\b(?:tomorrow|today)\b)"
        r"[\w\s:@,]*(?:\d{1,2}(?::\d{2})?\s*(?:am|pm))?",
        body,
        re.IGNORECASE,
    )

    slots: List[TimeSlot] = []
    for phrase in candidates:
        try:
            result, flag = cal.parseDT(phrase, sourceTime=now)
            if flag in (1, 2, 3):  # date, time, or datetime parsed
                start_naive = result
                end_naive = start_naive + timedelta(hours=1)
                slots.append((local_to_utc(start_naive, tz), local_to_utc(end_naive, tz)))
        except Exception:
            continue

    # Deduplicate
    seen = set()
    unique = []
    for s in slots:
        key = (s[0].isoformat(), s[1].isoformat())
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique
