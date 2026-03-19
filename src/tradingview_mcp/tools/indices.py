from __future__ import annotations

from typing import Any, Dict, List, Optional

from tradingview_mcp.core.services.indicators import (
    compute_expanded_metrics,
    compute_metrics,
    compute_pivot_levels,
)
from tradingview_mcp.core.utils.validators import EXCHANGE_SCREENER, sanitize_exchange, sanitize_timeframe
from tradingview_mcp.tools.shared import analyze_single

try:
    from tradingview_ta import get_multiple_analysis

    TRADINGVIEW_TA_AVAILABLE = True
except Exception:
    TRADINGVIEW_TA_AVAILABLE = False

try:
    from tradingview_screener import Query
    from tradingview_screener.column import Column

    TRADINGVIEW_SCREENER_AVAILABLE = True
except Exception:
    TRADINGVIEW_SCREENER_AVAILABLE = False


def _tf_to_tv_resolution(tf: Optional[str]) -> Optional[str]:
    if not tf:
        return None
    return {
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1D": "1D",
        "1W": "1W",
        "1M": "1M",
    }.get(tf)


def _normalize_symbol(symbol: str, exchange: str) -> str:
    clean = (symbol or "").strip().upper()
    if not clean:
        return ""
    if ":" in clean:
        return clean
    return f"{exchange.upper()}:{clean}"


def _resolve_screener(exchange: str) -> str:
    # For indices support, CBOE is mapped to `cfd` in validators.
    return EXCHANGE_SCREENER.get(exchange, "cfd")


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


def _build_columns(timeframe: str, include_pivots: bool = False) -> List[str]:
    suffix = _tf_to_tv_resolution(timeframe)
    base_cols = ["open", "close", "SMA20", "BB.upper", "BB.lower", "EMA50", "RSI", "volume"]

    if include_pivots:
        pivot_cols = []
        for base in ("Pivot.M.Classic", "Pivot.M.Fibonacci", "Pivot.M.Camarilla"):
            pivot_cols.extend(
                [
                    f"{base}.Middle",
                    f"{base}.S1",
                    f"{base}.S2",
                    f"{base}.S3",
                    f"{base}.R1",
                    f"{base}.R2",
                    f"{base}.R3",
                ]
            )
        base_cols.extend(pivot_cols)

    if suffix:
        return [f"{col}|{suffix}" for col in base_cols]
    return base_cols


def _row_to_indicators(row: Any) -> Dict[str, Any]:
    # Normalize suffixed column names back to base key names.
    indicators: Dict[str, Any] = {}
    for key in list(row.index):
        if not isinstance(key, str):
            continue
        normalized = key.split("|")[0]
        if normalized == "ticker":
            continue
        indicators[normalized] = row.get(key)
    return indicators


def _query_rows(
    *,
    exchange: str,
    timeframe: str,
    limit: int,
    symbol: Optional[str] = None,
    include_pivots: bool = False,
    cookies: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    if not TRADINGVIEW_SCREENER_AVAILABLE:
        return []

    screener = _resolve_screener(exchange)
    cols = _build_columns(timeframe, include_pivots=include_pivots)

    query = Query().set_markets(screener).select(*cols)
    if symbol:
        query = query.set_tickers(symbol)
    else:
        query = query.where(Column("exchange") == exchange.upper())

    query = query.limit(int(limit))

    _, df = query.get_scanner_data(cookies=cookies)
    if df is None or df.empty:
        return []

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "symbol": row.get("ticker"),
                "indicators": _row_to_indicators(row),
            }
        )
    return rows


