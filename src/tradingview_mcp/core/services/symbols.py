from __future__ import annotations

from ..utils.validators import EXCHANGE_SCREENER, is_crypto_exchange, sanitize_exchange
from .coinlist import load_symbols


def format_symbol(exchange: str, symbol: str) -> str:
    """Format a symbol into TradingView ticker form: EXCHANGE:SYMBOL.

    Rules:
    - If symbol already contains ':', return as-is.
    - For crypto exchanges, append USDT when no common USD quote suffix exists.
    - Prefix with uppercased/sanitized exchange code.
    """
    if ":" in symbol:
        return symbol

    ex = sanitize_exchange(exchange)
    sym = (symbol or "").strip().upper()

    if is_crypto_exchange(ex) and not sym.endswith(("USDT", "USDC", "USD")):
        sym = f"{sym}USDT"

    return f"{ex.upper()}:{sym}"


def get_screener_for_exchange(exchange: str) -> str:
    """Return screener market for an exchange with sanitize + fallback behavior."""
    ex = sanitize_exchange(exchange, default="all")
    return EXCHANGE_SCREENER.get(ex, "crypto")
