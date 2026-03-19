from __future__ import annotations

from typing import Any, Dict

from tradingview_mcp.tools import stocks


class DummyMCP:
    def __init__(self) -> None:
        self.tools: Dict[str, Any] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def _sample_pivot_levels() -> Dict[str, Any]:
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


def test_register_stocks_tools_exposes_required_tool_names() -> None:
    mcp = DummyMCP()
    stocks.register_stocks_tools(mcp)

    required_names = {
        "stocks_top_gainers",
        "stocks_top_losers",
        "stocks_bollinger_scan",
        "stocks_analysis",
        "stocks_volume_breakout",
        "stocks_smart_scanner",
        "stocks_levels",
    }
    assert required_names.issubset(set(mcp.tools.keys()))


def test_stocks_analysis_uses_analyze_single(monkeypatch) -> None:
    mcp = DummyMCP()
    stocks.register_stocks_tools(mcp)
    stocks_analysis = mcp.tools["stocks_analysis"]

    called: Dict[str, Any] = {}

    def fake_analyze_single(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
        called["symbol"] = symbol
        called["exchange"] = exchange
        called["timeframe"] = timeframe
        called["tv_session_id"] = tv_session_id
        return {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "metrics": {"change": 1.23},
        }

    monkeypatch.setattr("tradingview_mcp.tools.stocks.analyze_single", fake_analyze_single)

    result = stocks_analysis(symbol="AAPL", exchange="NASDAQ", timeframe="15m", tv_session_id="session-1")

    assert result["symbol"] == "AAPL"
    assert result["exchange"] == "NASDAQ"
    assert result["timeframe"] == "15m"
    assert called == {
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "timeframe": "15m",
        "tv_session_id": "session-1",
    }


def test_stocks_levels_maps_structured_levels(monkeypatch) -> None:
    mcp = DummyMCP()
    stocks.register_stocks_tools(mcp)
    stocks_levels = mcp.tools["stocks_levels"]

    pivot_levels = _sample_pivot_levels()

    def fake_analyze_single(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "metrics": {"pivot_levels": pivot_levels},
        }

    monkeypatch.setattr("tradingview_mcp.tools.stocks.analyze_single", fake_analyze_single)

    result = stocks_levels(symbol="AAPL", exchange="NASDAQ", timeframe="1D")

    assert result["pivot_levels"] == pivot_levels
    assert set(result["levels"].keys()) == {"Classic", "Fibonacci", "Camarilla"}
    assert result["levels"]["Classic"] == pivot_levels["classic"]
    assert result["levels"]["Fibonacci"] == pivot_levels["fibonacci"]
    assert result["levels"]["Camarilla"] == pivot_levels["camarilla"]
