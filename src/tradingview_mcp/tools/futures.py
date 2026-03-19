from __future__ import annotations

from typing import Any, Dict, List

from tradingview_mcp.core.services.orb_predictor import calculate_orb_levels
from tradingview_mcp.core.services.symbols import get_screener_for_exchange
from tradingview_mcp.core.utils.validators import sanitize_exchange, sanitize_timeframe
from tradingview_mcp.tools.shared import TRADINGVIEW_TA_AVAILABLE, _safe_get_multiple_analysis, analyze_single, fetch_and_analyze


def _resolve_futures_screener(exchange: str) -> str:
    """Resolve screener market via shared resolver utility."""
    return get_screener_for_exchange(exchange)


def _normalize_futures_symbol(symbol: str, exchange: str) -> str:
    """Normalize symbol format for get_multiple_analysis requests."""
    symbol_clean = (symbol or "").strip().upper()
    if not symbol_clean:
        return ""

    if ":" in symbol_clean:
        return symbol_clean

    return f"{exchange.upper()}:{symbol_clean}"


def _structured_levels_from_pivots(pivot_levels: Dict[str, Any]) -> Dict[str, Any]:
    mapping = {
        "Classic": "classic",
        "Fibonacci": "fibonacci",
        "Camarilla": "camarilla",
    }
    structured: Dict[str, Any] = {}
    for output_name, source_key in mapping.items():
        source = pivot_levels.get(source_key) if isinstance(pivot_levels, dict) else None
        structured[output_name] = source if isinstance(source, dict) else {
            "middle": None,
            "support": {"S1": None, "S2": None, "S3": None},
            "resistance": {"R1": None, "R2": None, "R3": None},
        }
    return structured


