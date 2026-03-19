"""Pure computation functions for intraday trading levels from OHLCV bars.

All functions are stateless and have no external dependencies.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def split_sessions(
    bars: List[Dict[str, Any]], gap_seconds: int = 14400
) -> List[List[Dict[str, Any]]]:
    """Split bars into sessions based on timestamp gaps.

    A new session starts when the gap between consecutive bars exceeds
    gap_seconds (default 4 hours = 14400s).
    """
    if not bars:
        return []

    sessions: List[List[Dict[str, Any]]] = [[bars[0]]]
    for i in range(1, len(bars)):
        gap = bars[i]["timestamp"] - bars[i - 1]["timestamp"]
        if gap > gap_seconds:
            sessions.append([bars[i]])
        else:
            sessions[-1].append(bars[i])

    return sessions


def compute_vwap(bars: List[Dict[str, Any]]) -> Optional[float]:
    """Compute VWAP from a list of OHLCV bars.

    VWAP = sum(typical_price * volume) / sum(volume)
    where typical_price = (high + low + close) / 3
    """
    if not bars:
        return None

    cum_tp_vol = 0.0
    cum_vol = 0.0

    for bar in bars:
        vol = float(bar.get("volume", 0))
        if vol <= 0:
            continue
        tp = (float(bar["high"]) + float(bar["low"]) + float(bar["close"])) / 3.0
        cum_tp_vol += tp * vol
        cum_vol += vol

    if cum_vol <= 0:
        return None

    return round(cum_tp_vol / cum_vol, 4)


def compute_classic_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Compute classic pivot points from prior session OHLC."""
    pp = (high + low + close) / 3.0
    return {
        "pivot": round(pp, 4),
        "s1": round(2 * pp - high, 4),
        "s2": round(pp - (high - low), 4),
        "s3": round(low - 2 * (high - pp), 4),
        "r1": round(2 * pp - low, 4),
        "r2": round(pp + (high - low), 4),
        "r3": round(high + 2 * (pp - low), 4),
    }


def compute_fibonacci_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Compute Fibonacci pivot points from prior session OHLC."""
    pp = (high + low + close) / 3.0
    r = high - low
    return {
        "pivot": round(pp, 4),
        "s1": round(pp - 0.382 * r, 4),
        "s2": round(pp - 0.618 * r, 4),
        "s3": round(pp - 1.000 * r, 4),
        "r1": round(pp + 0.382 * r, 4),
        "r2": round(pp + 0.618 * r, 4),
        "r3": round(pp + 1.000 * r, 4),
    }


def compute_camarilla_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Compute Camarilla pivot points from prior session OHLC."""
    r = high - low
    return {
        "s1": round(close - r * 1.1 / 12, 4),
        "s2": round(close - r * 1.1 / 6, 4),
        "s3": round(close - r * 1.1 / 4, 4),
        "s4": round(close - r * 1.1 / 2, 4),
        "r1": round(close + r * 1.1 / 12, 4),
        "r2": round(close + r * 1.1 / 6, 4),
        "r3": round(close + r * 1.1 / 4, 4),
        "r4": round(close + r * 1.1 / 2, 4),
    }


def _session_ohlc(bars: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract session-level OHLC from a list of bars."""
    if not bars:
        return {}
    return {
        "open": float(bars[0]["open"]),
        "high": max(float(b["high"]) for b in bars),
        "low": min(float(b["low"]) for b in bars),
        "close": float(bars[-1]["close"]),
    }


def compute_session_levels(
    bars: List[Dict[str, Any]], gap_seconds: int = 14400
) -> Optional[Dict[str, Any]]:
    """Compute comprehensive intraday levels from OHLCV bars.

    Requires at least 2 sessions (prior + current) to compute levels.
    Returns None if insufficient data.

    Output includes:
    - prior_day_high/low/close
    - session_open/high/low
    - session_vwap
    - classic_pivots, fibonacci_pivots, camarilla_pivots
    - opening_range (first bar of current session)
    """
    if not bars:
        return None

    sessions = split_sessions(bars, gap_seconds=gap_seconds)
    if len(sessions) < 2:
        return None

    prior_session = sessions[-2]
    current_session = sessions[-1]

    prior_ohlc = _session_ohlc(prior_session)
    current_ohlc = _session_ohlc(current_session)

    if not prior_ohlc or not current_ohlc:
        return None

    prior_h = prior_ohlc["high"]
    prior_l = prior_ohlc["low"]
    prior_c = prior_ohlc["close"]

    # Opening range from first bar of current session
    first_bar = current_session[0]
    opening_range = {
        "high": float(first_bar["high"]),
        "low": float(first_bar["low"]),
    }

    return {
        "prior_day_high": prior_h,
        "prior_day_low": prior_l,
        "prior_day_close": prior_c,
        "session_open": current_ohlc["open"],
        "session_high": current_ohlc["high"],
        "session_low": current_ohlc["low"],
        "session_vwap": compute_vwap(current_session),
        "opening_range": opening_range,
        "classic_pivots": compute_classic_pivots(prior_h, prior_l, prior_c),
        "fibonacci_pivots": compute_fibonacci_pivots(prior_h, prior_l, prior_c),
        "camarilla_pivots": compute_camarilla_pivots(prior_h, prior_l, prior_c),
    }
