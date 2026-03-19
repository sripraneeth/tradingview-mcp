from __future__ import annotations

from tradingview_mcp.tools.crypto import register_crypto_tools


class DummyMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name: str | None = None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


def test_register_crypto_tools_registers_required_names() -> None:
    mcp = DummyMCP()
    register_crypto_tools(mcp)

    required = {
        "crypto_top_gainers",
        "crypto_top_losers",
        "crypto_bollinger_scan",
        "crypto_rating_filter",
        "crypto_analysis",
        "crypto_consecutive_candles_scan",
        "crypto_advanced_candle_pattern",
        "crypto_volume_breakout_scanner",
        "crypto_volume_confirmation_analysis",
        "crypto_smart_volume_scanner",
    }

    assert required.issubset(set(mcp.tools.keys()))


def test_crypto_top_gainers_offline_structure(monkeypatch) -> None:
    mcp = DummyMCP()
    register_crypto_tools(mcp)
    top_gainers = mcp.tools["crypto_top_gainers"]

    fake_rows = [
        {
            "symbol": "KUCOIN:AAAUSDT",
            "changePercent": 12.34,
            "indicators": {
                "open": 1.0,
                "close": 1.1234,
                "SMA20": 1.02,
                "BB_upper": 1.2,
                "BB_lower": 0.9,
                "EMA50": 1.01,
                "RSI": 64.2,
                "volume": 123456,
            },
        }
    ]

    monkeypatch.setattr(
        "tradingview_mcp.tools.crypto._fetch_trending_analysis",
        lambda exchange, timeframe, limit, tv_session_id="": fake_rows,
    )

    result = top_gainers(exchange="kucoin", timeframe="15m", limit=1)

    assert isinstance(result, list)
    assert len(result) == 1
    row = result[0]
    assert set(row.keys()) == {"symbol", "changePercent", "indicators"}
    assert row["symbol"] == "KUCOIN:AAAUSDT"
    assert isinstance(row["changePercent"], float)
    assert isinstance(row["indicators"], dict)
    assert {"open", "close", "SMA20", "BB_upper", "BB_lower", "EMA50", "RSI", "volume"}.issubset(
        set(row["indicators"].keys())
    )
