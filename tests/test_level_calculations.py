from __future__ import annotations

import pytest

from tradingview_mcp.core.services.level_calc import (
    compute_session_levels,
    compute_vwap,
    compute_camarilla_pivots,
    compute_fibonacci_pivots,
    compute_classic_pivots,
    split_sessions,
)


def _make_bar(ts: float, o: float, h: float, l: float, c: float, v: float) -> dict:
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}


# --- Session splitting ---

class TestSplitSessions:
    def test_single_session(self) -> None:
        bars = [
            _make_bar(1000.0, 100, 105, 95, 102, 500),
            _make_bar(1900.0, 102, 108, 100, 106, 600),
            _make_bar(2800.0, 106, 110, 104, 109, 700),
        ]
        sessions = split_sessions(bars, gap_seconds=14400)
        assert len(sessions) == 1
        assert len(sessions[0]) == 3

    def test_two_sessions_with_gap(self) -> None:
        bars = [
            _make_bar(1000.0, 100, 105, 95, 102, 500),
            _make_bar(1900.0, 102, 108, 100, 106, 600),
            # Gap of 20000 seconds (> 4 hours)
            _make_bar(21900.0, 110, 115, 108, 113, 800),
            _make_bar(22800.0, 113, 118, 112, 116, 900),
        ]
        sessions = split_sessions(bars, gap_seconds=14400)
        assert len(sessions) == 2
        assert len(sessions[0]) == 2
        assert len(sessions[1]) == 2

    def test_empty_bars(self) -> None:
        assert split_sessions([], gap_seconds=14400) == []


# --- VWAP ---

class TestComputeVwap:
    def test_basic_vwap(self) -> None:
        bars = [
            _make_bar(1000, 100, 105, 95, 102, 1000),
            _make_bar(1900, 102, 108, 100, 106, 2000),
        ]
        # typical_price = (H+L+C)/3
        # bar1: (105+95+102)/3 = 100.667, * 1000 = 100666.67
        # bar2: (108+100+106)/3 = 104.667, * 2000 = 209333.33
        # vwap = (100666.67 + 209333.33) / 3000 = 103.333
        vwap = compute_vwap(bars)
        assert vwap is not None
        assert abs(vwap - 103.333) < 0.01

    def test_single_bar(self) -> None:
        bars = [_make_bar(1000, 100, 110, 90, 105, 500)]
        vwap = compute_vwap(bars)
        # (110+90+105)/3 = 101.667
        assert vwap is not None
        assert abs(vwap - 101.667) < 0.01

    def test_zero_volume(self) -> None:
        bars = [_make_bar(1000, 100, 110, 90, 105, 0)]
        assert compute_vwap(bars) is None

    def test_empty_bars(self) -> None:
        assert compute_vwap([]) is None


# --- Pivot calculations ---

class TestClassicPivots:
    def test_standard_calculation(self) -> None:
        # PP = (H + L + C) / 3 = (110 + 90 + 105) / 3 = 101.667
        pivots = compute_classic_pivots(high=110.0, low=90.0, close=105.0)
        assert abs(pivots["pivot"] - 101.667) < 0.01
        assert abs(pivots["s1"] - (2 * 101.667 - 110)) < 0.01  # 93.333
        assert abs(pivots["r1"] - (2 * 101.667 - 90)) < 0.01   # 113.333


class TestCamarillaPivots:
    def test_standard_calculation(self) -> None:
        pivots = compute_camarilla_pivots(high=110.0, low=90.0, close=105.0)
        r = 110.0 - 90.0  # range = 20
        assert abs(pivots["s1"] - (105.0 - r * 1.1 / 12)) < 0.01
        assert abs(pivots["r1"] - (105.0 + r * 1.1 / 12)) < 0.01
        assert abs(pivots["s3"] - (105.0 - r * 1.1 / 4)) < 0.01
        assert abs(pivots["r3"] - (105.0 + r * 1.1 / 4)) < 0.01


class TestFibonacciPivots:
    def test_standard_calculation(self) -> None:
        pivots = compute_fibonacci_pivots(high=110.0, low=90.0, close=105.0)
        pp = (110.0 + 90.0 + 105.0) / 3  # 101.667
        r = 110.0 - 90.0  # 20
        assert abs(pivots["pivot"] - pp) < 0.01
        assert abs(pivots["s1"] - (pp - 0.382 * r)) < 0.01
        assert abs(pivots["r1"] - (pp + 0.382 * r)) < 0.01


# --- Full session levels ---

class TestComputeSessionLevels:
    def test_computes_all_level_types(self) -> None:
        # Prior session bars
        prior_bars = [
            _make_bar(1000.0, 6600, 6680, 6590, 6650, 10000),
            _make_bar(1900.0, 6650, 6695, 6630, 6670, 12000),
            _make_bar(2800.0, 6670, 6690, 6640, 6660, 11000),
        ]
        # Current session bars (after gap)
        current_bars = [
            _make_bar(20000.0, 6665, 6680, 6655, 6675, 8000),
            _make_bar(20900.0, 6675, 6690, 6660, 6685, 9000),
            _make_bar(21800.0, 6685, 6700, 6670, 6695, 7000),
        ]
        all_bars = prior_bars + current_bars

        levels = compute_session_levels(all_bars, gap_seconds=14400)

        assert levels is not None
        # Prior day levels
        assert levels["prior_day_high"] == 6695.0
        assert levels["prior_day_low"] == 6590.0
        assert levels["prior_day_close"] == 6660.0

        # Current session
        assert levels["session_open"] == 6665.0
        assert levels["session_high"] == 6700.0
        assert levels["session_low"] == 6655.0

        # VWAP should be present
        assert "session_vwap" in levels
        assert levels["session_vwap"] is not None

        # Pivots should be present
        assert "classic_pivots" in levels
        assert "fibonacci_pivots" in levels
        assert "camarilla_pivots" in levels

    def test_returns_none_for_insufficient_data(self) -> None:
        # Only one session, no prior day data
        bars = [_make_bar(1000.0, 100, 110, 90, 105, 500)]
        levels = compute_session_levels(bars, gap_seconds=14400)
        assert levels is None

    def test_returns_none_for_empty_bars(self) -> None:
        assert compute_session_levels([], gap_seconds=14400) is None
