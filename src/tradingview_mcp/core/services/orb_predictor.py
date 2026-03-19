from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Any, Dict


DEFAULT_PRECISION = 4


def _to_valid_float(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid number") from exc

    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _round_half_up(value: float, digits: int = DEFAULT_PRECISION) -> float:
    quant = Decimal("1").scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)
    return float(rounded)


def calculate_orb_levels(
    open_price: float,
    high: float,
    low: float,
    atr: float,
    session_open: float | None = None,
) -> Dict[str, Any]:
    """
    Calculate ORB projection levels around the opening price.

    Range source:
    - ATR when no session candle data is available (session_open is None)
    - Session range (high - low) when session_open is provided
    """
    open_value = _to_valid_float("open_price", open_price)
    high_value = _to_valid_float("high", high)
    low_value = _to_valid_float("low", low)
    atr_value = _to_valid_float("atr", atr)

    if atr_value < 0:
        raise ValueError("atr must be non-negative")
    if high_value < low_value:
        raise ValueError("high must be greater than or equal to low")

    if session_open is None:
        range_estimate = atr_value
        range_source = "atr"
    else:
        _to_valid_float("session_open", session_open)
        range_estimate = high_value - low_value
        range_source = "session_range"

    small_range_high = open_value + (range_estimate * 0.5)
    small_range_low = open_value - (range_estimate * 0.5)
    range_high = open_value + (range_estimate * 1.0)
    range_low = open_value - (range_estimate * 1.0)
    large_range_high = open_value + (range_estimate * 1.5)
    large_range_low = open_value - (range_estimate * 1.5)

    return {
        "small_range_high": _round_half_up(small_range_high),
        "small_range_low": _round_half_up(small_range_low),
        "range_high": _round_half_up(range_high),
        "range_low": _round_half_up(range_low),
        "large_range_high": _round_half_up(large_range_high),
        "large_range_low": _round_half_up(large_range_low),
        "metadata": {
            "open_price": _round_half_up(open_value),
            "range_estimate": _round_half_up(range_estimate),
            "range_source": range_source,
            "atr": _round_half_up(atr_value),
            "session_open": _round_half_up(float(session_open)) if session_open is not None else None,
            "session_high": _round_half_up(high_value),
            "session_low": _round_half_up(low_value),
            "precision": DEFAULT_PRECISION,
        },
    }