def register_futures_tools(mcp: Any) -> None:
    """Register futures-prefixed tools on a FastMCP instance."""

    @mcp.tool()
    def futures_analysis(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Detailed futures analysis for a symbol.

        Symbol normalization does not append USDT and preserves "!" suffix.
        """
        exchange_sanitized = sanitize_exchange(exchange, "cme_mini")
        timeframe_sanitized = sanitize_timeframe(timeframe, "15m")

        # Ensure futures market routing is resolved for this exchange.
        _ = _resolve_futures_screener(exchange_sanitized)

        return analyze_single(
            symbol=symbol,
            exchange=exchange_sanitized,
            timeframe=timeframe_sanitized,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def futures_top_gainers(
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        limit: int = 25,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Top futures gainers by percentage change."""
        exchange_sanitized = sanitize_exchange(exchange, "cme_mini")
        timeframe_sanitized = sanitize_timeframe(timeframe, "15m")
        limit_sanitized = max(1, min(int(limit), 50))

        _ = _resolve_futures_screener(exchange_sanitized)

        return fetch_and_analyze(
            exchange=exchange_sanitized,
            timeframe=timeframe_sanitized,
            symbols=None,
            limit=limit_sanitized,
            filter_fn=None,
            sort_key="change",
            sort_reverse=True,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def futures_top_losers(
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        limit: int = 25,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Top futures losers by percentage change."""
        exchange_sanitized = sanitize_exchange(exchange, "cme_mini")
        timeframe_sanitized = sanitize_timeframe(timeframe, "15m")
        limit_sanitized = max(1, min(int(limit), 50))

        _ = _resolve_futures_screener(exchange_sanitized)

        return fetch_and_analyze(
            exchange=exchange_sanitized,
            timeframe=timeframe_sanitized,
            symbols=None,
            limit=limit_sanitized,
            filter_fn=None,
            sort_key="change",
            sort_reverse=False,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def futures_volume_breakout(
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        volume_multiplier: float = 2.0,
        price_change_min: float = 1.0,
        limit: int = 25,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Futures scan for volume-backed price breakouts."""
        exchange_sanitized = sanitize_exchange(exchange, "cme_mini")
        timeframe_sanitized = sanitize_timeframe(timeframe, "15m")
        limit_sanitized = max(1, min(int(limit), 50))
        volume_threshold = max(1.0, float(volume_multiplier))
        price_threshold = max(0.0, float(price_change_min))

        _ = _resolve_futures_screener(exchange_sanitized)

        return fetch_and_analyze(
            exchange=exchange_sanitized,
            timeframe=timeframe_sanitized,
            symbols=None,
            limit=limit_sanitized,
            filter_fn=lambda row: (
                float(row.get("volume") or 0) >= volume_threshold
                and abs(float(row.get("change") or 0)) >= price_threshold
            ),
            sort_key=lambda row: (
                float(row.get("volume") or 0),
                abs(float(row.get("change") or 0)),
            ),
            sort_reverse=True,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def futures_levels(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return pivot/support/resistance levels for a futures symbol."""
        exchange_sanitized = sanitize_exchange(exchange, "cme_mini")
        timeframe_sanitized = sanitize_timeframe(timeframe, "15m")

        _ = _resolve_futures_screener(exchange_sanitized)

        analysis = analyze_single(
            symbol=symbol,
            exchange=exchange_sanitized,
            timeframe=timeframe_sanitized,
            tv_session_id=tv_session_id,
        )
        if "error" in analysis:
            return analysis

        metrics = analysis.get("metrics") if isinstance(analysis, dict) else None
        pivot_levels = metrics.get("pivot_levels") if isinstance(metrics, dict) else None
        composite_signals = metrics.get("composite_signals") if isinstance(metrics, dict) else None

        return {
            "symbol": analysis.get("symbol", symbol) if isinstance(analysis, dict) else symbol,
            "exchange": exchange_sanitized,
            "timeframe": timeframe_sanitized,
            "pivot_levels": pivot_levels or {},
            "levels": _structured_levels_from_pivots(pivot_levels or {}),
            "metrics": metrics or {},
            "composite_signals": composite_signals,
        }

    @mcp.tool()
    def futures_orb_predictor(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Predict ORB levels for a futures symbol using current OHLC + ATR."""
        exchange_sanitized = sanitize_exchange(exchange, "cme_mini")
        timeframe_sanitized = sanitize_timeframe(timeframe, "15m")
        screener = _resolve_futures_screener(exchange_sanitized)

        if not TRADINGVIEW_TA_AVAILABLE:
            return {
                "error": "tradingview_ta is missing; run `uv sync`.",
                "symbol": symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
            }

        normalized_symbol = _normalize_futures_symbol(symbol, exchange_sanitized)
        if not normalized_symbol:
            return {
                "error": "Invalid symbol",
                "symbol": symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
            }

        try:
            analysis = _safe_get_multiple_analysis(
                screener=screener,
                interval=timeframe_sanitized,
                symbols=[normalized_symbol],
                tv_session_id=tv_session_id,
            )
        except Exception as exc:
            return {
                "error": f"Analysis failed: {str(exc)}",
                "symbol": normalized_symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
            }

        if not isinstance(analysis, dict) or normalized_symbol not in analysis:
            return {
                "error": f"No data found for {normalized_symbol}",
                "symbol": normalized_symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
            }

        analysis_item = analysis.get(normalized_symbol)
        indicators = analysis_item.indicators if analysis_item is not None and hasattr(analysis_item, "indicators") else None
        if not isinstance(indicators, dict):
            return {
                "error": f"No indicator data found for {normalized_symbol}",
                "symbol": normalized_symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
            }

        open_price = indicators.get("open")
        high = indicators.get("high")
        low = indicators.get("low")
        atr = indicators.get("ATR")

        if open_price is None or high is None or low is None or atr is None:
            return {
                "error": "Required indicators are missing (open/high/low/ATR)",
                "symbol": normalized_symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
                "inputs": {
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "atr": atr,
                },
            }

        try:
            orb_levels = calculate_orb_levels(
                open_price=float(open_price),
                high=float(high),
                low=float(low),
                atr=float(atr),
            )
        except Exception as exc:
            return {
                "error": f"Could not calculate ORB levels: {str(exc)}",
                "symbol": normalized_symbol,
                "exchange": exchange_sanitized,
                "timeframe": timeframe_sanitized,
            }

        return {
            "symbol": normalized_symbol,
            "exchange": exchange_sanitized,
            "timeframe": timeframe_sanitized,
            "orb_levels": orb_levels,
            "inputs": {
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "atr": float(atr),
            },
        }
