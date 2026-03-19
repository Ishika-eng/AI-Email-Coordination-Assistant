"""
Reply Composer.

Assembles professional email reply bodies for two scenarios:
  1. Scheduling outcomes (confirmed, collecting, no-overlap, clarification)
  2. Thread update summaries
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

import config
from src.llm.llm_client import prompt
from src.utils.time_utils import format_slot

logger = logging.getLogger(__name__)


def compose_confirmation_reply(
    start: datetime,
    end: datetime,
    cal_link: Optional[str],
    meet_link: Optional[str],
    attendees: List[str],
) -> str:
    """Reply when a meeting has been successfully scheduled."""
    slot_str = format_slot(start, end, config.CALENDAR_TIMEZONE)
    lines = [
        "Great news! I've found a common time slot and scheduled the meeting.",
        "",
        f"📅  {slot_str}",
    ]
    if meet_link:
        lines.append(f"🎥  Google Meet: {meet_link}")
    if cal_link:
        lines.append(f"🗓️  Calendar event: {cal_link}")
    lines += [
        "",
        "Calendar invites have been sent to all participants.",
        f"Attendees: {', '.join(attendees)}",
    ]
    return "\n".join(lines)


def compose_collecting_reply(participants_missing: List[str]) -> str:
    """Reply when still waiting for more participants' availability."""
    if participants_missing:
        waiting_on = ", ".join(participants_missing)
        body = (
            f"Thank you for sharing your availability.\n\n"
            f"I'm still waiting to hear from: {waiting_on}.\n"
            "I'll confirm the meeting time as soon as everyone has responded."
        )
    else:
        body = (
            "Thank you for sharing your availability.\n\n"
            "I'm still collecting responses from other participants. "
            "I'll confirm the meeting time once everyone has replied."
        )
    return body


def compose_no_overlap_reply(reason: str) -> str:
    """Reply when no common time slot could be found."""
    return (
        f"Thank you for your responses.\n\n"
        f"Unfortunately, I wasn't able to find a common time slot.\n"
        f"{reason}\n\n"
        "Could everyone please suggest a few additional time windows? "
        "I'll try again once I receive updated availability."
    )


def compose_update_reply(summary: str, original_subject: str) -> str:
    """
    Reply for a THREAD_UPDATE_REQUEST using the AI-generated thread summary.
    Uses the LLM to wrap the summary into a polished reply body.
    """
    system = (
        "You are a professional executive assistant writing a brief email reply. "
        "Given the status summary below, write 2-4 sentences as an email body. "
        "Do not add a subject line. Do not add a greeting or sign-off. "
        "Be concise and factual."
    )
    user = f"Status summary:\n{summary}\n\nOriginal subject: {original_subject}"
    try:
        body = prompt(system, user)
        return body.strip()
    except Exception as e:
        logger.warning(f"LLM reply composition failed: {e}. Using raw summary.")
        return f"Here is the latest status on '{original_subject}':\n\n{summary}"


def compose_availability_request(participants: List[str], subject: str) -> str:
    """
    Initial outreach asking participants for their availability.
    Sent when the orchestrator detects a scheduling request but no slots were provided.
    """
    return (
        f"Hello,\n\n"
        f"I'm coordinating a meeting regarding: '{subject}'.\n\n"
        "Could you please share your available time slots for the next week? "
        "For example: 'I'm free Monday 2-4 PM IST and Wednesday after 3 PM'.\n\n"
        "Once I hear from all participants, I'll find the best common time and "
        "send a calendar invite automatically."
    )
