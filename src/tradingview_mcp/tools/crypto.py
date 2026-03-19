from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

from tradingview_mcp.core.services.coinlist import load_symbols
from tradingview_mcp.core.services.indicators import compute_metrics
from tradingview_mcp.core.utils.validators import EXCHANGE_SCREENER, sanitize_exchange, sanitize_timeframe

try:
    from tradingview_ta import get_multiple_analysis

    TRADINGVIEW_TA_AVAILABLE = True
except ImportError:
    TRADINGVIEW_TA_AVAILABLE = False

try:
    from tradingview_screener import Query
    from tradingview_screener.column import Column

    TRADINGVIEW_SCREENER_AVAILABLE = True
except ImportError:
    TRADINGVIEW_SCREENER_AVAILABLE = False


class IndicatorMap(TypedDict, total=False):
    open: Optional[float]
    close: Optional[float]
    SMA20: Optional[float]
    BB_upper: Optional[float]
    BB_lower: Optional[float]
    EMA50: Optional[float]
    RSI: Optional[float]
    volume: Optional[float]


class Row(TypedDict):
    symbol: str
    changePercent: float
    indicators: IndicatorMap


def _build_tv_cookies(tv_session_id: str = "") -> Optional[Dict[str, str]]:
    session_id = (tv_session_id or "").strip()
    if not session_id:
        return None
    return {"sessionid": session_id}


def _safe_get_multiple_analysis(
    *,
    screener: str,
    interval: str,
    symbols: List[str],
    tv_session_id: str = "",
) -> Any:
    if not TRADINGVIEW_TA_AVAILABLE:
        raise RuntimeError("tradingview_ta is missing; run `uv sync`.")

    cookies = _build_tv_cookies(tv_session_id)
    if cookies:
        try:
            return get_multiple_analysis(
                screener=screener,
                interval=interval,
                symbols=symbols,
                cookies=cookies,
            )
        except TypeError:
            pass

    return get_multiple_analysis(
        screener=screener,
        interval=interval,
        symbols=symbols,
    )


def _fetch_bollinger_analysis(
    exchange: str,
    timeframe: str = "4h",
    limit: int = 50,
    bbw_filter: Optional[float] = None,
    tv_session_id: str = "",
) -> List[Row]:
    """Fetch analysis using tradingview_ta with bollinger band logic from the original screener."""
    if not TRADINGVIEW_TA_AVAILABLE:
        raise RuntimeError("tradingview_ta is missing; run `uv sync`.")

    symbols = load_symbols(exchange)
    if not symbols:
        raise RuntimeError(f"No symbols found for exchange: {exchange}")

    symbols = symbols[: limit * 2]
    screener = EXCHANGE_SCREENER.get(exchange, "crypto")

    try:
        analysis = _safe_get_multiple_analysis(
            screener=screener,
            interval=timeframe,
            symbols=symbols,
            tv_session_id=tv_session_id,
        )
    except Exception as e:
        raise RuntimeError(f"Analysis failed: {str(e)}")

    rows: List[Row] = []

    for key, value in analysis.items():
        try:
            if value is None:
                continue

            indicators = value.indicators
            metrics = compute_metrics(indicators)

            if not metrics or metrics.get("bbw") is None:
                continue

            if bbw_filter is not None and (metrics["bbw"] >= bbw_filter or metrics["bbw"] <= 0):
                continue

            if not (indicators.get("EMA50") and indicators.get("RSI")):
                continue

            rows.append(
                Row(
                    symbol=key,
                    changePercent=metrics["change"],
                    indicators=IndicatorMap(
                        open=metrics.get("open"),
                        close=metrics.get("price"),
                        SMA20=indicators.get("SMA20"),
                        BB_upper=indicators.get("BB.upper"),
                        BB_lower=indicators.get("BB.lower"),
                        EMA50=indicators.get("EMA50"),
                        RSI=indicators.get("RSI"),
                        volume=indicators.get("volume"),
                    ),
                )
            )
        except (TypeError, ZeroDivisionError, KeyError):
            continue

    rows.sort(key=lambda x: x["changePercent"], reverse=True)
    return rows[:limit]


