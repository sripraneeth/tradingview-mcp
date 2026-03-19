from __future__ import annotations

from statistics import median
from typing import Any, Dict, List

from tradingview_mcp.tools.shared import analyze_single, fetch_and_analyze


def _clamp_limit(limit: int, max_limit: int) -> int:
    try:
        value = int(limit)
    except Exception:
        return 25
    return max(1, min(value, max_limit))


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


def _as_float(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def register_stocks_tools(mcp) -> None:
    @mcp.tool()
    def stocks_top_gainers(
        exchange: str = "NASDAQ",
        timeframe: str = "15m",
        limit: int = 25,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Return top stock gainers for an exchange/timeframe."""
        return fetch_and_analyze(
            exchange=exchange,
            timeframe=timeframe,
            symbols=None,
            limit=_clamp_limit(limit, 50),
            filter_fn=None,
            sort_key="change",
            sort_reverse=True,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def stocks_top_losers(
        exchange: str = "NASDAQ",
        timeframe: str = "15m",
        limit: int = 25,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Return top stock losers for an exchange/timeframe."""
        return fetch_and_analyze(
            exchange=exchange,
            timeframe=timeframe,
            symbols=None,
            limit=_clamp_limit(limit, 50),
            filter_fn=None,
            sort_key="change",
            sort_reverse=False,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def stocks_bollinger_scan(
        exchange: str = "NASDAQ",
        timeframe: str = "4h",
        bbw_threshold: float = 0.04,
        limit: int = 50,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Scan stocks with low Bollinger Band Width (squeeze)."""

        def _filter(item: Dict[str, Any]) -> bool:
            bbw = item.get("bbw")
            return isinstance(bbw, (int, float)) and bbw > 0 and bbw < bbw_threshold

        return fetch_and_analyze(
            exchange=exchange,
            timeframe=timeframe,
            symbols=None,
            limit=_clamp_limit(limit, 100),
            filter_fn=_filter,
            sort_key="bbw",
            sort_reverse=False,
            tv_session_id=tv_session_id,
        )

    @mcp.tool()
    def stocks_analysis(symbol: str, exchange: str = "NASDAQ", timeframe: str = "15m", tv_session_id: str = "") -> Dict[str, Any]:
        """Get detailed technical analysis for a stock symbol."""
        return analyze_single(symbol=symbol, exchange=exchange, timeframe=timeframe, tv_session_id=tv_session_id)

    @mcp.tool()
    def stocks_volume_breakout(
        exchange: str = "NASDAQ",
        timeframe: str = "15m",
        volume_multiplier: float = 2.0,
        price_change_min: float = 3.0,
        limit: int = 25,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Detect stocks with breakout move plus relative volume breakout."""
        rows = fetch_and_analyze(
            exchange=exchange,
            timeframe=timeframe,
            symbols=None,
            limit=500,
            filter_fn=None,
            sort_key="volume",
            sort_reverse=True,
            tv_session_id=tv_session_id,
        )
        if not rows:
            return []

        volumes: List[float] = []
        for row in rows:
            row_volume = row.get("volume")
            if isinstance(row_volume, (int, float)):
                volumes.append(_as_float(row_volume))
        baseline = median(volumes) if volumes else 0.0

        out: List[Dict[str, Any]] = []
        for item in rows:
            change = item.get("change")
            volume = item.get("volume")
            if not isinstance(change, (int, float)) or abs(change) < price_change_min:
                continue
            if not isinstance(volume, (int, float)) or volume <= 0:
                continue

            volume_ratio = (float(volume) / baseline) if baseline > 0 else 0.0
            if volume_ratio < volume_multiplier:
                continue

            out.append(
                {
                    **item,
                    "volume_ratio": round(volume_ratio, 3),
                    "breakout_type": "bullish" if change > 0 else "bearish",
                }
            )

        out.sort(key=lambda x: (x.get("volume_ratio", 0), abs(x.get("change", 0))), reverse=True)
        return out[: _clamp_limit(limit, 50)]

    @mcp.tool()
    def stocks_smart_scanner(
        exchange: str = "NASDAQ",
        min_volume_ratio: float = 2.0,
        min_price_change: float = 2.0,
        rsi_range: str = "any",
        limit: int = 20,
        tv_session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Smart stock scanner combining volume, move, and RSI conditions."""
        candidates = stocks_volume_breakout(
            exchange=exchange,
            timeframe="15m",
            volume_multiplier=min_volume_ratio,
            price_change_min=min_price_change,
            limit=200,
            tv_session_id=tv_session_id,
        )

        filtered: List[Dict[str, Any]] = []
        for item in candidates:
            rsi = item.get("RSI")
            if not isinstance(rsi, (int, float)):
                continue

            if rsi_range == "oversold" and rsi >= 30:
                continue
            if rsi_range == "overbought" and rsi <= 70:
                continue
            if rsi_range == "neutral" and (rsi <= 30 or rsi >= 70):
                continue

            filtered.append(item)

        filtered.sort(key=lambda x: (x.get("volume_ratio", 0), abs(x.get("change", 0))), reverse=True)
        return filtered[: _clamp_limit(limit, 30)]

    @mcp.tool()
    def stocks_levels(symbol: str, exchange: str = "NASDAQ", timeframe: str = "1D", tv_session_id: str = "") -> Dict[str, Any]:
        """Return pivot support/resistance levels for a stock symbol."""
        analysis = analyze_single(symbol=symbol, exchange=exchange, timeframe=timeframe, tv_session_id=tv_session_id)
        if "error" in analysis:
            return analysis

        metrics = analysis.get("metrics") or {}
        pivot_levels = metrics.get("pivot_levels", {})
        return {
            "symbol": analysis.get("symbol"),
            "exchange": analysis.get("exchange"),
            "timeframe": analysis.get("timeframe"),
            "pivot_levels": pivot_levels,
            "levels": _structured_levels_from_pivots(pivot_levels),
        }
