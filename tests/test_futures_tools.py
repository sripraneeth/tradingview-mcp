from types import SimpleNamespace

from tradingview_mcp.tools import futures


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def _sample_pivot_levels() -> dict:
    return {
        "classic": {
            "middle": 100.0,
            "support": {"S1": 99.0, "S2": 98.0, "S3": 97.0},
            "resistance": {"R1": 101.0, "R2": 102.0, "R3": 103.0},
        },
        "fibonacci": {
            "middle": 200.0,
            "support": {"S1": 199.0, "S2": 198.0, "S3": 197.0},
            "resistance": {"R1": 201.0, "R2": 202.0, "R3": 203.0},
        },
        "camarilla": {
            "middle": 300.0,
            "support": {"S1": 299.0, "S2": 298.0, "S3": 297.0},
            "resistance": {"R1": 301.0, "R2": 302.0, "R3": 303.0},
        },
    }


def test_register_futures_tools_contains_required_names() -> None:
    mcp = DummyMCP()
    futures.register_futures_tools(mcp)

    required = {
        "futures_analysis",
        "futures_top_gainers",
        "futures_top_losers",
        "futures_volume_breakout",
        "futures_levels",
        "futures_orb_predictor",
    }
    assert required.issubset(set(mcp.tools.keys()))


def test_futures_orb_predictor_returns_levels_with_monkeypatched_get_multiple_analysis(monkeypatch) -> None:
    mcp = DummyMCP()
    futures.register_futures_tools(mcp)
    futures_orb_predictor = mcp.tools["futures_orb_predictor"]

    fake_item = SimpleNamespace(
        indicators={
            "open": 100.0,
            "high": 104.0,
            "low": 96.0,
            "ATR": 2.0,
        }
    )

    def fake_get_multiple_analysis(*, screener, interval, symbols, cookies=None):
        assert screener == "futures"
        assert interval == "15m"
        assert symbols == ["CME_MINI:ES1!"]
        return {"CME_MINI:ES1!": fake_item}

    monkeypatch.setattr("tradingview_mcp.tools.futures.TRADINGVIEW_TA_AVAILABLE", True)
    monkeypatch.setattr("tradingview_mcp.tools.shared.TRADINGVIEW_TA_AVAILABLE", True)
    monkeypatch.setattr("tradingview_mcp.tools.shared.get_multiple_analysis", fake_get_multiple_analysis)

    result = futures_orb_predictor(symbol="ES1!", exchange="CME_MINI", timeframe="15m")

    assert result["symbol"] == "CME_MINI:ES1!"
    assert result["exchange"] == "cme_mini"
    assert result["timeframe"] == "15m"
    assert "orb_levels" in result
    assert result["orb_levels"]["range_high"] == 102.0
    assert result["orb_levels"]["range_low"] == 98.0


def test_futures_levels_returns_structured_levels(monkeypatch) -> None:
    mcp = DummyMCP()
    futures.register_futures_tools(mcp)
    futures_levels = mcp.tools["futures_levels"]

    pivot_levels = _sample_pivot_levels()
    analysis_payload = {
        "symbol": "ES1!",
        "exchange": "CME_MINI",
        "timeframe": "15m",
        "metrics": {"pivot_levels": pivot_levels},
    }

    monkeypatch.setattr("tradingview_mcp.tools.futures.analyze_single", lambda **kwargs: analysis_payload)

    result = futures_levels(symbol="ES1!", exchange="CME_MINI", timeframe="15m")

    assert result["symbol"] == "ES1!"
    assert result["exchange"] == "cme_mini"
    assert result["timeframe"] == "15m"
    assert result["pivot_levels"] == pivot_levels
    assert set(result["levels"].keys()) == {"Classic", "Fibonacci", "Camarilla"}
    assert result["levels"]["Classic"] == pivot_levels["classic"]
    assert result["levels"]["Fibonacci"] == pivot_levels["fibonacci"]
    assert result["levels"]["Camarilla"] == pivot_levels["camarilla"]


def test_futures_levels_error_passthrough(monkeypatch) -> None:
    mcp = DummyMCP()
    futures.register_futures_tools(mcp)
    futures_levels = mcp.tools["futures_levels"]

    error_payload = {
        "error": "No data found",
        "symbol": "UNKNOWN",
        "exchange": "TEST",
        "timeframe": "15m",
    }
    monkeypatch.setattr("tradingview_mcp.tools.futures.analyze_single", lambda **kwargs: error_payload)

    result = futures_levels(symbol="UNKNOWN", exchange="CME_MINI", timeframe="15m")

    assert result == error_payload
