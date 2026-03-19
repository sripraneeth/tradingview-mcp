from __future__ import annotations

from typing import Any

from tradingview_mcp.tools.news import register_news_tools


class DummyMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def test_register_news_tools_registers_required_names() -> None:
    mcp = DummyMCP()
    register_news_tools(mcp)

    required_names = {
        "news_market_sentiment",
        "news_ticker_impact",
        "news_breaking",
    }
    assert required_names.issubset(set(mcp.tools.keys()))


def test_news_unavailable_returns_config_error_shape(monkeypatch) -> None:
    mcp = DummyMCP()
    register_news_tools(mcp)

    monkeypatch.setattr("tradingview_mcp.tools.news.is_news_available", lambda: False)

    cases = [
        ("news_market_sentiment", {"category": "general", "limit": 5}),
        ("news_ticker_impact", {"symbol": "AAPL", "limit": 5}),
        ("news_breaking", {"limit": 5}),
    ]

    for tool_name, kwargs in cases:
        result = mcp.tools[tool_name](**kwargs)
        assert isinstance(result, dict)
        assert result["error"] is True
        assert result["code"] == "news_unavailable"
        assert result["function"] == tool_name
        assert isinstance(result.get("message"), str)
        assert result["message"]


def test_news_market_sentiment_aggregation_with_mocked_provider(monkeypatch) -> None:
    mcp = DummyMCP()
    register_news_tools(mcp)
    news_market_sentiment = mcp.tools["news_market_sentiment"]

    monkeypatch.setattr("tradingview_mcp.tools.news.is_news_available", lambda: True)
    monkeypatch.setattr(
        "tradingview_mcp.tools.news.get_market_news",
        lambda category, limit: [
            {"headline": "Bullish 1", "sentiment_score": 0.6},
            {"headline": "Bullish 2", "sentiment_score": 0.2},
            {"headline": "Bearish 1", "sentiment_score": -0.4},
            {"headline": "Neutral 1", "sentiment_score": 0.0},
            {"headline": "Unscored", "sentiment_score": None},
        ],
    )

    result = news_market_sentiment(category="GENERAL", limit=10)

    assert result["category"] == "general"
    assert result["limit"] == 10
    assert result["count"] == 5
    assert isinstance(result["items"], list)

    sentiment = result["sentiment"]
    assert sentiment["scored_count"] == 4
    assert sentiment["positive_count"] == 2
    assert sentiment["negative_count"] == 1
    assert sentiment["neutral_count"] == 1
    assert sentiment["average_sentiment_score"] == 0.1
