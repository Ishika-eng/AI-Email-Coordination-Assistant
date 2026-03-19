"""
AI Email Coordination Assistant — Entry Point.

Starts two concurrent services:
  1. APScheduler polling loop  — reads inbox and runs the orchestrator every N seconds
  2. FastAPI dashboard server  — config UI, logs, human override at http://localhost:8000
"""
import logging
import threading
import os

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from src.agent.orchestrator import run_once
from src.api.routes import router
from src.scheduling.state_store import init_db

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Validate required config ───────────────────────────────────────────────────
_required = {
    "ASSISTANT_EMAIL": config.ASSISTANT_EMAIL,
    "GMAIL_APP_PASSWORD": config.GMAIL_APP_PASSWORD,
}
for name, val in _required.items():
    if not val:
        raise EnvironmentError(
            f"Missing required environment variable: {name}\n"
            "Copy .env.example → .env and fill in your credentials."
        )

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Email Coordination Assistant",
    description="Autonomous AI agent that schedules meetings and answers thread updates via email.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

# ── Startup event ──────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    logger.info("✅ Database initialised.")

    # Start the email polling scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_once,
        trigger="interval",
        seconds=config.POLL_INTERVAL_SECONDS,
        id="email_poll",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"🤖 AI Email Assistant started. "
        f"Polling every {config.POLL_INTERVAL_SECONDS}s. "
        f"Dashboard → http://localhost:{config.DASHBOARD_PORT}"
    )

    # Run immediately on startup (don't wait for first interval)
    threading.Thread(target=run_once, daemon=True).start()


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.DASHBOARD_PORT,
        reload=False,
        log_level="info",
    )
