"""Extract TradingView auth_token from session cookie.

The auth_token is required for WebSocket authentication. It is obtained by
loading tradingview.com with the user's sessionid cookie and scraping the
embedded JSON payload from the HTML response.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Dict, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_AUTH_TOKEN_CACHE: Dict[str, str] = {}

_AUTH_TOKEN_PATTERN = re.compile(r'"auth_token"\s*:\s*"([^"]+)"')

_TV_URL = "https://www.tradingview.com"
_HTTP_TIMEOUT = 10


def _parse_auth_token_from_html(html: str) -> Optional[str]:
    """Extract auth_token value from TradingView HTML page content."""
    if not html:
        return None
    match = _AUTH_TOKEN_PATTERN.search(html)
    return match.group(1) if match else None


def get_session_id(explicit: str = "") -> str:
    """Return the session ID to use: explicit param > env var > empty string."""
    if explicit:
        return explicit
    return os.environ.get("TV_SESSION_ID", "")


def extract_auth_token(session_id: str) -> Optional[str]:
    """Extract auth_token for a given TradingView session cookie.

    Returns the token string on success, or None on failure.
    Results are cached per session_id for the process lifetime.
    """
    if not session_id:
        return None

    cached = _AUTH_TOKEN_CACHE.get(session_id)
    if cached:
        return cached

    try:
        req = Request(
            _TV_URL,
            headers={
                "Cookie": f"sessionid={session_id}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Failed to fetch TradingView page for auth: %s", exc)
        return None

    token = _parse_auth_token_from_html(html)
    if token:
        _AUTH_TOKEN_CACHE[session_id] = token
    else:
        logger.warning("auth_token not found in TradingView HTML response")
    return token
