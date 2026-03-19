"""
Gmail OAuth 2.0 authentication.
Handles first-time browser login and automatic token refresh.

Scopes requested:
  - https://mail.google.com/           (full Gmail access for IMAP labels)
  - https://www.googleapis.com/auth/calendar  (create Google Calendar events)
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
]

TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"


def get_credentials() -> Credentials:
    """
    Return valid Google OAuth2 credentials.
    - Loads from token.json if available and refreshes if expired.
    - Runs interactive browser login on first use.
    """
    creds: Credentials | None = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None  # force re-auth

        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console "
                    "(APIs & Services → Credentials → OAuth 2.0 Client IDs → Desktop App)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds
