"""
Main Orchestrator.

The heart of the AI Email Coordination Assistant.
Runs on a schedule (via APScheduler), reads unseen emails,
classifies their intent, and routes to the appropriate pipeline.

Pipeline A — Scheduling:
  parse slots → store state → check overlap → create event → send reply

Pipeline B — Thread Update:
  fetch thread → summarize → compose reply → send
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import config
from src.email_client.imap_reader import fetch_unseen_emails, EmailMessage
from src.email_client.thread_fetcher import (
    fetch_thread,
    get_gmail_thread_id_for_message_id,
)
from src.email_client.sender import send_reply
from src.agent.intent_classifier import classify
from src.scheduling.availability_parser import parse_slots
from src.scheduling.overlap_resolver import find_overlaps, describe_no_overlap
from src.scheduling.calendar_manager import create_event
from src.scheduling.state_store import (
    init_db,
    get_thread,
    upsert_thread,
    record_meeting,
    log_activity,
)
from src.intelligence.thread_summarizer import summarize_thread
from src.intelligence.reply_composer import (
    compose_confirmation_reply,
    compose_collecting_reply,
    compose_no_overlap_reply,
    compose_update_reply,
    compose_availability_request,
)

logger = logging.getLogger(__name__)


def run_once():
    """
    Single polling cycle:
      1. Fetch unseen emails
      2. Resolve their Gmail thread ID
      3. Classify intent
      4. Route to scheduling or update pipeline
    """
    init_db()
    log_activity("🔍 Polling inbox for new emails...")

    try:
        emails = fetch_unseen_emails()
    except Exception as e:
        log_activity(f"❌ Failed to fetch emails: {e}", level="ERROR")
        return

    if not emails:
        log_activity("📭 No new emails.")
        return

    log_activity(f"📬 Found {len(emails)} new email(s).")

    for em in emails:
        try:
            _process_email(em)
        except Exception as e:
            log_activity(f"❌ Error processing email from {em.sender_email}: {e}", level="ERROR")
            logger.exception(f"Unhandled error for email {em.uid}")


def _process_email(em: EmailMessage):
    # Skip our own outgoing emails
    if em.sender_email.lower() == config.ASSISTANT_EMAIL.lower():
        logger.debug(f"Skipping our own email: {em.subject}")
        return

    log_activity(
        f"📧 Processing: '{em.subject}' from {em.sender_email}",
        thread_id=em.message_id,
    )

    # Resolve Gmail thread ID from RFC 822 Message-ID
    gmail_thread_id = get_gmail_thread_id_for_message_id(em.message_id) or em.message_id
    em.gmail_thread_id = gmail_thread_id

    intent = classify(em.subject, em.body)
    log_activity(f"🔎 Intent: {intent}", thread_id=gmail_thread_id)

    if intent == "SCHEDULING_REQUEST":
        _handle_scheduling(em, gmail_thread_id)
    elif intent == "THREAD_UPDATE_REQUEST":
        _handle_update(em, gmail_thread_id)
    else:
        log_activity(f"⏭️  Skipping (intent=OTHER): {em.subject}", thread_id=gmail_thread_id)


# ── Pipeline A: Scheduling ─────────────────────────────────────────────────────

def _handle_scheduling(em: EmailMessage, thread_id: str):
    # Parse slots from this email
    new_slots = parse_slots(em.body, config.CALENDAR_TIMEZONE)
    log_activity(
        f"🕐 Parsed {len(new_slots)} slot(s) from {em.sender_email}",
        thread_id=thread_id,
    )

    # Load existing thread state or create new
    state = get_thread(thread_id)
    if state:
        all_slots: Dict = state["slots"]
        participants: List[str] = state["participants"]
        if em.sender_email not in participants:
            participants.append(em.sender_email)
    else:
        all_slots = {}
        participants = [em.sender_email]
        # Also collect CC'd participants
        for cc_email in em.cc:
            if cc_email and cc_email.lower() != config.ASSISTANT_EMAIL.lower():
                if cc_email not in participants:
                    participants.append(cc_email)

    if new_slots:
        all_slots[em.sender_email] = new_slots

    # Check if we have enough participants and slots
    respondents = [p for p in participants if p in all_slots]
    all_responded = len(respondents) >= config.MIN_PARTICIPANTS and len(respondents) == len(participants)

    if all_responded and all_slots:
        overlaps = find_overlaps(all_slots)
        if overlaps:
            _schedule_meeting(em, thread_id, participants, all_slots, overlaps)
            return
        else:
            # No overlap — ask for more availability
            reason = describe_no_overlap(all_slots)
            upsert_thread(thread_id, participants, all_slots, "no_overlap", em.subject)
            reply = compose_no_overlap_reply(reason)
            send_reply(em.sender_email, em.subject, reply, em.message_id, cc=em.cc)
            log_activity("❌ No overlap found — asked for more availability.", thread_id=thread_id)
            return

    # Still collecting
    upsert_thread(thread_id, participants, all_slots, "collecting", em.subject)

    if not new_slots:
        # This person didn't share slots — ask them
        request_body = compose_availability_request(participants, em.subject)
        send_reply(em.sender_email, em.subject, request_body, em.message_id)
        log_activity(f"📤 Asked {em.sender_email} for availability.", thread_id=thread_id)
    else:
        missing = [p for p in participants if p not in all_slots]
        reply = compose_collecting_reply(missing)
        send_reply(em.sender_email, em.subject, reply, em.message_id)
        log_activity(
            f"📤 Collecting reply sent (waiting for {len(missing)} more participants).",
            thread_id=thread_id,
        )


def _schedule_meeting(
    em: EmailMessage,
    thread_id: str,
    participants: List[str],
    all_slots: Dict,
    overlaps: List[Tuple[datetime, datetime]],
):
    best_start, best_end = overlaps[0]
    title = f"Meeting: {em.subject}"

    log_activity(
        f"📅 Creating calendar event: {title} at {best_start.isoformat()}",
        thread_id=thread_id,
    )

    cal_link, meet_link = create_event(
        title=title,
        start=best_start,
        end=best_end,
        attendees=participants,
        description=f"Scheduled via AI Email Assistant based on availability coordination for: {em.subject}",
    )

    upsert_thread(thread_id, participants, all_slots, "scheduled", em.subject)
    record_meeting(thread_id, title, best_start, best_end, participants, cal_link or "", meet_link or "")

    reply = compose_confirmation_reply(
        start=best_start,
        end=best_end,
        cal_link=cal_link,
        meet_link=meet_link,
        attendees=participants,
    )
    send_reply(em.sender_email, em.subject, reply, em.message_id, cc=em.cc)
    log_activity(f"✅ Meeting scheduled & confirmed! Event: {cal_link}", thread_id=thread_id)


# ── Pipeline B: Thread Update ──────────────────────────────────────────────────

def _handle_update(em: EmailMessage, thread_id: str):
    log_activity(f"📖 Fetching thread for update summary...", thread_id=thread_id)
    messages = fetch_thread(thread_id)

    if not messages:
        # Fallback: summarize just this email's body
        messages = [{"sender": em.sender_email, "body": em.body}]

    summary = summarize_thread(messages)
    reply_body = compose_update_reply(summary, em.subject)
    send_reply(em.sender_email, em.subject, reply_body, em.message_id)
    log_activity(f"📤 Thread update summary sent to {em.sender_email}.", thread_id=thread_id)
