"""
Central configuration for the AI Email Coordination Assistant.
All values are read from environment variables (set in .env).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Assistant identity ────────────────────────────────────────────────────────
ASSISTANT_EMAIL: str = os.getenv("ASSISTANT_EMAIL", "")
ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "AI Email Assistant")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")

# ── LLM ──────────────────────────────────────────────────────────────────────
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")

# ── Scheduling ────────────────────────────────────────────────────────────────
CALENDAR_TIMEZONE: str = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")
POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
MIN_PARTICIPANTS: int = int(os.getenv("MIN_PARTICIPANTS_TO_SCHEDULE", "2"))

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8000"))

# ── AI disclaimer appended to every outbound email ───────────────────────────
AI_DISCLAIMER = """

---
⚠️  This message was sent by an experimental AI email assistant ({name}).
    Please verify important information independently.
""".format(name=ASSISTANT_NAME)

# ── Gmail IMAP / SMTP ────────────────────────────────────────────────────────
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
PROCESSED_LABEL = "AI-Processed"
