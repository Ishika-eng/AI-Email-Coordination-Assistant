"""
Singleton credentials manager.
Provides authenticated Google credentials and assistant config to all modules.
"""
import os
from dotenv import load_dotenv
from src.auth.gmail_auth import get_credentials

load_dotenv()


class CredentialsManager:
    _creds = None

    @classmethod
    def get(cls):
        """Return valid (auto-refreshed) Google OAuth2 credentials."""
        if cls._creds is None or not cls._creds.valid:
            cls._creds = get_credentials()
        return cls._creds

    @classmethod
    def assistant_email(cls) -> str:
        return os.getenv("ASSISTANT_EMAIL", "")

    @classmethod
    def gmail_app_password(cls) -> str:
        return os.getenv("GMAIL_APP_PASSWORD", "")

    @classmethod
    def invalidate(cls):
        """Force re-authentication on next .get() call."""
        cls._creds = None
