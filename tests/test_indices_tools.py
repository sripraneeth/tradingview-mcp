from __future__ import annotations

from typing import Any, Dict

from tradingview_mcp.tools import indices


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
            "middle": 5000.0,
            "support": {"S1": 4990.0, "S2": 4980.0, "S3": 4970.0},
            "resistance": {"R1": 5010.0, "R2": 5020.0, "R3": 5030.0},
        },
        "fibonacci": {
            "middle": 6000.0,
            "support": {"S1": 5990.0, "S2": 5980.0, "S3": 5970.0},
            "resistance": {"R1": 6010.0, "R2": 6020.0, "R3": 6030.0},
        },
        "camarilla": {
            "middle": 7000.0,
            "support": {"S1": 6990.0, "S2": 6980.0, "S3": 6970.0},
            "resistance": {"R1": 7010.0, "R2": 7020.0, "R3": 7030.0},
        },
    }


def test_register_indices_tools_exposes_required_tool_names() -> None:
    mcp = DummyMCP()
    indices.register_indices_tools(mcp)

    required_names = {
        "indices_analysis",
        "indices_bollinger_scan",
        "indices_rating_filter",
        "indices_levels",
    }
    assert required_names.issubset(set(mcp.tools.keys()))


def test_indices_analysis_uses_screener_fallback_when_direct_fails(monkeypatch) -> None:
    mcp = DummyMCP()
    indices.register_indices_tools(mcp)
    indices_analysis = mcp.tools["indices_analysis"]

    calls: Dict[str, int] = {"direct": 0, "fallback": 0}

    def fake_direct(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
        calls["direct"] += 1
        return {"error": "direct failure"}

    def fake_fallback(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
        calls["fallback"] += 1
        return {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "metrics": {"change": 0.25},
            "fallback": "screener_query",
        }

    monkeypatch.setattr("tradingview_mcp.tools.indices._analyze_with_ta", fake_direct)
    monkeypatch.setattr("tradingview_mcp.tools.indices._analyze_with_query", fake_fallback)

    result = indices_analysis(symbol="SPX", exchange="CBOE", timeframe="15m", tv_session_id="session-2")

    assert calls == {"direct": 1, "fallback": 1}
    assert result["symbol"] == "CBOE:SPX"
    assert result["exchange"] == "cboe"
    assert result["timeframe"] == "15m"
    assert result["fallback"] == "screener_query"


def test_indices_levels_maps_structured_levels_from_pivot_data(monkeypatch) -> None:
    mcp = DummyMCP()
    indices.register_indices_tools(mcp)
    indices_levels = mcp.tools["indices_levels"]

    pivot_levels = _sample_pivot_levels()

    def fake_analyze_single(symbol: str, exchange: str, timeframe: str, tv_session_id: str = "") -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "metrics": {"pivot_levels": pivot_levels},
        }

    monkeypatch.setattr("tradingview_mcp.tools.indices.analyze_single", fake_analyze_single)

    result = indices_levels(symbol="SPX", exchange="CBOE", timeframe="1D")

    assert result["pivot_levels"] == pivot_levels
    assert set(result["levels"].keys()) == {"Classic", "Fibonacci", "Camarilla"}
    assert result["levels"]["Classic"] == pivot_levels["classic"]
    assert result["levels"]["Fibonacci"] == pivot_levels["fibonacci"]
    assert result["levels"]["Camarilla"] == pivot_levels["camarilla"]
