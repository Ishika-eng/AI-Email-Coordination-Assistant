"""
SQLite State Store.

Tracks the lifecycle of each multi-turn scheduling thread so the orchestrator
can resume coordination after collecting availability from multiple participants.

Thread lifecycle:
  collecting  → waiting for more participant availability responses
  ready       → all participants responded, ready to schedule
  scheduled   → calendar event created
  failed      → could not find overlap after multiple attempts
  ignored     → intent was OTHER or already handled
"""
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = "scheduling_state.db"


def init_db():
    """Create tables if they don't exist."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                thread_id    TEXT PRIMARY KEY,
                participants TEXT NOT NULL DEFAULT '[]',
                slots        TEXT NOT NULL DEFAULT '{}',
                status       TEXT NOT NULL DEFAULT 'collecting',
                subject      TEXT DEFAULT '',
                updated_at   TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id    TEXT NOT NULL,
                title        TEXT,
                start_utc    TEXT,
                end_utc      TEXT,
                attendees    TEXT,
                cal_link     TEXT,
                meet_link    TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                level      TEXT DEFAULT 'INFO',
                message    TEXT,
                thread_id  TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


def _conn():
    return sqlite3.connect(DB_PATH)


# ── Thread state ───────────────────────────────────────────────────────────────

def get_thread(thread_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT thread_id, participants, slots, status, subject FROM threads WHERE thread_id=?",
            (thread_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "thread_id": row[0],
        "participants": json.loads(row[1]),
        "slots": {k: _deserialize_slots(v) for k, v in json.loads(row[2]).items()},
        "status": row[3],
        "subject": row[4],
    }


def upsert_thread(
    thread_id: str,
    participants: List[str],
    slots: Dict[str, List[Tuple]],
    status: str,
    subject: str = "",
):
    serialized_slots = {k: _serialize_slots(v) for k, v in slots.items()}
    with _conn() as conn:
        conn.execute("""
            INSERT INTO threads (thread_id, participants, slots, status, subject, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(thread_id) DO UPDATE SET
                participants = excluded.participants,
                slots        = excluded.slots,
                status       = excluded.status,
                subject      = excluded.subject,
                updated_at   = excluded.updated_at
        """, (
            thread_id,
            json.dumps(participants),
            json.dumps(serialized_slots),
            status,
            subject,
        ))
        conn.commit()


def all_threads() -> List[Dict[str, Any]]:
    """Return all threads for the dashboard."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT thread_id, participants, status, subject, updated_at FROM threads ORDER BY updated_at DESC"
        ).fetchall()
    return [
        {"thread_id": r[0], "participants": json.loads(r[1]), "status": r[2], "subject": r[3], "updated_at": r[4]}
        for r in rows
    ]


# ── Meetings ──────────────────────────────────────────────────────────────────

def record_meeting(
    thread_id: str,
    title: str,
    start_utc: datetime,
    end_utc: datetime,
    attendees: List[str],
    cal_link: str,
    meet_link: str,
):
    with _conn() as conn:
        conn.execute("""
            INSERT INTO meetings (thread_id, title, start_utc, end_utc, attendees, cal_link, meet_link)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id, title,
            start_utc.isoformat(), end_utc.isoformat(),
            json.dumps(attendees), cal_link or "", meet_link or ""
        ))
        conn.commit()


def all_meetings() -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, thread_id, title, start_utc, end_utc, attendees, cal_link, meet_link, created_at "
            "FROM meetings ORDER BY start_utc ASC"
        ).fetchall()
    return [
        {
            "id": r[0], "thread_id": r[1], "title": r[2],
            "start_utc": r[3], "end_utc": r[4],
            "attendees": json.loads(r[5]),
            "cal_link": r[6], "meet_link": r[7], "created_at": r[8],
        }
        for r in rows
    ]


def cancel_meeting(meeting_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
        conn.commit()


# ── Activity log ──────────────────────────────────────────────────────────────

def log_activity(message: str, level: str = "INFO", thread_id: str = ""):
    logger.info(f"[{level}] {message}")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO activity_log (level, message, thread_id) VALUES (?, ?, ?)",
            (level, message, thread_id),
        )
        conn.commit()


def get_logs(limit: int = 100) -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, level, message, thread_id, created_at FROM activity_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"id": r[0], "level": r[1], "message": r[2], "thread_id": r[3], "created_at": r[4]}
        for r in rows
    ]


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _serialize_slots(slots: List[Tuple]) -> List:
    return [[s.isoformat() if isinstance(s, datetime) else str(s),
             e.isoformat() if isinstance(e, datetime) else str(e)]
            for s, e in slots]


def _deserialize_slots(raw: List) -> List[Tuple]:
    from datetime import datetime as dt
    result = []
    for pair in raw:
        try:
            s = dt.fromisoformat(pair[0])
            e = dt.fromisoformat(pair[1])
            result.append((s, e))
        except Exception:
            pass
    return result
