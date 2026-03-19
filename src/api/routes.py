"""
FastAPI routes for the AI Email Assistant dashboard.
Provides config management, activity logs, meeting management, and human override.
"""
import json
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.scheduling.state_store import (
    all_meetings,
    all_threads,
    cancel_meeting,
    get_logs,
)

router = APIRouter()


# ── Models ─────────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    poll_interval_seconds: int = 60
    calendar_timezone: str = "Asia/Kolkata"
    assistant_name: str = "AI Email Assistant"
    min_participants: int = 2


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/meetings")
def get_meetings():
    return {"meetings": all_meetings()}


@router.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int):
    """Human override: cancel a scheduled meeting from the database."""
    cancel_meeting(meeting_id)
    return {"status": "cancelled", "id": meeting_id}


@router.get("/api/threads")
def get_threads():
    return {"threads": all_threads()}


@router.get("/api/logs")
def get_activity_logs(limit: int = 100):
    return {"logs": get_logs(limit)}


@router.get("/api/config")
def get_config():
    return {
        "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", 60)),
        "calendar_timezone": os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata"),
        "assistant_email": os.getenv("ASSISTANT_EMAIL", ""),
        "assistant_name": os.getenv("ASSISTANT_NAME", "AI Email Assistant"),
        "min_participants": int(os.getenv("MIN_PARTICIPANTS_TO_SCHEDULE", 2)),
        "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "groq_configured": bool(os.getenv("GROQ_API_KEY", "")),
    }


@router.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the single-page dashboard."""
    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>Dashboard coming soon</h1>", status_code=200)
