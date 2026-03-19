from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Union, cast

from tradingview_mcp.core.services.coinlist import load_symbols
from tradingview_mcp.core.services.indicators import (
    compute_composite_signals,
    compute_metrics,
    compute_pivot_levels,
)
from tradingview_mcp.core.utils.validators import EXCHANGE_SCREENER, sanitize_exchange, sanitize_timeframe

try:
    from tradingview_ta import get_multiple_analysis

    TRADINGVIEW_TA_AVAILABLE = True
except ImportError:
    get_multiple_analysis = None
    TRADINGVIEW_TA_AVAILABLE = False


MetricsDict = Dict[str, Any]
FilterFn = Callable[[MetricsDict], bool]
SortKeyCallable = Callable[[MetricsDict], Any]
SortKeyType = Optional[Union[str, SortKeyCallable]]


def _build_tv_cookies(tv_session_id: str = "") -> Optional[Dict[str, str]]:
    session_id = (tv_session_id or "").strip()
    if not session_id:
        return None
    return {"sessionid": session_id}


def _safe_get_multiple_analysis(
    *,
    screener: str,
    interval: str,
    symbols: Sequence[str],
    tv_session_id: str = "",
) -> Any:
    fn = get_multiple_analysis
    if not TRADINGVIEW_TA_AVAILABLE or fn is None:
        raise RuntimeError("tradingview_ta is missing; run `uv sync`.")

    cookies = _build_tv_cookies(tv_session_id)
    if cookies:
        try:
            return fn(
                screener=screener,
                interval=interval,
                symbols=list(symbols),
                cookies=cookies,
            )
        except TypeError:
            # Older tradingview_ta versions may not support a cookies kwarg.
            pass

    return fn(
        screener=screener,
        interval=interval,
        symbols=list(symbols),
    )


def _resolve_compute_expanded_metrics() -> Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]]:
    """Resolve optional expanded metrics function without hard dependency."""
    for module_path in (
        "tradingview_mcp.core.services.indicators",
        "tradingview_mcp.core.services.expanded_indicators",
    ):
        try:
            module = __import__(module_path, fromlist=["compute_expanded_metrics"])
            fn = getattr(module, "compute_expanded_metrics", None)
            if callable(fn):
                return cast(Callable[[Dict[str, Any]], Optional[Dict[str, Any]]], fn)
        except Exception:
            continue
    return None


def _resolve_screener(exchange: str) -> str:
    sanitized_exchange = sanitize_exchange(exchange, "kucoin")
    return EXCHANGE_SCREENER.get(sanitized_exchange, "crypto")


def _normalize_symbol(symbol: str, exchange: str) -> str:
    symbol_clean = (symbol or "").strip().upper()
    if not symbol_clean:
        return ""

    if ":" in symbol_clean:
        return symbol_clean

    return f"{exchange.upper()}:{symbol_clean}"


