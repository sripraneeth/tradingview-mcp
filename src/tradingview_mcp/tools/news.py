from __future__ import annotations

from typing import Any

from tradingview_mcp.core.services.news_provider import (
    get_market_news,
    get_news_sentiment,
    get_ticker_news,
    is_news_available,
)


def _clamp_limit(limit: int, max_limit: int = 50, default: int = 20) -> int:
    try:
        value = int(limit)
    except Exception:
        value = default
    return max(1, min(value, max_limit))


def _config_error(function_name: str) -> dict[str, Any]:
    return {
        "error": True,
        "code": "news_unavailable",
        "function": function_name,
        "message": "Finnhub API is unavailable. Ensure FINNHUB_API_KEY is set and finnhub-python is installed.",
    }


def _sentiment_aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [item.get("sentiment_score") for item in items if isinstance(item.get("sentiment_score"), (int, float))]

    positive = sum(1 for score in scores if score > 0)
    negative = sum(1 for score in scores if score < 0)
    neutral = sum(1 for score in scores if score == 0)

    average_score = (sum(float(score) for score in scores) / len(scores)) if scores else None

    return {
        "scored_count": len(scores),
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "average_sentiment_score": round(average_score, 6) if isinstance(average_score, float) else None,
    }


def register_news_tools(mcp) -> None:
    @mcp.tool()
    def news_market_sentiment(category: str = "general", limit: int = 20) -> dict[str, Any]:
        """Return market news with aggregated sentiment summary."""
        if not is_news_available():
            return _config_error("news_market_sentiment")

        safe_limit = _clamp_limit(limit, max_limit=100, default=20)
        news = get_market_news(category=category, limit=safe_limit)

        if news and isinstance(news[0], dict) and news[0].get("error"):
            return {
                "error": True,
                "code": news[0].get("code", "api_error"),
                "function": "news_market_sentiment",
                "message": news[0].get("message", "Failed to fetch market news"),
            }

        return {
            "category": (category or "general").strip().lower() or "general",
            "limit": safe_limit,
            "count": len(news),
            "sentiment": _sentiment_aggregate(news),
            "items": news,
        }

    @mcp.tool()
    def news_ticker_impact(symbol: str, limit: int = 10) -> dict[str, Any]:
        """Return ticker-specific news and impact/sentiment summary."""
        if not is_news_available():
            return _config_error("news_ticker_impact")

        safe_symbol = (symbol or "").strip().upper()
        safe_limit = _clamp_limit(limit, max_limit=50, default=10)

        news = get_ticker_news(symbol=safe_symbol, days_back=7, limit=safe_limit)
        if news and isinstance(news[0], dict) and news[0].get("error"):
            return {
                "error": True,
                "code": news[0].get("code", "api_error"),
                "function": "news_ticker_impact",
                "message": news[0].get("message", "Failed to fetch ticker news"),
            }

        provider_sentiment = get_news_sentiment(safe_symbol)
        provider_error = isinstance(provider_sentiment, dict) and provider_sentiment.get("error")

        news_aggregate = _sentiment_aggregate(news)
        endpoint_score = provider_sentiment.get("sentiment_score") if isinstance(provider_sentiment, dict) else None
        effective_score = endpoint_score if isinstance(endpoint_score, (int, float)) else news_aggregate["average_sentiment_score"]

        if not isinstance(effective_score, (int, float)):
            impact_label = "unknown"
        elif effective_score > 0:
            impact_label = "bullish"
        elif effective_score < 0:
            impact_label = "bearish"
        else:
            impact_label = "neutral"

        return {
            "symbol": safe_symbol,
            "limit": safe_limit,
            "count": len(news),
            "impact": {
                "label": impact_label,
                "effective_sentiment_score": round(float(effective_score), 6) if isinstance(effective_score, (int, float)) else None,
            },
            "sentiment": {
                **news_aggregate,
                "provider_sentiment_score": endpoint_score if isinstance(endpoint_score, (int, float)) else None,
                "provider_sentiment_available": not provider_error,
            },
            "items": news,
        }

    @mcp.tool()
    def news_breaking(limit: int = 10) -> dict[str, Any]:
        """Return latest general market breaking news with sentiment summary."""
        if not is_news_available():
            return _config_error("news_breaking")

        safe_limit = _clamp_limit(limit, max_limit=50, default=10)
        news = get_market_news(category="general", limit=safe_limit)

        if news and isinstance(news[0], dict) and news[0].get("error"):
            return {
                "error": True,
                "code": news[0].get("code", "api_error"),
                "function": "news_breaking",
                "message": news[0].get("message", "Failed to fetch breaking news"),
            }

        return {
            "category": "general",
            "limit": safe_limit,
            "count": len(news),
            "sentiment": _sentiment_aggregate(news),
            "items": news,
        }


__all__ = ["register_news_tools"]
