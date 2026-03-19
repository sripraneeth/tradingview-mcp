from __future__ import annotations
from typing import Any, Dict, Optional, Tuple


def compute_change(open_price: float, close: float) -> float:
    return ((close - open_price) / open_price) * 100 if open_price else 0.0


def compute_bbw(sma: float, bb_upper: float, bb_lower: float) -> Optional[float]:
    if not sma:
        return None
    try:
        return (bb_upper - bb_lower) / sma
    except ZeroDivisionError:
        return None


def compute_bb_rating_signal(close: float, bb_upper: float, bb_middle: float, bb_lower: float) -> Tuple[int, str]:
    rating = 0
    if close > bb_upper:
        rating = 3
    elif close > bb_middle + ((bb_upper - bb_middle) / 2):
        rating = 2
    elif close > bb_middle:
        rating = 1
    elif close < bb_lower:
        rating = -3
    elif close < bb_middle - ((bb_middle - bb_lower) / 2):
        rating = -2
    elif close < bb_middle:
        rating = -1

    signal = "NEUTRAL"
    if rating == 2:
        signal = "BUY"
    elif rating == -2:
        signal = "SELL"
    return rating, signal


def compute_metrics(indicators: Dict) -> Optional[Dict]:
    try:
        open_price = indicators["open"]
        close = indicators["close"]
        sma = indicators["SMA20"]
        bb_upper = indicators["BB.upper"]
        bb_lower = indicators["BB.lower"]
        bb_middle = sma

        change = compute_change(open_price, close)
        bbw = compute_bbw(sma, bb_upper, bb_lower)
        rating, signal = compute_bb_rating_signal(close, bb_upper, bb_middle, bb_lower)

        return {
            "price": round(close, 4),
            "change": round(change, 3),
            "bbw": round(bbw, 4) if bbw is not None else None,
            "rating": rating,
            "signal": signal,
        }
    except (KeyError, TypeError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def compute_composite_signals(metrics: Dict) -> Dict:
    adx = _to_float(metrics.get("ADX"))
    if adx is None:
        trend_strength = "Unknown"
    elif adx < 20:
        trend_strength = "Ranging"
    elif adx <= 40:
        trend_strength = "Trending"
    else:
        trend_strength = "Strong Trend"

    rsi = _to_float(metrics.get("RSI"))
    stoch_k = _to_float(metrics.get("Stoch.K"))
    stoch_d = _to_float(metrics.get("Stoch.D"))
    cci20 = _to_float(metrics.get("CCI20"))
    wr = _to_float(metrics.get("W.R"))

    rsi_score = _clamp((50 - rsi) * 2, -100, 100) if rsi is not None else 0.0
    stoch_base = ((stoch_k + stoch_d) / 2) if stoch_k is not None and stoch_d is not None else stoch_k
    stoch_score = _clamp((50 - stoch_base) * 2, -100, 100) if stoch_base is not None else 0.0
    cci_score = _clamp(-cci20 / 2, -100, 100) if cci20 is not None else 0.0
    wr_score = _clamp(-2 * (wr + 50), -100, 100) if wr is not None else 0.0

    oscillator_score = _clamp(
        (rsi_score * 0.35) + (stoch_score * 0.25) + (cci_score * 0.2) + (wr_score * 0.2),
        -100,
        100,
    )

    buy_votes = 0
    sell_votes = 0

    ema10 = _to_float(metrics.get("EMA10"))
    ema20 = _to_float(metrics.get("EMA20"))
    ema50 = _to_float(metrics.get("EMA50"))
    ema100 = _to_float(metrics.get("EMA100"))
    ema200 = _to_float(metrics.get("EMA200"))

    for fast, slow in ((ema10, ema20), (ema20, ema50), (ema50, ema100), (ema100, ema200)):
        if fast is None or slow is None:
            continue
        if fast > slow:
            buy_votes += 1
        elif fast < slow:
            sell_votes += 1

    if rsi is not None:
        if rsi < 30:
            buy_votes += 1
        elif rsi > 70:
            sell_votes += 1

    macd = _to_float(metrics.get("MACD.macd"))
    macd_signal = _to_float(metrics.get("MACD.signal"))
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            buy_votes += 1
        elif macd < macd_signal:
            sell_votes += 1

    price = _to_float(metrics.get("price"))
    supertrend = _to_float(metrics.get("Supertrend"))
    if price is not None and supertrend is not None:
        if price > supertrend:
            buy_votes += 1
        elif price < supertrend:
            sell_votes += 1

    total_votes = buy_votes + sell_votes
    if buy_votes > sell_votes:
        confluence_signal = "BUY"
        confidence = int(round((buy_votes / total_votes) * 100)) if total_votes else 0
    elif sell_votes > buy_votes:
        confluence_signal = "SELL"
        confidence = int(round((sell_votes / total_votes) * 100)) if total_votes else 0
    else:
        confluence_signal = "NEUTRAL"
        confidence = int(round((50 if total_votes else 0)))

    return {
        "trend_strength": trend_strength,
        "adx": _round_or_none(adx, 3),
        "oscillator_score": round(oscillator_score, 2),
        "confluence_signal": confluence_signal,
        "confluence_confidence": confidence,
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
    }


def compute_pivot_levels(indicators: Dict) -> Dict:
    pivot_bases = {
        "classic": "Pivot.M.Classic",
        "fibonacci": "Pivot.M.Fibonacci",
        "camarilla": "Pivot.M.Camarilla",
    }

    result: Dict[str, Dict[str, Any]] = {}
    for name, base in pivot_bases.items():
        middle = _to_float(indicators.get(f"{base}.Middle"))

        support = {
            "S1": _round_or_none(_to_float(indicators.get(f"{base}.S1"))),
            "S2": _round_or_none(_to_float(indicators.get(f"{base}.S2"))),
            "S3": _round_or_none(_to_float(indicators.get(f"{base}.S3"))),
        }
        resistance = {
            "R1": _round_or_none(_to_float(indicators.get(f"{base}.R1"))),
            "R2": _round_or_none(_to_float(indicators.get(f"{base}.R2"))),
            "R3": _round_or_none(_to_float(indicators.get(f"{base}.R3"))),
        }

        has_any_value = any(value is not None for value in support.values()) or any(
            value is not None for value in resistance.values()
        ) or middle is not None

        if has_any_value:
            result[name] = {
                "middle": _round_or_none(middle),
                "support": support,
                "resistance": resistance,
            }

    return result


def compute_expanded_metrics(indicators: Dict) -> Optional[Dict]:
    open_price = _to_float(indicators.get("open"))
    close = _to_float(indicators.get("close"))
    if open_price is None or close is None:
        return None

    sma20 = _to_float(indicators.get("SMA20"))
    bb_upper = _to_float(indicators.get("BB.upper"))
    bb_lower = _to_float(indicators.get("BB.lower"))

    change = compute_change(open_price, close)
    if sma20 is not None and bb_upper is not None and bb_lower is not None:
        bbw = compute_bbw(sma20, bb_upper, bb_lower)
        rating, signal = compute_bb_rating_signal(close, bb_upper, sma20, bb_lower)
    else:
        bbw = None
        rating, signal = 0, "NEUTRAL"

    metrics: Dict[str, Any] = {
        "price": round(close, 4),
        "change": round(change, 3),
        "bbw": round(bbw, 4) if bbw is not None else None,
        "rating": rating,
        "signal": signal,
        "EMA10": _round_or_none(_to_float(indicators.get("EMA10"))),
        "EMA20": _round_or_none(_to_float(indicators.get("EMA20"))),
        "EMA50": _round_or_none(_to_float(indicators.get("EMA50"))),
        "EMA100": _round_or_none(_to_float(indicators.get("EMA100"))),
        "EMA200": _round_or_none(_to_float(indicators.get("EMA200"))),
        "SMA10": _round_or_none(_to_float(indicators.get("SMA10"))),
        "SMA20": _round_or_none(sma20),
        "SMA50": _round_or_none(_to_float(indicators.get("SMA50"))),
        "SMA100": _round_or_none(_to_float(indicators.get("SMA100"))),
        "SMA200": _round_or_none(_to_float(indicators.get("SMA200"))),
        "Supertrend": _round_or_none(_to_float(indicators.get("Supertrend"))),
        "P.SAR": _round_or_none(_to_float(indicators.get("P.SAR"))),
        "ADX": _round_or_none(_to_float(indicators.get("ADX")), 3),
        "ADX+DI": _round_or_none(_to_float(indicators.get("ADX+DI")), 3),
        "ADX-DI": _round_or_none(_to_float(indicators.get("ADX-DI")), 3),
        "Ichimoku.BLine": _round_or_none(_to_float(indicators.get("Ichimoku.BLine"))),
        "Ichimoku.CLine": _round_or_none(_to_float(indicators.get("Ichimoku.CLine"))),
        "RSI": _round_or_none(_to_float(indicators.get("RSI")), 3),
        "MACD.macd": _round_or_none(_to_float(indicators.get("MACD.macd")), 4),
        "MACD.signal": _round_or_none(_to_float(indicators.get("MACD.signal")), 4),
        "Stoch.K": _round_or_none(_to_float(indicators.get("Stoch.K")), 3),
        "Stoch.D": _round_or_none(_to_float(indicators.get("Stoch.D")), 3),
        "CCI20": _round_or_none(_to_float(indicators.get("CCI20")), 3),
        "W.R": _round_or_none(_to_float(indicators.get("W.R")), 3),
        "Mom": _round_or_none(_to_float(indicators.get("Mom")), 4),
        "AO": _round_or_none(_to_float(indicators.get("AO")), 4),
        "HullMA9": _round_or_none(_to_float(indicators.get("HullMA9"))),
        "BB.upper": _round_or_none(bb_upper),
        "BB.lower": _round_or_none(bb_lower),
        "ATR": _round_or_none(_to_float(indicators.get("ATR")), 4),
        "high": _round_or_none(_to_float(indicators.get("high"))),
        "low": _round_or_none(_to_float(indicators.get("low"))),
        "volume": _round_or_none(_to_float(indicators.get("volume")), 4),
    }

    metrics["composite_signals"] = compute_composite_signals(metrics)
    metrics["pivot_levels"] = compute_pivot_levels(indicators)
    return metrics
