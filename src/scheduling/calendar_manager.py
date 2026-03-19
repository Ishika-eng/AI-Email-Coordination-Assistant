"""
Google Calendar Manager.

Creates Google Calendar events with Google Meet links and sends
calendar invites to all attendees via the Google Calendar API.
Includes duplicate-event detection to prevent double-bookings.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
from src.auth.credentials_manager import CredentialsManager

logger = logging.getLogger(__name__)


def create_event(
    title: str,
    start: datetime,
    end: datetime,
    attendees: List[str],
    description: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a Google Calendar event and send invites to all attendees.

    Args:
        title: Event title / summary.
        start: Start datetime (UTC-aware preferred).
        end: End datetime (UTC-aware preferred).
        attendees: List of email addresses to invite.
        description: Optional event description.

    Returns:
        (calendar_html_link, google_meet_link) — either may be None on error.
    """
    # Duplicate check
    if _event_exists(start, end, attendees):
        logger.warning("Duplicate event detected — skipping creation.")
        return None, None

    creds = CredentialsManager.get()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    tz = config.CALENDAR_TIMEZONE
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    event_body = {
        "summary": title,
        "description": description
        + f"\n\n⚠️ This meeting was scheduled by an experimental AI email assistant ({config.ASSISTANT_NAME}).",
        "start": {"dateTime": start_iso, "timeZone": tz},
        "end": {"dateTime": end_iso, "timeZone": tz},
        "attendees": [{"email": email} for email in attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": f"ai-assist-{int(start.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    try:
        result = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",  # sends Google Calendar invite emails
            )
            .execute()
        )
        cal_link = result.get("htmlLink")
        meet_link = result.get("hangoutLink")
        logger.info(f"Calendar event created: {cal_link}")
        return cal_link, meet_link
    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        return None, None


def _event_exists(start: datetime, end: datetime, attendees: List[str]) -> bool:
    """
    Check if an event already exists in the same time window with the same attendees.
    Simple deduplication: looks at ±5 min window around start time.
    """
    try:
        creds = CredentialsManager.get()
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        time_min = (start - timedelta(minutes=5)).isoformat()
        time_max = (start + timedelta(minutes=5)).isoformat()
        events = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
            )
            .execute()
            .get("items", [])
        )
        attendee_set = set(a.lower() for a in attendees)
        for ev in events:
            existing_attendees = {
                a.get("email", "").lower()
                for a in ev.get("attendees", [])
            }
            if attendee_set & existing_attendees:
                logger.warning(
                    f"Found existing overlapping event: {ev.get('summary')} at {ev.get('start')}"
                )
                return True
    except Exception as e:
        logger.warning(f"Duplicate check failed (proceeding): {e}")
    return False
