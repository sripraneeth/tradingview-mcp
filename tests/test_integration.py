from __future__ import annotations

import os
from typing import Any

import pytest

from tradingview_mcp.tools.crypto import register_crypto_tools
from tradingview_mcp.tools.futures import register_futures_tools
from tradingview_mcp.tools.indices import register_indices_tools
from tradingview_mcp.tools.stocks import register_stocks_tools


class DummyMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


RUN_LIVE_TESTS = os.environ.get("RUN_LIVE_TESTS") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_LIVE_TESTS,
    reason="Live integration tests are disabled by default. Set RUN_LIVE_TESTS=1 to enable.",
)


def test_live_crypto_smoke() -> None:
    mcp = DummyMCP()
    register_crypto_tools(mcp)

    result = mcp.tools["crypto_top_gainers"](exchange="KUCOIN", timeframe="15m", limit=1)

    assert isinstance(result, list)
    if result:
        row = result[0]
        assert isinstance(row, dict)
        assert {"symbol", "changePercent", "indicators"}.issubset(set(row.keys()))


def test_live_stocks_smoke() -> None:
    mcp = DummyMCP()
    register_stocks_tools(mcp)

    result = mcp.tools["stocks_top_gainers"](exchange="NASDAQ", timeframe="15m", limit=1)

    assert isinstance(result, list)
    if result:
        row = result[0]
        assert isinstance(row, dict)
        assert isinstance(row.get("symbol"), str)


def test_live_futures_smoke() -> None:
    mcp = DummyMCP()
    register_futures_tools(mcp)

    result = mcp.tools["futures_top_gainers"](exchange="CME_MINI", timeframe="15m", limit=1)

    assert isinstance(result, list)
    if result:
        row = result[0]
        assert isinstance(row, dict)
        assert isinstance(row.get("symbol"), str)


def test_live_indices_smoke() -> None:
    mcp = DummyMCP()
    register_indices_tools(mcp)

    result = mcp.tools["indices_bollinger_scan"](exchange="CBOE", timeframe="4h", limit=1)

    assert isinstance(result, list)
    if result:
        row = result[0]
        assert isinstance(row, dict)
        assert isinstance(row.get("symbol"), str)
