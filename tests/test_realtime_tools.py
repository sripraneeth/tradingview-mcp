from __future__ import annotations

from unittest.mock import patch, MagicMock
import time

import pytest

from tradingview_mcp.tools import realtime


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator


class TestRegisterRealtimeTools:
    def test_registers_all_required_tools(self) -> None:
        mcp = DummyMCP()
        realtime.register_realtime_tools(mcp)
        required = {"realtime_levels", "realtime_bars", "realtime_analysis"}
        assert required.issubset(set(mcp.tools.keys()))


class TestRealtimeBars:
    def setup_method(self) -> None:
        self.mcp = DummyMCP()
        realtime.register_realtime_tools(self.mcp)
        self.tool = self.mcp.tools["realtime_bars"]

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_allows_empty_session_id(self, mock_get_provider) -> None:
        fake_bars = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500},
        ]
        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = fake_bars
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", count=100, tv_session_id="")
        assert "error" not in result
        assert result["bar_count"] == 1

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_bars_on_success(self, mock_get_provider) -> None:
        fake_bars = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500},
            {"timestamp": 1900, "open": 105, "high": 115, "low": 95, "close": 110, "volume": 600},
        ]
        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = fake_bars
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", count=100, tv_session_id="test_session")

        assert result["symbol"] == "CME_MINI:ES1!"
        assert result["timeframe"] == "15m"
        assert len(result["bars"]) == 2
        assert result["bar_count"] == 2

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_error_from_provider(self, mock_get_provider) -> None:
        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = {"error": "Session expired"}
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", count=100, tv_session_id="test")
        assert result == {"error": "Session expired"}


class TestRealtimeLevels:
    def setup_method(self) -> None:
        self.mcp = DummyMCP()
        realtime.register_realtime_tools(self.mcp)
        self.tool = self.mcp.tools["realtime_levels"]

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_allows_empty_session_id(self, mock_get_provider) -> None:
        fake_levels = {
            "prior_day_high": 6695.0,
            "session_vwap": 6680.0,
            "symbol": "CME_MINI:ES1!",
            "bar_count": 50,
        }
        mock_provider = MagicMock()
        mock_provider.get_session_levels.return_value = fake_levels
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="30m", tv_session_id="")
        assert "error" not in result
        assert result["prior_day_high"] == 6695.0

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_levels_on_success(self, mock_get_provider) -> None:
        fake_levels = {
            "prior_day_high": 6695.0,
            "prior_day_low": 6590.0,
            "prior_day_close": 6660.0,
            "session_open": 6665.0,
            "session_high": 6700.0,
            "session_low": 6655.0,
            "session_vwap": 6680.0,
            "opening_range": {"high": 6680.0, "low": 6655.0},
            "classic_pivots": {"pivot": 6648.33},
            "fibonacci_pivots": {"pivot": 6648.33},
            "camarilla_pivots": {"s1": 6650.0},
            "symbol": "CME_MINI:ES1!",
            "bar_count": 50,
        }
        mock_provider = MagicMock()
        mock_provider.get_session_levels.return_value = fake_levels
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="30m", tv_session_id="test")
        assert result["prior_day_high"] == 6695.0
        assert result["session_vwap"] == 6680.0


class TestRealtimeAnalysis:
    def setup_method(self) -> None:
        self.mcp = DummyMCP()
        realtime.register_realtime_tools(self.mcp)
        self.tool = self.mcp.tools["realtime_analysis"]

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_allows_empty_session_id(self, mock_get_provider) -> None:
        fake_bars = []
        for i in range(30):
            fake_bars.append({
                "timestamp": 1000 + i * 900,
                "open": 100 + i * 0.5,
                "high": 102 + i * 0.5,
                "low": 98 + i * 0.5,
                "close": 101 + i * 0.5,
                "volume": 1000 + i * 10,
            })

        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = fake_bars
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", tv_session_id="")
        assert "error" not in result
        assert "analysis" in result

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_analysis_on_success(self, mock_get_provider) -> None:
        # Generate 30 bars for indicator computation
        fake_bars = []
        for i in range(30):
            fake_bars.append({
                "timestamp": 1000 + i * 900,
                "open": 100 + i * 0.5,
                "high": 102 + i * 0.5,
                "low": 98 + i * 0.5,
                "close": 101 + i * 0.5,
                "volume": 1000 + i * 10,
            })

        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = fake_bars
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", tv_session_id="test")

        assert result["symbol"] == "CME_MINI:ES1!"
        assert "analysis" in result
        analysis = result["analysis"]
        assert "rsi" in analysis
        assert "sma_20" in analysis
        assert "latest_bar" in result
