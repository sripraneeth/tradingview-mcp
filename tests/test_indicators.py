from tradingview_mcp.core.services.indicators import (
    compute_composite_signals,
    compute_expanded_metrics,
    compute_pivot_levels,
)


def test_compute_expanded_metrics_includes_required_fields() -> None:
    indicators = {
        "open": 100,
        "close": 110,
        "SMA20": 105,
        "BB.upper": 115,
        "BB.lower": 95,
        "EMA10": 109,
        "EMA20": 108,
        "EMA50": 106,
        "EMA100": 104,
        "EMA200": 102,
        "RSI": 45,
        "MACD.macd": 1.2,
        "MACD.signal": 1.0,
        "Stoch.K": 40,
        "Stoch.D": 42,
        "CCI20": -50,
        "W.R": -60,
        "ADX": 28,
        "Supertrend": 107,
        "Pivot.M.Classic.Middle": 105,
        "Pivot.M.Classic.S1": 100,
        "Pivot.M.Classic.R1": 110,
    }

    result = compute_expanded_metrics(indicators)
    assert result is not None

    required_top_level_fields = {
        "price",
        "change",
        "bbw",
        "rating",
        "signal",
        "composite_signals",
        "pivot_levels",
    }
    assert required_top_level_fields.issubset(result.keys())

    composite_required = {
        "trend_strength",
        "adx",
        "oscillator_score",
        "confluence_signal",
        "confluence_confidence",
        "buy_votes",
        "sell_votes",
    }
    assert composite_required.issubset(result["composite_signals"].keys())


def test_compute_expanded_metrics_returns_none_when_open_or_close_missing() -> None:
    assert compute_expanded_metrics({"close": 110}) is None
    assert compute_expanded_metrics({"open": 100}) is None


def test_compute_composite_signals_required_fields_and_oscillator_bounds() -> None:
    # Extreme values to ensure bounded oscillator score
    metrics = {
        "ADX": 80,
        "RSI": -1000,
        "Stoch.K": -1000,
        "Stoch.D": -1000,
        "CCI20": -10000,
        "W.R": -1000,
        "EMA10": 120,
        "EMA20": 110,
        "EMA50": 100,
        "EMA100": 90,
        "EMA200": 80,
        "MACD.macd": 2,
        "MACD.signal": 1,
        "price": 130,
        "Supertrend": 100,
    }

    result = compute_composite_signals(metrics)

    required_fields = {
        "trend_strength",
        "adx",
        "oscillator_score",
        "confluence_signal",
        "confluence_confidence",
        "buy_votes",
        "sell_votes",
    }
    assert required_fields.issubset(result.keys())
    assert -100 <= result["oscillator_score"] <= 100


def test_compute_pivot_levels_returns_expected_structure() -> None:
    indicators = {
        "Pivot.M.Classic.Middle": 100,
        "Pivot.M.Classic.S1": 99,
        "Pivot.M.Classic.S2": 98,
        "Pivot.M.Classic.S3": 97,
        "Pivot.M.Classic.R1": 101,
        "Pivot.M.Classic.R2": 102,
        "Pivot.M.Classic.R3": 103,
        "Pivot.M.Fibonacci.Middle": 200,
        "Pivot.M.Fibonacci.S1": 199,
        "Pivot.M.Fibonacci.S2": 198,
        "Pivot.M.Fibonacci.S3": 197,
        "Pivot.M.Fibonacci.R1": 201,
        "Pivot.M.Fibonacci.R2": 202,
        "Pivot.M.Fibonacci.R3": 203,
        "Pivot.M.Camarilla.Middle": 300,
        "Pivot.M.Camarilla.S1": 299,
        "Pivot.M.Camarilla.S2": 298,
        "Pivot.M.Camarilla.S3": 297,
        "Pivot.M.Camarilla.R1": 301,
        "Pivot.M.Camarilla.R2": 302,
        "Pivot.M.Camarilla.R3": 303,
    }

    result = compute_pivot_levels(indicators)

    assert {"classic", "fibonacci", "camarilla"}.issubset(result.keys())
    for key in ("classic", "fibonacci", "camarilla"):
        assert {"middle", "support", "resistance"}.issubset(result[key].keys())
        assert {"S1", "S2", "S3"}.issubset(result[key]["support"].keys())
        assert {"R1", "R2", "R3"}.issubset(result[key]["resistance"].keys())