def _batch(items: Sequence[str], size: int) -> List[List[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def _compute_symbol_metrics(
    symbol: str,
    analysis_item: Any,
    compute_expanded_metrics: Optional[Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]],
    exchange: str,
    timeframe: str,
) -> Optional[MetricsDict]:
    try:
        if analysis_item is None or not hasattr(analysis_item, "indicators"):
            return None

        indicators = analysis_item.indicators
        if not isinstance(indicators, dict):
            return None

        metrics: Optional[Dict[str, Any]] = None
        if compute_expanded_metrics is not None:
            try:
                metrics = compute_expanded_metrics(indicators)
            except Exception:
                metrics = None

        if metrics is None:
            metrics = compute_metrics(indicators)

        if metrics is None:
            return None

        result: MetricsDict = {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            **metrics,
        }

        if "composite_signals" in metrics:
            result["composite_signals"] = metrics.get("composite_signals")

        return result
    except Exception:
        return None


def _sort_results(rows: List[MetricsDict], sort_key: SortKeyType, sort_reverse: bool) -> List[MetricsDict]:
    if not rows:
        return rows

    try:
        if callable(sort_key):
            rows.sort(key=sort_key, reverse=sort_reverse)
            return rows

        if isinstance(sort_key, str) and sort_key:
            rows.sort(
                key=lambda item: (item.get(sort_key) is None, item.get(sort_key)),
                reverse=sort_reverse,
            )
            return rows
    except Exception:
        pass

    return rows


def fetch_and_analyze(
    exchange: str,
    timeframe: str,
    symbols: Optional[Sequence[str]],
    limit: int,
    filter_fn: Optional[FilterFn],
    sort_key: SortKeyType,
    sort_reverse: bool,
    tv_session_id: str = "",
) -> List[MetricsDict]:
    """Fetch TradingView analysis in batches and return processed metrics."""
    if not TRADINGVIEW_TA_AVAILABLE:
        raise RuntimeError("tradingview_ta is missing; run `uv sync`.")

    sanitized_exchange = sanitize_exchange(exchange, "kucoin")
    sanitized_timeframe = sanitize_timeframe(timeframe, "15m")
    safe_limit = max(1, int(limit)) if isinstance(limit, int) else 25

    source_symbols = list(symbols) if symbols else load_symbols(sanitized_exchange)
    if not source_symbols:
        return []

    normalized_symbols = [
        normalized
        for normalized in (_normalize_symbol(symbol, sanitized_exchange) for symbol in source_symbols)
        if normalized
    ]
    if not normalized_symbols:
        return []

    screener = _resolve_screener(sanitized_exchange)
    compute_expanded_metrics = _resolve_compute_expanded_metrics()

    rows: List[MetricsDict] = []
    for symbol_batch in _batch(normalized_symbols, 200):
        try:
            analysis = _safe_get_multiple_analysis(
                screener=screener,
                interval=sanitized_timeframe,
                symbols=symbol_batch,
                tv_session_id=tv_session_id,
            )
        except Exception:
            continue

        if not isinstance(analysis, dict):
            continue

        for symbol, analysis_item in analysis.items():
            metric_row = _compute_symbol_metrics(
                symbol=symbol,
                analysis_item=analysis_item,
                compute_expanded_metrics=compute_expanded_metrics,
                exchange=sanitized_exchange,
                timeframe=sanitized_timeframe,
            )
            if metric_row is None:
                continue

            if filter_fn is not None:
                try:
                    if not filter_fn(metric_row):
                        continue
                except Exception:
                    continue

            rows.append(metric_row)

    rows = _sort_results(rows, sort_key, sort_reverse)
    return rows[:safe_limit]


def analyze_single(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
    """Analyze a single symbol and return expanded metrics when available."""
    if not TRADINGVIEW_TA_AVAILABLE:
        return {"error": "tradingview_ta is missing; run `uv sync`."}

    sanitized_exchange = sanitize_exchange(exchange, "kucoin")
    sanitized_timeframe = sanitize_timeframe(timeframe, "15m")
    normalized_symbol = _normalize_symbol(symbol, sanitized_exchange)
    if not normalized_symbol:
        return {
            "error": "Invalid symbol",
            "symbol": symbol,
            "exchange": sanitized_exchange,
            "timeframe": sanitized_timeframe,
        }

    screener = _resolve_screener(sanitized_exchange)
    compute_expanded_metrics = _resolve_compute_expanded_metrics()

    try:
        analysis = _safe_get_multiple_analysis(
            screener=screener,
            interval=sanitized_timeframe,
            symbols=[normalized_symbol],
            tv_session_id=tv_session_id,
        )
    except Exception as e:
        return {
            "error": f"Analysis failed: {str(e)}",
            "symbol": normalized_symbol,
            "exchange": sanitized_exchange,
            "timeframe": sanitized_timeframe,
        }

    if not isinstance(analysis, dict) or normalized_symbol not in analysis:
        return {
            "error": f"No data found for {normalized_symbol}",
            "symbol": normalized_symbol,
            "exchange": sanitized_exchange,
            "timeframe": sanitized_timeframe,
        }

    analysis_item = analysis.get(normalized_symbol)
    indicators = getattr(analysis_item, "indicators", None)

    metrics = _compute_symbol_metrics(
        symbol=normalized_symbol,
        analysis_item=analysis_item,
        compute_expanded_metrics=compute_expanded_metrics,
        exchange=sanitized_exchange,
        timeframe=sanitized_timeframe,
    )

    if metrics is None:
        return {
            "error": f"Could not compute metrics for {normalized_symbol}",
            "symbol": normalized_symbol,
            "exchange": sanitized_exchange,
            "timeframe": sanitized_timeframe,
        }

    composite_signals = compute_composite_signals(metrics)
    pivot_levels = compute_pivot_levels(indicators if isinstance(indicators, dict) else {})

    return {
        "symbol": normalized_symbol,
        "exchange": sanitized_exchange,
        "timeframe": sanitized_timeframe,
        "metrics": metrics,
        "composite_signals": metrics.get("composite_signals") or composite_signals,
        "pivot_levels": metrics.get("pivot_levels") or pivot_levels,
        "trend_strength": composite_signals.get("trend_strength"),
        "oscillator_score": composite_signals.get("oscillator_score"),
        "confluence_signal": composite_signals.get("confluence_signal"),
        "support_resistance_levels": pivot_levels,
    }