def _fetch_trending_analysis(
    exchange: str,
    timeframe: str = "5m",
    filter_type: str = "",
    rating_filter: Optional[int] = None,
    limit: int = 50,
    tv_session_id: str = "",
) -> List[Row]:
    """Fetch trending coins analysis similar to the original app's trending endpoint."""
    if not TRADINGVIEW_TA_AVAILABLE:
        raise RuntimeError("tradingview_ta is missing; run `uv sync`.")

    symbols = load_symbols(exchange)
    if not symbols:
        raise RuntimeError(f"No symbols found for exchange: {exchange}")

    batch_size = 200
    all_coins: List[Row] = []
    screener = EXCHANGE_SCREENER.get(exchange, "crypto")

    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i : i + batch_size]

        try:
            analysis = _safe_get_multiple_analysis(
                screener=screener,
                interval=timeframe,
                symbols=batch_symbols,
                tv_session_id=tv_session_id,
            )
        except Exception:
            continue

        for key, value in analysis.items():
            try:
                if value is None:
                    continue

                indicators = value.indicators
                metrics = compute_metrics(indicators)

                if not metrics or metrics.get("bbw") is None:
                    continue

                if filter_type == "rating" and rating_filter is not None:
                    if metrics["rating"] != rating_filter:
                        continue

                all_coins.append(
                    Row(
                        symbol=key,
                        changePercent=metrics["change"],
                        indicators=IndicatorMap(
                            open=metrics.get("open"),
                            close=metrics.get("price"),
                            SMA20=indicators.get("SMA20"),
                            BB_upper=indicators.get("BB.upper"),
                            BB_lower=indicators.get("BB.lower"),
                            EMA50=indicators.get("EMA50"),
                            RSI=indicators.get("RSI"),
                            volume=indicators.get("volume"),
                        ),
                    )
                )
            except (TypeError, ZeroDivisionError, KeyError):
                continue

    all_coins.sort(key=lambda x: x["changePercent"], reverse=True)
    return all_coins[:limit]


def _calculate_candle_pattern_score(indicators: dict, pattern_length: int, min_increase: float) -> dict:
    """Calculate candle pattern score based on available indicators."""
    try:
        open_price = indicators.get("open", 0)
        close_price = indicators.get("close", 0)
        high_price = indicators.get("high", 0)
        low_price = indicators.get("low", 0)
        volume = indicators.get("volume", 0)
        rsi = indicators.get("RSI", 50)

        if not all([open_price, close_price, high_price, low_price]):
            return {"detected": False, "score": 0}

        candle_body = abs(close_price - open_price)
        candle_range = high_price - low_price
        body_ratio = candle_body / candle_range if candle_range > 0 else 0
        price_change = ((close_price - open_price) / open_price) * 100

        score = 0
        details = []

        if body_ratio > 0.7:
            score += 2
            details.append("Strong candle body")
        elif body_ratio > 0.5:
            score += 1
            details.append("Moderate candle body")

        if abs(price_change) >= min_increase:
            score += 2
            details.append(f"Strong momentum ({price_change:.1f}%)")
        elif abs(price_change) >= min_increase / 2:
            score += 1
            details.append(f"Moderate momentum ({price_change:.1f}%)")

        if volume > 5000:
            score += 1
            details.append("Good volume")

        if (price_change > 0 and 50 < rsi < 80) or (price_change < 0 and 20 < rsi < 50):
            score += 1
            details.append("RSI momentum aligned")

        ema50 = indicators.get("EMA50", close_price)
        if (price_change > 0 and close_price > ema50) or (price_change < 0 and close_price < ema50):
            score += 1
            details.append("Trend alignment")

        detected = score >= 3

        return {
            "detected": detected,
            "score": score,
            "details": details,
            "price": round(close_price, 6),
            "total_change": round(price_change, 3),
            "body_ratio": round(body_ratio, 3),
            "volume": volume,
        }
    except Exception as e:
        return {"detected": False, "score": 0, "error": str(e)}


def _fetch_multi_timeframe_patterns(
    exchange: str,
    symbols: List[str],
    base_tf: str,
    length: int,
    min_increase: float,
    tv_session_id: str = "",
) -> List[dict]:
    """Fetch multi-timeframe pattern data using tradingview-screener."""
    try:
        if not TRADINGVIEW_SCREENER_AVAILABLE:
            return []

        tf_map = {"5m": "5", "15m": "15", "1h": "60", "4h": "240", "1D": "1D"}
        tv_interval = tf_map.get(base_tf, "15")

        cols = [
            f"open|{tv_interval}",
            f"close|{tv_interval}",
            f"high|{tv_interval}",
            f"low|{tv_interval}",
            f"volume|{tv_interval}",
            "RSI",
        ]

        q = Query().set_markets("crypto").select(*cols)
        q = q.where(Column("exchange") == exchange.upper())
        q = q.limit(len(symbols))

        _, df = q.get_scanner_data(cookies=_build_tv_cookies(tv_session_id))
        if df is None or df.empty:
            return []

        results = []

        for _, row in df.iterrows():
            symbol = row.get("ticker", "")

            try:
                open_val = row.get(f"open|{tv_interval}")
                close_val = row.get(f"close|{tv_interval}")
                high_val = row.get(f"high|{tv_interval}")
                low_val = row.get(f"low|{tv_interval}")
                volume_val = row.get(f"volume|{tv_interval}", 0)
                rsi_val = row.get("RSI", 50)

                if not all([open_val, close_val, high_val, low_val]):
                    continue

                pattern_score = _calculate_candle_pattern_score(
                    {
                        "open": open_val,
                        "close": close_val,
                        "high": high_val,
                        "low": low_val,
                        "volume": volume_val,
                        "RSI": rsi_val,
                    },
                    length,
                    min_increase,
                )

                if pattern_score["detected"]:
                    results.append(
                        {
                            "symbol": symbol,
                            "pattern_score": pattern_score["score"],
                            "price": pattern_score["price"],
                            "change": pattern_score["total_change"],
                            "body_ratio": pattern_score["body_ratio"],
                            "volume": volume_val,
                            "rsi": round(rsi_val, 2),
                            "details": pattern_score["details"],
                        }
                    )
            except Exception:
                continue

        return sorted(results, key=lambda x: x["pattern_score"], reverse=True)
    except Exception:
        return []