def _analyze_with_ta(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
    if not TRADINGVIEW_TA_AVAILABLE:
        return {"error": "tradingview_ta is missing"}

    screener = _resolve_screener(exchange)
    cookies = _session_cookies(tv_session_id)
    try:
        if cookies:
            try:
                analysis = get_multiple_analysis(
                    screener=screener,
                    interval=timeframe,
                    symbols=[symbol],
                    cookies=cookies,
                )
            except TypeError:
                analysis = get_multiple_analysis(screener=screener, interval=timeframe, symbols=[symbol])
        else:
            analysis = get_multiple_analysis(screener=screener, interval=timeframe, symbols=[symbol])
    except Exception as exc:
        return {"error": f"Analysis failed: {str(exc)}"}

    if not isinstance(analysis, dict) or symbol not in analysis or analysis.get(symbol) is None:
        return {"error": f"No data found for {symbol}"}

    item = analysis[symbol]
    indicators = getattr(item, "indicators", None)
    if not isinstance(indicators, dict):
        return {"error": f"No indicators for {symbol}"}

    expanded = compute_expanded_metrics(indicators)
    metrics = expanded if expanded is not None else compute_metrics(indicators)
    if metrics is None:
        return {"error": f"Could not compute metrics for {symbol}"}

    return {
        "symbol": symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "metrics": metrics,
        "composite_signals": metrics.get("composite_signals"),
        "pivot_levels": metrics.get("pivot_levels") or compute_pivot_levels(indicators),
    }


def _analyze_with_query(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
    cookies = _session_cookies(tv_session_id)
    rows = _query_rows(
        exchange=exchange,
        timeframe=timeframe,
        limit=1,
        symbol=symbol,
        include_pivots=True,
        cookies=cookies,
    )
    if not rows:
        return {"error": f"No data found for {symbol}"}

    indicators = rows[0].get("indicators") or {}
    expanded = compute_expanded_metrics(indicators)
    metrics = expanded if expanded is not None else compute_metrics(indicators)
    if metrics is None:
        return {"error": f"Could not compute metrics for {symbol}"}

    return {
        "symbol": rows[0].get("symbol") or symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "metrics": metrics,
        "composite_signals": metrics.get("composite_signals"),
        "pivot_levels": metrics.get("pivot_levels") or compute_pivot_levels(indicators),
        "fallback": "screener_query",
    }


def _session_cookies(tv_session_id: str = "") -> Optional[Dict[str, str]]:
    session_id = (tv_session_id or "").strip()
    if not session_id:
        return None
    return {"sessionid": session_id}


def register_indices_tools(mcp: Any) -> None:
    @mcp.tool()
    def indices_analysis(symbol: str, exchange: str = "CBOE", timeframe: str = "15m", tv_session_id: str = "") -> dict:
        """Analyze a single index symbol with CBOE/cfd defaults.

        Fallback path: if direct TradingView-TA analysis fails, a TradingView-Screener
        query is attempted with screener/exchange mapping.
        """

        ex = sanitize_exchange(exchange, "cboe")
        tf = sanitize_timeframe(timeframe, "15m")
        normalized_symbol = _normalize_symbol(symbol, ex)
        if not normalized_symbol:
            return {
                "error": "Invalid symbol",
                "symbol": symbol,
                "exchange": ex,
                "timeframe": tf,
            }

        direct_result = _analyze_with_ta(normalized_symbol, ex, tf, tv_session_id=tv_session_id)
        if "error" not in direct_result:
            return direct_result

        # Required fallback: query path when direct analysis fails.
        fallback_result = _analyze_with_query(normalized_symbol, ex, tf, tv_session_id=tv_session_id)
        if "error" not in fallback_result:
            return fallback_result

        return {
            "error": f"{direct_result.get('error')} | fallback failed: {fallback_result.get('error')}",
            "symbol": normalized_symbol,
            "exchange": ex,
            "timeframe": tf,
        }

    @mcp.tool()
    def indices_bollinger_scan(
        exchange: str = "CBOE",
        timeframe: str = "4h",
        bbw_threshold: float = 0.04,
        limit: int = 50,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Scan index symbols with low Bollinger Band Width (squeeze)."""

        ex = sanitize_exchange(exchange, "cboe")
        tf = sanitize_timeframe(timeframe, "4h")
        safe_limit = max(1, min(int(limit), 100))

        rows = _query_rows(
            exchange=ex,
            timeframe=tf,
            limit=max(safe_limit * 2, 100),
            include_pivots=False,
            cookies=_session_cookies(tv_session_id),
        )
        output: List[Dict[str, Any]] = []
        for row in rows:
            indicators = row.get("indicators") or {}
            metrics = compute_metrics(indicators)
            if not metrics or metrics.get("bbw") is None:
                continue
            if metrics["bbw"] <= 0 or metrics["bbw"] >= bbw_threshold:
                continue

            output.append(
                {
                    "symbol": row.get("symbol"),
                    "exchange": ex,
                    "timeframe": tf,
                    **metrics,
                }
            )

        output.sort(key=lambda item: item.get("bbw") if item.get("bbw") is not None else 999, reverse=False)
        return output[:safe_limit]

    @mcp.tool()
    def indices_rating_filter(
        exchange: str = "CBOE",
        timeframe: str = "5m",
        rating: int = 2,
        limit: int = 25,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Filter index symbols by Bollinger rating (-3..+3)."""

        ex = sanitize_exchange(exchange, "cboe")
        tf = sanitize_timeframe(timeframe, "5m")
        safe_limit = max(1, min(int(limit), 50))
        target_rating = max(-3, min(3, int(rating)))

        rows = _query_rows(
            exchange=ex,
            timeframe=tf,
            limit=max(safe_limit * 3, 120),
            include_pivots=False,
            cookies=_session_cookies(tv_session_id),
        )
        output: List[Dict[str, Any]] = []
        for row in rows:
            indicators = row.get("indicators") or {}
            metrics = compute_metrics(indicators)
            if not metrics:
                continue
            if metrics.get("rating") != target_rating:
                continue

            output.append(
                {
                    "symbol": row.get("symbol"),
                    "exchange": ex,
                    "timeframe": tf,
                    **metrics,
                }
            )

        output.sort(key=lambda item: item.get("change") if item.get("change") is not None else 0, reverse=True)
        return output[:safe_limit]

    @mcp.tool()
    def indices_levels(symbol: str, exchange: str = "CBOE", timeframe: str = "1D", tv_session_id: str = "") -> dict:
        """Return pivot/support/resistance levels for a single index symbol."""

        ex = sanitize_exchange(exchange, "cboe")
        tf = sanitize_timeframe(timeframe, "1D")
        analysis = analyze_single(symbol=symbol, exchange=ex, timeframe=tf, tv_session_id=tv_session_id)
        if "error" in analysis:
            return analysis

        metrics = analysis.get("metrics") if isinstance(analysis, dict) else {}
        pivot_levels = metrics.get("pivot_levels", {}) if isinstance(metrics, dict) else {}
        return {
            "symbol": analysis.get("symbol") if isinstance(analysis, dict) else symbol,
            "exchange": analysis.get("exchange") if isinstance(analysis, dict) else ex,
            "timeframe": analysis.get("timeframe") if isinstance(analysis, dict) else tf,
            "pivot_levels": pivot_levels,
            "levels": _structured_levels_from_pivots(pivot_levels),
            "metrics": metrics,
        }
