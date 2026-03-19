"""
IMAP email reader.

Connects to Gmail via IMAP SSL, fetches UNSEEN messages from INBOX,
parses them into EmailMessage dataclasses, and applies the AI-Processed label
via Gmail API to prevent re-processing.
"""
import imaplib
import email as email_lib
from email.header import decode_header as _decode_header
from dataclasses import dataclass, field
from typing import List, Optional
import logging
import re

import config

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    uid: str
    sender: str
    sender_email: str          # bare email address extracted from "Name <email>"
    recipient: str
    subject: str
    body: str
    message_id: str            # RFC 822 Message-ID header (for In-Reply-To)
    gmail_thread_id: str       # Gmail API thread ID (set later by orchestrator)
    date: str
    cc: List[str] = field(default_factory=list)


def _decode_str(value: str) -> str:
    """Decode RFC 2047 encoded header strings."""
    if not value:
        return ""
    parts = _decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="ignore"))
        else:
            result.append(part)
    return "".join(result)


def _extract_email(raw: str) -> str:
    """Extract bare email from 'Name <email@domain.com>' format."""
    match = re.search(r"<([^>]+)>", raw or "")
    return match.group(1).strip() if match else (raw or "").strip()


def _get_body(msg) -> str:
    """Extract plain-text body from a MIME message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(
                        part.get_content_charset() or "utf-8", errors="ignore"
                    )
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(
                msg.get_content_charset() or "utf-8", errors="ignore"
            )
    return ""


def fetch_unseen_emails() -> List[EmailMessage]:
    """
    Connect to Gmail IMAP, fetch all UNSEEN emails, and return parsed messages.
    Does NOT mark them as seen here — the orchestrator handles labelling via Gmail API.
    """
    messages: List[EmailMessage] = []

    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_SERVER)
        mail.login(config.ASSISTANT_EMAIL, config.GMAIL_APP_PASSWORD)
        mail.select("inbox")

        _, uids_data = mail.search(None, "UNSEEN")
        uids = uids_data[0].split()

        if not uids:
            logger.debug("No unseen emails.")
            mail.logout()
            return []

        logger.info(f"Found {len(uids)} unseen email(s).")

        for uid in uids:
            try:
                _, data = mail.fetch(uid, "(RFC822)")
                raw_bytes = data[0][1]
                raw_msg = email_lib.message_from_bytes(raw_bytes)

                sender_raw = _decode_str(raw_msg.get("From", ""))
                cc_raw = raw_msg.get("CC", "") or ""
                cc_list = [_extract_email(a.strip()) for a in cc_raw.split(",") if a.strip()]

                msg = EmailMessage(
                    uid=uid.decode(),
                    sender=sender_raw,
                    sender_email=_extract_email(sender_raw),
                    recipient=_decode_str(raw_msg.get("To", "")),
                    subject=_decode_str(raw_msg.get("Subject", "(no subject)")),
                    body=_get_body(raw_msg),
                    message_id=raw_msg.get("Message-ID", ""),
                    gmail_thread_id="",   # filled in by orchestrator via Gmail API
                    date=raw_msg.get("Date", ""),
                    cc=cc_list,
                )
                messages.append(msg)
            except Exception as e:
                logger.warning(f"Failed to parse email UID {uid}: {e}")

        mail.logout()

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {e}")

    return messages
