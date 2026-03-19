"""High-level data provider built on the TradingView WebSocket client.

Manages connection lifecycle, caching, and provides clean interfaces
for tools to request bars, quotes, and computed levels.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from tradingview_mcp.core.services.tv_auth import extract_auth_token, get_session_id
from tradingview_mcp.core.services.ws_client import TVWebSocketClient, TV_TIMEFRAME_MAP
from tradingview_mcp.core.services.level_calc import compute_session_levels

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30
_RETRY_DELAY_SECONDS = 5


def _format_ws_symbol(symbol: str, exchange: str) -> str:
    """Format symbol for WebSocket requests: EXCHANGE:SYMBOL."""
    sym = (symbol or "").strip().upper()
    ex = (exchange or "").strip().upper()
    if ":" in sym:
        return sym
    return f"{ex}:{sym}"


class WSDataProvider:
    """High-level interface for fetching real-time data via TradingView WebSocket.

    Manages a single WebSocket connection with lazy initialization,
    automatic reconnection, and a 30-second bar cache.
    """

    def __init__(self) -> None:
        self._client: TVWebSocketClient = TVWebSocketClient()
        self._cache: Dict[Tuple[str, str], Tuple[float, Any]] = {}

    def _ensure_connected(self, session_id: str) -> Optional[str]:
        """Ensure WebSocket is connected. Returns error string or None on success."""
        if self._client.connected:
            return None

        sid = get_session_id(session_id)
        auth_token = "unauthorized_user_token"
        if sid:
            extracted = extract_auth_token(sid)
            if extracted:
                auth_token = extracted
            else:
                logger.warning(
                    "Could not extract TradingView auth token from provided session. "
                    "Falling back to anonymous mode."
                )
        else:
            logger.info("No TradingView session provided. Using anonymous mode.")

        try:
            self._client.connect(auth_token=auth_token)
        except Exception as exc:
            logger.warning("WebSocket connection failed: %s", exc)
            return f"WebSocket connection failed: {exc}"

        return None

    def _get_cached(self, cache_key: Tuple[str, str]) -> Optional[Any]:
        """Return cached data if still valid, else None."""
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > _CACHE_TTL_SECONDS:
            return None
        return data

    def get_bars(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        count: int = 100,
        session_id: str = "",
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """Fetch OHLCV bars. Returns list of bar dicts or error dict."""
        full_symbol = _format_ws_symbol(symbol, exchange)
        tf_tv = TV_TIMEFRAME_MAP.get(timeframe, timeframe)
        cache_key = (full_symbol, tf_tv)

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        err = self._ensure_connected(session_id)
        if err:
            return {"error": err}

        for attempt in range(2):
            try:
                bars = self._client.get_series(
                    full_symbol=full_symbol,
                    timeframe_tv=tf_tv,
                    count=count,
                )
                self._cache[cache_key] = (time.monotonic(), bars)
                return bars
            except (ConnectionError, TimeoutError) as exc:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, full_symbol, exc)
                if attempt == 0:
                    # Reconnect and retry once
                    self._client.disconnect()
                    err = self._ensure_connected(session_id)
                    if err:
                        return {"error": err}
                    time.sleep(_RETRY_DELAY_SECONDS)
                else:
                    return {"error": f"Failed to fetch bars for {full_symbol}: {exc}"}
            except Exception as exc:
                return {"error": f"Unexpected error fetching bars for {full_symbol}: {exc}"}

        return {"error": f"Failed to fetch bars for {full_symbol}"}

    def get_session_levels(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        session_id: str = "",
    ) -> Union[Dict[str, Any], Dict[str, str]]:
        """Compute intraday session levels from real bar data.

        Returns level dict or error dict.
        """
        bars_result = self.get_bars(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            count=200,  # ~2 trading days of 30m bars
            session_id=session_id,
        )

        if isinstance(bars_result, dict) and "error" in bars_result:
            return bars_result

        if not isinstance(bars_result, list) or len(bars_result) == 0:
            return {"error": f"No bar data received for {_format_ws_symbol(symbol, exchange)}"}

        levels = compute_session_levels(bars_result)
        if levels is None:
            return {
                "error": "Insufficient data to compute session levels. Need at least 2 trading sessions."
            }

        levels["symbol"] = _format_ws_symbol(symbol, exchange)
        levels["bar_count"] = len(bars_result)
        return levels

    def disconnect(self) -> None:
        """Disconnect the WebSocket client."""
        self._client.disconnect()
        self._cache.clear()


# Module-level singleton, lazily used by tools
_provider: Optional[WSDataProvider] = None


def get_provider() -> WSDataProvider:
    """Get or create the singleton WSDataProvider instance."""
    global _provider
    if _provider is None:
        _provider = WSDataProvider()
    return _provider
