"""
Email sender via Gmail SMTP.

Sends replies with proper threading headers (In-Reply-To, References)
and automatically appends the mandatory AI disclaimer to every message.
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import config

logger = logging.getLogger(__name__)


def send_reply(
    to: str,
    subject: str,
    body: str,
    reply_to_msg_id: Optional[str] = None,
    cc: Optional[List[str]] = None,
):
    """
    Send an email reply via Gmail SMTP SSL.

    Args:
        to: Recipient email address.
        subject: Email subject (auto-prefixed with 'Re:' if needed).
        body: Plain-text body content.
        reply_to_msg_id: The original Message-ID for threading (In-Reply-To header).
        cc: Optional list of CC addresses.
    """
    full_body = body.strip() + config.AI_DISCLAIMER

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["From"] = f"{config.ASSISTANT_NAME} <{config.ASSISTANT_EMAIL}>"
    msg["To"] = to

    if cc:
        msg["CC"] = ", ".join(cc)
    if reply_to_msg_id:
        msg["In-Reply-To"] = reply_to_msg_id
        msg["References"] = reply_to_msg_id

    # Plain text part
    msg.attach(MIMEText(full_body, "plain"))

    all_recipients = [to] + (cc or [])

    try:
        with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as smtp:
            smtp.login(config.ASSISTANT_EMAIL, config.GMAIL_APP_PASSWORD)
            smtp.sendmail(config.ASSISTANT_EMAIL, all_recipients, msg.as_string())
        logger.info(f"Email sent to {to} | Subject: {msg['Subject']}")
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send email to {to}: {e}")
        raise


def send_initial_request(
    to_list: List[str],
    subject: str,
    body: str,
):
    """
    Send a fresh scheduling request email (not a reply) to multiple people.
    Used when the assistant needs to ask participants for availability.
    """
    full_body = body.strip() + config.AI_DISCLAIMER
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{config.ASSISTANT_NAME} <{config.ASSISTANT_EMAIL}>"
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(full_body, "plain"))

    try:
        with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as smtp:
            smtp.login(config.ASSISTANT_EMAIL, config.GMAIL_APP_PASSWORD)
            smtp.sendmail(config.ASSISTANT_EMAIL, to_list, msg.as_string())
        logger.info(f"Availability request sent to {to_list}")
    except smtplib.SMTPException as e:
        logger.error(f"Failed to send availability request: {e}")
        raise
