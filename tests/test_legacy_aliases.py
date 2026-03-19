from __future__ import annotations

import tradingview_mcp.server as server


def test_legacy_and_crypto_names_are_both_registered() -> None:
    tool_names = set(server.mcp._tool_manager._tools.keys())

    pairs = {
        "top_gainers": "crypto_top_gainers",
        "top_losers": "crypto_top_losers",
        "bollinger_scan": "crypto_bollinger_scan",
        "rating_filter": "crypto_rating_filter",
        "coin_analysis": "crypto_analysis",
        "consecutive_candles_scan": "crypto_consecutive_candles_scan",
        "advanced_candle_pattern": "crypto_advanced_candle_pattern",
        "volume_breakout_scanner": "crypto_volume_breakout_scanner",
        "volume_confirmation_analysis": "crypto_volume_confirmation_analysis",
        "smart_volume_scanner": "crypto_smart_volume_scanner",
    }

    for legacy, crypto in pairs.items():
        assert legacy in tool_names
        assert crypto in tool_names


def test_top_gainers_alias_forwards_to_crypto_impl(monkeypatch) -> None:
    called: dict[str, object] = {}

    def fake_crypto_top_gainers(**kwargs):
        called["kwargs"] = kwargs
        return [{"symbol": "KUCOIN:AAAUSDT", "changePercent": 1.23, "indicators": {}}]

    def fake_crypto_fn(name: str):
        called["name"] = name
        return fake_crypto_top_gainers

    monkeypatch.setattr(server, "_crypto_fn", fake_crypto_fn)

    result = server.top_gainers(exchange="BINANCE", timeframe="1h", limit=3)

    assert called["name"] == "crypto_top_gainers"
    assert called["kwargs"] == {"exchange": "BINANCE", "timeframe": "1h", "limit": 3}
    assert result == [{"symbol": "KUCOIN:AAAUSDT", "changePercent": 1.23, "indicators": {}}]
