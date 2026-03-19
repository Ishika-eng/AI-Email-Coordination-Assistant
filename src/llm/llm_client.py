"""
LLM Gateway — Ollama (local) first, Groq free tier as fallback.

All AI components call this single interface:
    from src.llm.llm_client import prompt
    result = prompt(system="...", user="...")

Both models used are completely FREE:
  - Ollama + llama3: local, no API key, no cost ever
  - Groq llama3-8b-8192: free tier, no credit card required
"""
import logging
import os

import requests

import config

logger = logging.getLogger(__name__)


def prompt(system: str, user: str, temperature: float = 0.3) -> str:
    """
    Send a prompt to the LLM and return the response string.
    Tries Ollama first (local), falls back to Groq API (free cloud).
    """
    # ── Primary: Ollama (local, completely free) ──────────────────────────────
    result = _try_ollama(system, user, temperature)
    if result:
        return result

    logger.info("Ollama unavailable — falling back to Groq API (free tier).")

    # ── Fallback: Groq free-tier API ──────────────────────────────────────────
    result = _try_groq(system, user, temperature)
    if result:
        return result

    raise RuntimeError(
        "Both Ollama and Groq are unavailable. "
        "Start Ollama (ollama serve) or set GROQ_API_KEY in .env"
    )


def _try_ollama(system: str, user: str, temperature: float) -> str | None:
    """Call local Ollama API. Returns None if unavailable."""
    try:
        payload = {
            "model": config.OLLAMA_MODEL,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {"temperature": temperature},
        }
        resp = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            text = resp.json().get("response", "").strip()
            logger.debug(f"Ollama responded ({len(text)} chars)")
            return text
        logger.warning(f"Ollama HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.ConnectionError:
        logger.debug("Ollama not running (connection refused).")
    except Exception as e:
        logger.warning(f"Ollama error: {e}")
    return None


def _try_groq(system: str, user: str, temperature: float) -> str | None:
    """Call Groq API (free tier). Returns None if unavailable or key missing."""
    api_key = config.GROQ_API_KEY
    if not api_key:
        logger.warning("GROQ_API_KEY not set — cannot use Groq fallback.")
        return None
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        text = response.choices[0].message.content.strip()
        logger.debug(f"Groq responded ({len(text)} chars)")
        return text
    except Exception as e:
        logger.error(f"Groq API error: {e}")
    return None
