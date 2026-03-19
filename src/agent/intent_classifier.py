"""
Intent Classifier.

Classifies incoming emails into one of three intents using LLM.
Falls back to keyword heuristics if LLM is unavailable.

Intent values:
  SCHEDULING_REQUEST    — email discusses availability / meeting coordination
  THREAD_UPDATE_REQUEST — email asks for status/update on a thread topic
  OTHER                 — no action needed
"""
import logging
import re

from src.llm.llm_client import prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an email intent classifier for an AI scheduling assistant.
Classify the given email into EXACTLY ONE of these labels:

  SCHEDULING_REQUEST     - The email mentions availability, meeting times, scheduling,
                           calendar coordination, or asks to set up / confirm a meeting.
  THREAD_UPDATE_REQUEST  - The email asks for a status update, progress report, or
                           latest information about an ongoing topic in this thread.
  OTHER                  - The email does not require scheduling or update actions.

Rules:
- Reply with ONLY the label (one of the three above). No explanation.
- If in doubt between SCHEDULING and UPDATE, choose SCHEDULING_REQUEST.
"""

# Keyword fallback sets
_SCHEDULING_KEYWORDS = {
    "schedule", "meeting", "availability", "available", "calendar",
    "time slot", "let's meet", "can we meet", "book", "appointment",
    "reschedule", "free on", "works for me", "how about", "next week",
    "this week", "monday", "tuesday", "wednesday", "thursday", "friday",
    "am", "pm", "morning", "afternoon", "evening",
}
_UPDATE_KEYWORDS = {
    "update", "status", "progress", "any news", "what's happening",
    "latest", "how is", "where are we", "follow up", "follow-up",
    "what happened", "results",
}


def classify(subject: str, body: str) -> str:
    """
    Return the intent label for an email.
    Primary: LLM (Ollama / Groq). Secondary: keyword heuristics.
    """
    combined = f"Subject: {subject}\n\nBody:\n{body[:1500]}"

    try:
        result = prompt(SYSTEM_PROMPT, combined).strip().upper()
        # Only accept valid labels
        for label in ("SCHEDULING_REQUEST", "THREAD_UPDATE_REQUEST", "OTHER"):
            if label in result:
                logger.info(f"LLM classified intent: {label}")
                return label
        logger.warning(f"LLM returned unexpected result: {result!r}. Using heuristic.")
    except Exception as e:
        logger.warning(f"LLM unavailable for classification: {e}. Using heuristics.")

    return _keyword_classify(subject, body)


def _keyword_classify(subject: str, body: str) -> str:
    """Simple keyword-based fallback classifier."""
    text = (subject + " " + body).lower()
    words = set(re.findall(r"\b\w+\b", text))

    s_score = len(words & _SCHEDULING_KEYWORDS)
    u_score = len(words & _UPDATE_KEYWORDS)

    if s_score == 0 and u_score == 0:
        return "OTHER"
    if s_score >= u_score:
        return "SCHEDULING_REQUEST"
    return "THREAD_UPDATE_REQUEST"
