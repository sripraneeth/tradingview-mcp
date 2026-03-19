"""MCP tool definitions for real-time WebSocket data.

Provides realtime_levels, realtime_bars, and realtime_analysis tools
that use TradingView's WebSocket API for actual OHLCV bar data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from tradingview_mcp.core.services.ws_data_provider import get_provider


def _format_symbol(symbol: str, exchange: str) -> str:
    """Format symbol with exchange prefix."""
    sym = (symbol or "").strip().upper()
    ex = (exchange or "").strip().upper()
    if ":" in sym:
        return sym
    return f"{ex}:{sym}"


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Compute RSI from a list of close prices."""
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 3)


def _compute_sma(values: List[float], period: int) -> Optional[float]:
    """Compute Simple Moving Average."""
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 4)


def _compute_ema(values: List[float], period: int) -> Optional[float]:
    """Compute Exponential Moving Average."""
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for val in values[period:]:
        ema = (val - ema) * multiplier + ema
    return round(ema, 4)


def _compute_macd(
    closes: List[float],
) -> Optional[Dict[str, Optional[float]]]:
    """Compute MACD (12, 26, 9)."""
    if len(closes) < 26:
        return None

    ema12 = _compute_ema(closes, 12)
    ema26 = _compute_ema(closes, 26)
    if ema12 is None or ema26 is None:
        return None

    macd_line = round(ema12 - ema26, 4)
    # Signal line needs MACD history; simplified: just return current MACD
    return {"macd": macd_line, "signal": None, "histogram": None}


def _compute_bollinger(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> Optional[Dict[str, Optional[float]]]:
    """Compute Bollinger Bands."""
    if len(closes) < period:
        return None
    window = closes[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std = variance**0.5
    return {
        "upper": round(sma + std_dev * std, 4),
        "middle": round(sma, 4),
        "lower": round(sma - std_dev * std, 4),
        "width": round((2 * std_dev * std) / sma, 6) if sma else None,
    }


def _build_analysis(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build technical analysis from raw OHLCV bars."""
    closes = [float(b["close"]) for b in bars]

    return {
        "rsi": _compute_rsi(closes),
        "sma_20": _compute_sma(closes, 20),
        "ema_20": _compute_ema(closes, 20),
        "ema_50": _compute_ema(closes, 50),
        "ema_200": _compute_ema(closes, 200),
        "macd": _compute_macd(closes),
        "bollinger": _compute_bollinger(closes),
        "bar_count": len(bars),
    }


def register_realtime_tools(mcp: Any) -> None:
    """Register realtime WebSocket-based tools on a FastMCP instance."""

    @mcp.tool()
    def realtime_bars(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        count: int = 100,
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return raw OHLCV bar data from TradingView WebSocket.

        Parameters:
            symbol: Trading symbol (e.g., "ES1!", "NQ1!", "BTCUSDT")
            exchange: Exchange name (default CME_MINI)
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            count: Number of bars (default 100, max 5000)
            tv_session_id: Optional TradingView session cookie.
                If omitted, anonymous mode is used.
        """
        count_clamped = max(1, min(int(count), 5000))
        provider = get_provider()
        result = provider.get_bars(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            count=count_clamped,
            session_id=tv_session_id,
        )

        if isinstance(result, dict) and "error" in result:
            return result

        return {
            "symbol": _format_symbol(symbol, exchange),
            "exchange": exchange.strip().lower(),
            "timeframe": timeframe,
            "bar_count": len(result),
            "bars": result,
        }

    @mcp.tool()
    def realtime_levels(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "30m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return session-based support/resistance levels computed from real OHLCV bars.

        Includes prior day H/L/C, opening range, session VWAP, and intraday pivots
        (Classic, Fibonacci, Camarilla). These match the tight ranges visible on
        TradingView charts, unlike screener-based daily pivots.

        Parameters:
            symbol: Trading symbol (e.g., "ES1!", "NQ1!")
            exchange: Exchange name (default CME_MINI)
            timeframe: Timeframe for bar data (default 30m)
            tv_session_id: Optional TradingView session cookie.
                If omitted, anonymous mode is used.
        """
        provider = get_provider()
        return provider.get_session_levels(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            session_id=tv_session_id,
        )

    @mcp.tool()
    def realtime_analysis(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return technical analysis computed from real OHLCV bars via WebSocket.

        Computes RSI, MACD, Bollinger Bands, and moving averages from actual
        bar data rather than screener snapshots.

        Parameters:
            symbol: Trading symbol (e.g., "ES1!", "NQ1!", "BTCUSDT")
            exchange: Exchange name (default CME_MINI)
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            tv_session_id: Optional TradingView session cookie.
                If omitted, anonymous mode is used.
        """
        provider = get_provider()
        bars_result = provider.get_bars(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            count=300,  # enough for EMA200 + buffer
            session_id=tv_session_id,
        )

        if isinstance(bars_result, dict) and "error" in bars_result:
            return bars_result

        if not isinstance(bars_result, list) or len(bars_result) == 0:
            return {"error": f"No bar data received for {_format_symbol(symbol, exchange)}"}

        analysis = _build_analysis(bars_result)

        latest = bars_result[-1]
        return {
            "symbol": _format_symbol(symbol, exchange),
            "exchange": exchange.strip().lower(),
            "timeframe": timeframe,
            "analysis": analysis,
            "latest_bar": latest,
        }
