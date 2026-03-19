"""
Gmail Thread Fetcher.

Uses the Gmail API to retrieve the full ordered message list for a thread,
given a Gmail thread ID. This is the correct way to get thread context —
the IMAP Message-ID is different from Gmail's internal threadId.
"""
import base64
import logging
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from src.auth.credentials_manager import CredentialsManager

logger = logging.getLogger(__name__)


def get_gmail_thread_id_for_message_id(message_id: str) -> Optional[str]:
    """
    Search Gmail for a message with the given RFC 822 Message-ID header,
    and return its Gmail threadId.
    """
    try:
        creds = CredentialsManager.get()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        query = f"rfc822msgid:{message_id.strip('<>')}"
        result = service.users().messages().list(userId="me", q=query, maxResults=1).execute()
        messages = result.get("messages", [])
        if messages:
            return messages[0].get("threadId")
    except Exception as e:
        logger.warning(f"Could not resolve threadId for Message-ID {message_id}: {e}")
    return None


def fetch_thread(thread_id: str) -> List[Dict[str, str]]:
    """
    Fetch all messages in a Gmail thread, ordered oldest-first.
    Returns a list of dicts with 'sender' and 'body' keys.
    """
    if not thread_id:
        return []
    try:
        creds = CredentialsManager.get()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        thread = service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()

        messages = []
        for msg in thread.get("messages", []):
            payload = msg.get("payload", {})
            sender = _get_header(payload, "From")
            body = _extract_body(payload)
            messages.append({"sender": sender, "body": body})

        return messages

    except Exception as e:
        logger.error(f"Failed to fetch thread {thread_id}: {e}")
        return []


def _get_header(payload: dict, name: str) -> str:
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from Gmail API payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return ""
