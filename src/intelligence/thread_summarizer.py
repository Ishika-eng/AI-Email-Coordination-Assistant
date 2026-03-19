"""
Thread Summarizer.

Reads the full ordered message list of a Gmail thread and uses the LLM
to produce a concise, factual status update — returned as plain text
ready to embed in an email reply.
"""
import logging
from typing import List, Dict

from src.llm.llm_client import prompt

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a professional executive assistant.
Read the email thread below (oldest message first) and write a concise status update (3-5 sentences).
Cover: what was discussed, what decisions were made, and the current status.
Be factual and professional. Do not address anyone by name. Do not start with "I".
"""


def summarize_thread(messages: List[Dict[str, str]]) -> str:
    """
    Summarize an email thread into a 3-5 sentence status update.

    Args:
        messages: List of {"sender": str, "body": str} dicts, oldest first.

    Returns:
        Plain-text summary string.
    """
    if not messages:
        return "No messages found in this thread to summarize."

    thread_text = "\n\n---\n\n".join(
        f"From: {m.get('sender', 'Unknown')}\n{m.get('body', '').strip()}"
        for m in messages
    )

    # Limit context to avoid LLM token limits
    if len(thread_text) > 6000:
        thread_text = thread_text[-6000:]
        thread_text = "[earlier messages truncated]\n\n" + thread_text

    try:
        summary = prompt(_SYSTEM_PROMPT, thread_text)
        logger.info("Thread summarized successfully.")
        return summary.strip()
    except Exception as e:
        logger.error(f"Thread summarization failed: {e}")
        return "Unable to generate summary at this time. Please review the thread directly."
