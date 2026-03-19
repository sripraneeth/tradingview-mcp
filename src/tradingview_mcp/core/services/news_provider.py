from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any


FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")


def _get_api_key() -> str | None:
    return os.environ.get("FINNHUB_API_KEY")


def _error_dict(function: str, message: str, *, code: str = "api_error") -> dict[str, Any]:
    return {
        "error": True,
        "code": code,
        "function": function,
        "message": message,
    }


def _get_client():
    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        import finnhub  # type: ignore

        return finnhub.Client(api_key=api_key)
    except Exception:
        return None


def _normalize_news_item(item: dict[str, Any]) -> dict[str, Any]:
    sentiment_score: Any = item.get("sentiment")
    if sentiment_score is None:
        sentiment_score = item.get("sentimentScore")

    return {
        "headline": item.get("headline"),
        "source": item.get("source"),
        "url": item.get("url"),
        "datetime": item.get("datetime"),
        "summary": item.get("summary"),
        "sentiment_score": sentiment_score,
    }


def is_news_available() -> bool:
    return _get_client() is not None


def get_market_news(category: str = "general", limit: int = 20) -> list[dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [
            _error_dict(
                "get_market_news",
                "Finnhub API is unavailable. Ensure FINNHUB_API_KEY is set and finnhub-python is installed.",
                code="news_unavailable",
            )
        ]

    try:
        raw_news = client.general_news(category=category)
        if not isinstance(raw_news, list):
            return []

        normalized = [_normalize_news_item(item) for item in raw_news if isinstance(item, dict)]
        return normalized[: max(0, int(limit))]
    except Exception as exc:
        return [_error_dict("get_market_news", str(exc))]


def get_ticker_news(symbol: str, days_back: int = 7, limit: int = 10) -> list[dict[str, Any]]:
    client = _get_client()
    if client is None:
        return [
            _error_dict(
                "get_ticker_news",
                "Finnhub API is unavailable. Ensure FINNHUB_API_KEY is set and finnhub-python is installed.",
                code="news_unavailable",
            )
        ]

    symbol = (symbol or "").strip().upper()
    if not symbol:
        return [_error_dict("get_ticker_news", "symbol is required", code="validation_error")]

    try:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(1, int(days_back)))
        raw_news = client.company_news(symbol=symbol, _from=start_date.isoformat(), to=end_date.isoformat())

        if not isinstance(raw_news, list):
            return []

        normalized = [_normalize_news_item(item) for item in raw_news if isinstance(item, dict)]
        return normalized[: max(0, int(limit))]
    except Exception as exc:
        return [_error_dict("get_ticker_news", str(exc))]


def get_news_sentiment(symbol: str) -> dict[str, Any]:
    client = _get_client()
    if client is None:
        return _error_dict(
            "get_news_sentiment",
            "Finnhub API is unavailable. Ensure FINNHUB_API_KEY is set and finnhub-python is installed.",
            code="news_unavailable",
        )

    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _error_dict("get_news_sentiment", "symbol is required", code="validation_error")

    try:
        data = client.news_sentiment(symbol=symbol)
        if not isinstance(data, dict):
            return {
                "symbol": symbol,
                "sentiment_score": None,
                "raw": {},
            }

        sentiment_score = None
        sentiment = data.get("sentiment")
        if isinstance(sentiment, dict):
            sentiment_score = sentiment.get("score")

        if sentiment_score is None:
            buzz = data.get("buzz")
            if isinstance(buzz, dict):
                sentiment_score = buzz.get("buzz")

        return {
            "symbol": symbol,
            "sentiment_score": sentiment_score,
            "raw": data,
        }
    except Exception as exc:
        return _error_dict("get_news_sentiment", str(exc))