def register_crypto_tools(mcp: Any) -> None:
    """Register crypto-prefixed MCP tools."""

    @mcp.tool(name="crypto_top_gainers")
    def crypto_top_gainers(
        exchange: str = "KUCOIN",
        timeframe: str = "15m",
        limit: int = 25,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Return top gainers for an exchange and timeframe using bollinger band analysis.

        Args:
            exchange: Exchange name like KUCOIN, BINANCE, BYBIT, etc.
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            limit: Number of rows to return (max 50)
        """
        exchange = sanitize_exchange(exchange, "KUCOIN")
        timeframe = sanitize_timeframe(timeframe, "15m")
        limit = max(1, min(limit, 50))

        rows = _fetch_trending_analysis(exchange, timeframe=timeframe, limit=limit, tv_session_id=tv_session_id)
        return [
            {
                "symbol": row["symbol"],
                "changePercent": row["changePercent"],
                "indicators": dict(row["indicators"]),
            }
            for row in rows
        ]

    @mcp.tool(name="crypto_top_losers")
    def crypto_top_losers(
        exchange: str = "KUCOIN",
        timeframe: str = "15m",
        limit: int = 25,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Return top losers for an exchange and timeframe using bollinger band analysis."""
        exchange = sanitize_exchange(exchange, "KUCOIN")
        timeframe = sanitize_timeframe(timeframe, "15m")
        limit = max(1, min(limit, 50))

        rows = _fetch_trending_analysis(exchange, timeframe=timeframe, limit=limit, tv_session_id=tv_session_id)
        rows.sort(key=lambda x: x["changePercent"])

        return [
            {
                "symbol": row["symbol"],
                "changePercent": row["changePercent"],
                "indicators": dict(row["indicators"]),
            }
            for row in rows[:limit]
        ]

    @mcp.tool(name="crypto_bollinger_scan")
    def crypto_bollinger_scan(
        exchange: str = "KUCOIN",
        timeframe: str = "4h",
        bbw_threshold: float = 0.04,
        limit: int = 50,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Scan for coins with low Bollinger Band Width (squeeze detection).

        Args:
            exchange: Exchange name like KUCOIN, BINANCE, BYBIT, etc.
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            bbw_threshold: Maximum BBW value to filter (default 0.04)
            limit: Number of rows to return (max 100)
        """
        exchange = sanitize_exchange(exchange, "KUCOIN")
        timeframe = sanitize_timeframe(timeframe, "4h")
        limit = max(1, min(limit, 100))

        rows = _fetch_bollinger_analysis(
            exchange,
            timeframe=timeframe,
            bbw_filter=bbw_threshold,
            limit=limit,
            tv_session_id=tv_session_id,
        )
        return [
            {
                "symbol": row["symbol"],
                "changePercent": row["changePercent"],
                "indicators": dict(row["indicators"]),
            }
            for row in rows
        ]

    @mcp.tool(name="crypto_rating_filter")
    def crypto_rating_filter(
        exchange: str = "KUCOIN",
        timeframe: str = "5m",
        rating: int = 2,
        limit: int = 25,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Filter coins by Bollinger Band rating.

        Args:
            exchange: Exchange name like KUCOIN, BINANCE, BYBIT, etc.
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            rating: BB rating (-3 to +3): -3=Strong Sell, -2=Sell, -1=Weak Sell, 1=Weak Buy, 2=Buy, 3=Strong Buy
            limit: Number of rows to return (max 50)
        """
        exchange = sanitize_exchange(exchange, "KUCOIN")
        timeframe = sanitize_timeframe(timeframe, "5m")
        rating = max(-3, min(3, rating))
        limit = max(1, min(limit, 50))

        rows = _fetch_trending_analysis(
            exchange,
            timeframe=timeframe,
            filter_type="rating",
            rating_filter=rating,
            limit=limit,
            tv_session_id=tv_session_id,
        )
        return [
            {
                "symbol": row["symbol"],
                "changePercent": row["changePercent"],
                "indicators": dict(row["indicators"]),
            }
            for row in rows
        ]

    @mcp.tool(name="crypto_analysis")
    def crypto_analysis(symbol: str, exchange: str = "KUCOIN", timeframe: str = "15m", tv_session_id: str = "") -> dict:
        """Get detailed analysis for a specific coin on specified exchange and timeframe.

        Args:
            symbol: Coin symbol (e.g., "ACEUSDT", "BTCUSDT")
            exchange: Exchange name (BINANCE, KUCOIN, etc.)
            timeframe: Time interval (5m, 15m, 1h, 4h, 1D, 1W, 1M)

        Returns:
            Detailed coin analysis with all indicators and metrics
        """
        try:
            exchange = sanitize_exchange(exchange, "KUCOIN")
            timeframe = sanitize_timeframe(timeframe, "15m")

            if ":" not in symbol:
                full_symbol = f"{exchange.upper()}:{symbol.upper()}"
            else:
                full_symbol = symbol.upper()

            screener = EXCHANGE_SCREENER.get(exchange, "crypto")

            try:
                analysis = _safe_get_multiple_analysis(
                    screener=screener,
                    interval=timeframe,
                    symbols=[full_symbol],
                    tv_session_id=tv_session_id,
                )

                if full_symbol not in analysis or analysis[full_symbol] is None:
                    return {
                        "error": f"No data found for {symbol} on {exchange}",
                        "symbol": symbol,
                        "exchange": exchange,
                        "timeframe": timeframe,
                    }

                data = analysis[full_symbol]
                indicators = data.indicators

                metrics = compute_metrics(indicators)
                if not metrics:
                    return {
                        "error": f"Could not compute metrics for {symbol}",
                        "symbol": symbol,
                        "exchange": exchange,
                        "timeframe": timeframe,
                    }

                macd = indicators.get("MACD.macd", 0)
                macd_signal = indicators.get("MACD.signal", 0)
                adx = indicators.get("ADX", 0)
                stoch_k = indicators.get("Stoch.K", 0)
                stoch_d = indicators.get("Stoch.D", 0)

                volume = indicators.get("volume", 0)

                high = indicators.get("high", 0)
                low = indicators.get("low", 0)
                open_price = indicators.get("open", 0)
                close_price = indicators.get("close", 0)

                return {
                    "symbol": full_symbol,
                    "exchange": exchange,
                    "timeframe": timeframe,
                    "timestamp": "real-time",
                    "price_data": {
                        "current_price": metrics["price"],
                        "open": round(open_price, 6) if open_price else None,
                        "high": round(high, 6) if high else None,
                        "low": round(low, 6) if low else None,
                        "close": round(close_price, 6) if close_price else None,
                        "change_percent": metrics["change"],
                        "volume": volume,
                    },
                    "bollinger_analysis": {
                        "rating": metrics["rating"],
                        "signal": metrics["signal"],
                        "bbw": metrics["bbw"],
                        "bb_upper": round(indicators.get("BB.upper", 0), 6),
                        "bb_middle": round(indicators.get("SMA20", 0), 6),
                        "bb_lower": round(indicators.get("BB.lower", 0), 6),
                        "position": "Above Upper"
                        if close_price > indicators.get("BB.upper", 0)
                        else "Below Lower"
                        if close_price < indicators.get("BB.lower", 0)
                        else "Within Bands",
                    },
                    "technical_indicators": {
                        "rsi": round(indicators.get("RSI", 0), 2),
                        "rsi_signal": "Overbought"
                        if indicators.get("RSI", 0) > 70
                        else "Oversold"
                        if indicators.get("RSI", 0) < 30
                        else "Neutral",
                        "sma20": round(indicators.get("SMA20", 0), 6),
                        "ema50": round(indicators.get("EMA50", 0), 6),
                        "ema200": round(indicators.get("EMA200", 0), 6),
                        "macd": round(macd, 6),
                        "macd_signal": round(macd_signal, 6),
                        "macd_divergence": round(macd - macd_signal, 6),
                        "adx": round(adx, 2),
                        "trend_strength": "Strong" if adx > 25 else "Weak",
                        "stoch_k": round(stoch_k, 2),
                        "stoch_d": round(stoch_d, 2),
                    },
                    "market_sentiment": {
                        "overall_rating": metrics["rating"],
                        "buy_sell_signal": metrics["signal"],
                        "volatility": "High"
                        if metrics["bbw"] > 0.05
                        else "Medium"
                        if metrics["bbw"] > 0.02
                        else "Low",
                        "momentum": "Bullish" if metrics["change"] > 0 else "Bearish",
                    },
                }
            except Exception as e:
                return {
                    "error": f"Analysis failed: {str(e)}",
                    "symbol": symbol,
                    "exchange": exchange,
                    "timeframe": timeframe,
                }
        except Exception as e:
            return {
                "error": f"Coin analysis failed: {str(e)}",
                "symbol": symbol,
                "exchange": exchange,
                "timeframe": timeframe,
            }

    @mcp.tool(name="crypto_consecutive_candles_scan")
    def crypto_consecutive_candles_scan(
        exchange: str = "KUCOIN",
        timeframe: str = "15m",
        pattern_type: str = "bullish",
        candle_count: int = 3,
        min_growth: float = 2.0,
        limit: int = 20,
        tv_session_id: str = "",
    ) -> dict:
        """Scan for coins with consecutive growing/shrinking candles pattern.

        Args:
            exchange: Exchange name (BINANCE, KUCOIN, etc.)
            timeframe: Time interval (5m, 15m, 1h, 4h)
            pattern_type: "bullish" (growing candles) or "bearish" (shrinking candles)
            candle_count: Number of consecutive candles to check (2-5)
            min_growth: Minimum growth percentage for each candle
            limit: Maximum number of results to return

        Returns:
            List of coins with consecutive candle patterns
        """
        try:
            exchange = sanitize_exchange(exchange, "KUCOIN")
            timeframe = sanitize_timeframe(timeframe, "15m")
            candle_count = max(2, min(5, candle_count))
            min_growth = max(0.5, min(20.0, min_growth))
            limit = max(1, min(50, limit))

            symbols = load_symbols(exchange)
            if not symbols:
                return {"error": f"No symbols found for exchange: {exchange}", "exchange": exchange, "timeframe": timeframe}

            symbols = symbols[: min(limit * 3, 200)]
            screener = EXCHANGE_SCREENER.get(exchange, "crypto")

            try:
                analysis = _safe_get_multiple_analysis(
                    screener=screener,
                    interval=timeframe,
                    symbols=symbols,
                    tv_session_id=tv_session_id,
                )

                pattern_coins = []

                for symbol, data in analysis.items():
                    if data is None:
                        continue

                    try:
                        indicators = data.indicators

                        open_price = indicators.get("open")
                        close_price = indicators.get("close")
                        high_price = indicators.get("high")
                        low_price = indicators.get("low")
                        volume = indicators.get("volume", 0)

                        if not all([open_price, close_price, high_price, low_price]):
                            continue

                        current_change = ((close_price - open_price) / open_price) * 100
                        candle_body = abs(close_price - open_price)
                        candle_range = high_price - low_price
                        body_to_range_ratio = candle_body / candle_range if candle_range > 0 else 0

                        rsi = indicators.get("RSI", 50)
                        sma20 = indicators.get("SMA20", close_price)
                        ema50 = indicators.get("EMA50", close_price)

                        price_above_sma = close_price > sma20
                        price_above_ema = close_price > ema50

                        pattern_detected = False
                        pattern_strength = 0

                        if pattern_type == "bullish":
                            conditions = [
                                current_change > min_growth,
                                body_to_range_ratio > 0.6,
                                price_above_sma,
                                rsi > 45 and rsi < 80,
                                volume > 1000,
                            ]
                            pattern_strength = sum(conditions)
                            pattern_detected = pattern_strength >= 3

                        elif pattern_type == "bearish":
                            conditions = [
                                current_change < -min_growth,
                                body_to_range_ratio > 0.6,
                                not price_above_sma,
                                rsi < 55 and rsi > 20,
                                volume > 1000,
                            ]
                            pattern_strength = sum(conditions)
                            pattern_detected = pattern_strength >= 3

                        if pattern_detected:
                            metrics = compute_metrics(indicators)

                            coin_data = {
                                "symbol": symbol,
                                "price": round(close_price, 6),
                                "current_change": round(current_change, 3),
                                "candle_body_ratio": round(body_to_range_ratio, 3),
                                "pattern_strength": pattern_strength,
                                "volume": volume,
                                "bollinger_rating": metrics.get("rating", 0) if metrics else 0,
                                "rsi": round(rsi, 2),
                                "price_levels": {
                                    "open": round(open_price, 6),
                                    "high": round(high_price, 6),
                                    "low": round(low_price, 6),
                                    "close": round(close_price, 6),
                                },
                                "momentum_signals": {
                                    "above_sma20": price_above_sma,
                                    "above_ema50": price_above_ema,
                                    "strong_volume": volume > 5000,
                                },
                            }

                            pattern_coins.append(coin_data)
                    except Exception:
                        continue

                if pattern_type == "bullish":
                    pattern_coins.sort(key=lambda x: (x["pattern_strength"], x["current_change"]), reverse=True)
                else:
                    pattern_coins.sort(key=lambda x: (x["pattern_strength"], -x["current_change"]), reverse=True)

                return {
                    "exchange": exchange,
                    "timeframe": timeframe,
                    "pattern_type": pattern_type,
                    "candle_count": candle_count,
                    "min_growth": min_growth,
                    "total_found": len(pattern_coins),
                    "data": pattern_coins[:limit],
                }
            except Exception as e:
                return {"error": f"Pattern analysis failed: {str(e)}", "exchange": exchange, "timeframe": timeframe}
        except Exception as e:
            return {"error": f"Consecutive candles scan failed: {str(e)}", "exchange": exchange, "timeframe": timeframe}

    @mcp.tool(name="crypto_advanced_candle_pattern")
    def crypto_advanced_candle_pattern(
        exchange: str = "KUCOIN",
        base_timeframe: str = "15m",
        pattern_length: int = 3,
        min_size_increase: float = 10.0,
        limit: int = 15,
        tv_session_id: str = "",
    ) -> dict:
        """Advanced candle pattern analysis using multi-timeframe data.

        Args:
            exchange: Exchange name (BINANCE, KUCOIN, etc.)
            base_timeframe: Base timeframe for analysis (5m, 15m, 1h, 4h)
            pattern_length: Number of consecutive periods to analyze (2-4)
            min_size_increase: Minimum percentage increase in candle size
            limit: Maximum number of results to return

        Returns:
            Coins with progressive candle size increase patterns
        """
        try:
            exchange = sanitize_exchange(exchange, "KUCOIN")
            base_timeframe = sanitize_timeframe(base_timeframe, "15m")
            pattern_length = max(2, min(4, pattern_length))
            min_size_increase = max(5.0, min(50.0, min_size_increase))
            limit = max(1, min(30, limit))

            symbols = load_symbols(exchange)
            if not symbols:
                return {"error": f"No symbols found for exchange: {exchange}", "exchange": exchange}

            symbols = symbols[: min(limit * 2, 100)]

            if TRADINGVIEW_SCREENER_AVAILABLE:
                try:
                    results = _fetch_multi_timeframe_patterns(
                        exchange,
                        symbols,
                        base_timeframe,
                        pattern_length,
                        min_size_increase,
                        tv_session_id=tv_session_id,
                    )

                    return {
                        "exchange": exchange,
                        "base_timeframe": base_timeframe,
                        "pattern_length": pattern_length,
                        "min_size_increase": min_size_increase,
                        "method": "multi-timeframe",
                        "total_found": len(results),
                        "data": results[:limit],
                    }
                except Exception:
                    pass

            screener = EXCHANGE_SCREENER.get(exchange, "crypto")
            analysis = _safe_get_multiple_analysis(
                screener=screener,
                interval=base_timeframe,
                symbols=symbols,
                tv_session_id=tv_session_id,
            )

            pattern_results = []

            for symbol, data in analysis.items():
                if data is None:
                    continue

                try:
                    indicators = data.indicators
                    pattern_score = _calculate_candle_pattern_score(indicators, pattern_length, min_size_increase)

                    if pattern_score["detected"]:
                        metrics = compute_metrics(indicators)

                        result = {
                            "symbol": symbol,
                            "pattern_score": pattern_score["score"],
                            "pattern_details": pattern_score["details"],
                            "current_price": pattern_score["price"],
                            "total_change": pattern_score["total_change"],
                            "volume": indicators.get("volume", 0),
                            "bollinger_rating": metrics.get("rating", 0) if metrics else 0,
                            "technical_strength": {
                                "rsi": round(indicators.get("RSI", 50), 2),
                                "momentum": "Strong" if abs(pattern_score["total_change"]) > min_size_increase else "Moderate",
                                "volume_trend": "High" if indicators.get("volume", 0) > 10000 else "Low",
                            },
                        }

                        pattern_results.append(result)
                except Exception:
                    continue

            pattern_results.sort(key=lambda x: (x["pattern_score"], abs(x["total_change"])), reverse=True)

            return {
                "exchange": exchange,
                "base_timeframe": base_timeframe,
                "pattern_length": pattern_length,
                "min_size_increase": min_size_increase,
                "method": "enhanced-single-timeframe",
                "total_found": len(pattern_results),
                "data": pattern_results[:limit],
            }
        except Exception as e:
            return {"error": f"Advanced pattern analysis failed: {str(e)}", "exchange": exchange, "base_timeframe": base_timeframe}

    @mcp.tool(name="crypto_volume_breakout_scanner")
    def crypto_volume_breakout_scanner(
        exchange: str = "KUCOIN",
        timeframe: str = "15m",
        volume_multiplier: float = 2.0,
        price_change_min: float = 3.0,
        limit: int = 25,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Detect coins with volume breakout + price breakout.

        Args:
            exchange: Exchange name like KUCOIN, BINANCE, BYBIT, etc.
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            volume_multiplier: How many times the volume should be above normal level (default 2.0)
            price_change_min: Minimum price change percentage (default 3.0)
            limit: Number of rows to return (max 50)
        """
        exchange = sanitize_exchange(exchange, "KUCOIN")
        timeframe = sanitize_timeframe(timeframe, "15m")
        volume_multiplier = max(1.5, min(10.0, volume_multiplier))
        price_change_min = max(1.0, min(20.0, price_change_min))
        limit = max(1, min(limit, 50))

        symbols = load_symbols(exchange)
        if not symbols:
            return []

        screener = EXCHANGE_SCREENER.get(exchange, "crypto")
        volume_breakouts = []

        batch_size = 100
        for i in range(0, min(len(symbols), 500), batch_size):
            batch_symbols = symbols[i : i + batch_size]

            try:
                analysis = _safe_get_multiple_analysis(
                    screener=screener,
                    interval=timeframe,
                    symbols=batch_symbols,
                    tv_session_id=tv_session_id,
                )
            except Exception:
                continue

            for symbol, data in analysis.items():
                try:
                    if not data or not hasattr(data, "indicators"):
                        continue

                    indicators = data.indicators

                    volume = indicators.get("volume", 0)
                    close = indicators.get("close", 0)
                    open_price = indicators.get("open", 0)
                    sma20_volume = indicators.get("volume.SMA20", 0)

                    if not all([volume, close, open_price]) or volume <= 0:
                        continue

                    price_change = ((close - open_price) / open_price) * 100 if open_price > 0 else 0

                    if sma20_volume and sma20_volume > 0:
                        volume_ratio = volume / sma20_volume
                    else:
                        avg_volume_estimate = volume / 2
                        volume_ratio = volume / avg_volume_estimate if avg_volume_estimate > 0 else 1

                    if abs(price_change) >= price_change_min and volume_ratio >= volume_multiplier:
                        rsi = indicators.get("RSI", 50)
                        bb_upper = indicators.get("BB.upper", 0)
                        bb_lower = indicators.get("BB.lower", 0)
                        volume_strength = min(10, volume_ratio)

                        volume_breakouts.append(
                            {
                                "symbol": symbol,
                                "changePercent": price_change,
                                "volume_ratio": round(volume_ratio, 2),
                                "volume_strength": round(volume_strength, 1),
                                "current_volume": volume,
                                "breakout_type": "bullish" if price_change > 0 else "bearish",
                                "indicators": {
                                    "close": close,
                                    "RSI": rsi,
                                    "BB_upper": bb_upper,
                                    "BB_lower": bb_lower,
                                    "volume": volume,
                                },
                            }
                        )
                except Exception:
                    continue

        volume_breakouts.sort(key=lambda x: (x["volume_strength"], abs(x["changePercent"])), reverse=True)
        return volume_breakouts[:limit]

    @mcp.tool(name="crypto_volume_confirmation_analysis")
    def crypto_volume_confirmation_analysis(
        symbol: str,
        exchange: str = "KUCOIN",
        timeframe: str = "15m",
        tv_session_id: str = "",
    ) -> dict:
        """Detailed volume confirmation analysis for a specific coin.

        Args:
            symbol: Coin symbol (e.g., BTCUSDT)
            exchange: Exchange name
            timeframe: Time frame for analysis
        """
        exchange = sanitize_exchange(exchange, "KUCOIN")
        timeframe = sanitize_timeframe(timeframe, "15m")

        if not symbol.upper().endswith("USDT"):
            symbol = symbol.upper() + "USDT"

        screener = EXCHANGE_SCREENER.get(exchange, "crypto")

        try:
            analysis = _safe_get_multiple_analysis(
                screener=screener,
                interval=timeframe,
                symbols=[symbol],
                tv_session_id=tv_session_id,
            )

            if not analysis or symbol not in analysis:
                return {"error": f"No data found for {symbol}"}

            data = analysis[symbol]
            if not data or not hasattr(data, "indicators"):
                return {"error": f"No indicator data for {symbol}"}

            indicators = data.indicators

            volume = indicators.get("volume", 0)
            close = indicators.get("close", 0)
            open_price = indicators.get("open", 0)
            high = indicators.get("high", 0)
            low = indicators.get("low", 0)

            price_change = ((close - open_price) / open_price) * 100 if open_price > 0 else 0
            candle_range = ((high - low) / low) * 100 if low > 0 else 0

            sma20_volume = indicators.get("volume.SMA20", 0)
            volume_ratio = volume / sma20_volume if sma20_volume > 0 else 1

            rsi = indicators.get("RSI", 50)
            bb_upper = indicators.get("BB.upper", 0)
            bb_lower = indicators.get("BB.lower", 0)

            signals = []

            if volume_ratio >= 2.0 and abs(price_change) >= 3.0:
                signals.append(f"🚀 STRONG BREAKOUT: {volume_ratio:.1f}x volume + {price_change:.1f}% price")

            if volume_ratio >= 1.5 and abs(price_change) < 1.0:
                signals.append(f"⚠️ VOLUME DIVERGENCE: High volume ({volume_ratio:.1f}x) but low price movement")

            if abs(price_change) >= 2.0 and volume_ratio < 0.8:
                signals.append(f"❌ WEAK SIGNAL: Price moved but volume is low ({volume_ratio:.1f}x)")

            if close > bb_upper and volume_ratio >= 1.5:
                signals.append("💥 BB BREAKOUT CONFIRMED: Upper band breakout + volume confirmation")
            elif close < bb_lower and volume_ratio >= 1.5:
                signals.append("📉 BB SELL CONFIRMED: Lower band breakout + volume confirmation")

            if rsi > 70 and volume_ratio >= 2.0:
                signals.append(f"🔥 OVERBOUGHT + VOLUME: RSI {rsi:.1f} + {volume_ratio:.1f}x volume")
            elif rsi < 30 and volume_ratio >= 2.0:
                signals.append(f"🛒 OVERSOLD + VOLUME: RSI {rsi:.1f} + {volume_ratio:.1f}x volume")

            if volume_ratio >= 3.0:
                volume_strength = "VERY STRONG"
            elif volume_ratio >= 2.0:
                volume_strength = "STRONG"
            elif volume_ratio >= 1.5:
                volume_strength = "MEDIUM"
            elif volume_ratio >= 1.0:
                volume_strength = "NORMAL"
            else:
                volume_strength = "WEAK"

            return {
                "symbol": symbol,
                "price_data": {
                    "close": close,
                    "change_percent": round(price_change, 2),
                    "candle_range_percent": round(candle_range, 2),
                },
                "volume_analysis": {
                    "current_volume": volume,
                    "volume_ratio": round(volume_ratio, 2),
                    "volume_strength": volume_strength,
                    "average_volume": sma20_volume,
                },
                "technical_indicators": {
                    "RSI": round(rsi, 1),
                    "BB_position": "ABOVE" if close > bb_upper else "BELOW" if close < bb_lower else "WITHIN",
                    "BB_upper": bb_upper,
                    "BB_lower": bb_lower,
                },
                "signals": signals,
                "overall_assessment": {
                    "bullish_signals": len([s for s in signals if "🚀" in s or "💥" in s or "🛒" in s]),
                    "bearish_signals": len([s for s in signals if "📉" in s or "❌" in s]),
                    "warning_signals": len([s for s in signals if "⚠️" in s]),
                },
            }
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

    @mcp.tool(name="crypto_smart_volume_scanner")
    def crypto_smart_volume_scanner(
        exchange: str = "KUCOIN",
        min_volume_ratio: float = 2.0,
        min_price_change: float = 2.0,
        rsi_range: str = "any",
        limit: int = 20,
        tv_session_id: str = "",
    ) -> list[dict]:
        """Smart volume + technical analysis combination scanner.

        Args:
            exchange: Exchange name
            min_volume_ratio: Minimum volume multiplier (default 2.0)
            min_price_change: Minimum price change percentage (default 2.0)
            rsi_range: "oversold" (<30), "overbought" (>70), "neutral" (30-70), "any"
            limit: Number of results (max 30)
        """
        exchange = sanitize_exchange(exchange, "KUCOIN")
        min_volume_ratio = max(1.2, min(10.0, min_volume_ratio))
        min_price_change = max(0.5, min(20.0, min_price_change))
        limit = max(1, min(limit, 30))

        volume_breakouts = crypto_volume_breakout_scanner(
            exchange=exchange,
            volume_multiplier=min_volume_ratio,
            price_change_min=min_price_change,
            limit=limit * 2,
            tv_session_id=tv_session_id,
        )

        if not volume_breakouts:
            return []

        filtered_results = []
        for coin in volume_breakouts:
            rsi = coin["indicators"].get("RSI", 50)

            if rsi_range == "oversold" and rsi >= 30:
                continue
            elif rsi_range == "overbought" and rsi <= 70:
                continue
            elif rsi_range == "neutral" and (rsi <= 30 or rsi >= 70):
                continue

            recommendation = ""
            if coin["changePercent"] > 0 and coin["volume_ratio"] >= 2.0:
                if rsi < 70:
                    recommendation = "🚀 STRONG BUY"
                else:
                    recommendation = "⚠️ OVERBOUGHT - CAUTION"
            elif coin["changePercent"] < 0 and coin["volume_ratio"] >= 2.0:
                if rsi > 30:
                    recommendation = "📉 STRONG SELL"
                else:
                    recommendation = "🛒 OVERSOLD - OPPORTUNITY?"

            coin["trading_recommendation"] = recommendation
            filtered_results.append(coin)

        return filtered_results[:limit]


__all__ = ["register_crypto_tools"]
