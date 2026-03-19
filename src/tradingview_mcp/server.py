from __future__ import annotations

import argparse
import os
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from tradingview_mcp.tools.crypto import register_crypto_tools
from tradingview_mcp.tools.futures import register_futures_tools
from tradingview_mcp.tools.indices import register_indices_tools
from tradingview_mcp.tools.stocks import register_stocks_tools


mcp = FastMCP(
    name="TradingView Screener",
    instructions=(
        "TradingView screener utilities for crypto, stocks, futures, and indices. "
        "Includes legacy aliases for backward compatibility."
    ),
)


def _register_all_tools() -> None:
    register_crypto_tools(mcp)
    register_stocks_tools(mcp)
    register_futures_tools(mcp)
    register_indices_tools(mcp)


_register_all_tools()


def _crypto_fn(name: str) -> Callable[..., Any]:
    tool = mcp._tool_manager.get_tool(name)
    if tool is None or not callable(getattr(tool, "fn", None)):
        raise RuntimeError(f"Required crypto tool not registered: {name}")
    return tool.fn


@mcp.tool()
def top_gainers(exchange: str = "KUCOIN", timeframe: str = "15m", limit: int = 25) -> list[dict]:
    """Legacy alias for crypto_top_gainers."""
    return _crypto_fn("crypto_top_gainers")(exchange=exchange, timeframe=timeframe, limit=limit)


@mcp.tool()
def top_losers(exchange: str = "KUCOIN", timeframe: str = "15m", limit: int = 25) -> list[dict]:
    """Legacy alias for crypto_top_losers."""
    return _crypto_fn("crypto_top_losers")(exchange=exchange, timeframe=timeframe, limit=limit)


@mcp.tool()
def bollinger_scan(exchange: str = "KUCOIN", timeframe: str = "4h", bbw_threshold: float = 0.04, limit: int = 50) -> list[dict]:
    """Legacy alias for crypto_bollinger_scan."""
    return _crypto_fn("crypto_bollinger_scan")(
        exchange=exchange,
        timeframe=timeframe,
        bbw_threshold=bbw_threshold,
        limit=limit,
    )


@mcp.tool()
def rating_filter(exchange: str = "KUCOIN", timeframe: str = "5m", rating: int = 2, limit: int = 25) -> list[dict]:
    """Legacy alias for crypto_rating_filter."""
    return _crypto_fn("crypto_rating_filter")(exchange=exchange, timeframe=timeframe, rating=rating, limit=limit)


@mcp.tool()
def coin_analysis(symbol: str, exchange: str = "KUCOIN", timeframe: str = "15m") -> dict:
    """Legacy alias for crypto_analysis."""
    return _crypto_fn("crypto_analysis")(symbol=symbol, exchange=exchange, timeframe=timeframe)


@mcp.tool()
def consecutive_candles_scan(
    exchange: str = "KUCOIN",
    timeframe: str = "15m",
    pattern_type: str = "bullish",
    candle_count: int = 3,
    min_growth: float = 2.0,
    limit: int = 20,
) -> dict:
    """Legacy alias for crypto_consecutive_candles_scan."""
    return _crypto_fn("crypto_consecutive_candles_scan")(
        exchange=exchange,
        timeframe=timeframe,
        pattern_type=pattern_type,
        candle_count=candle_count,
        min_growth=min_growth,
        limit=limit,
    )


@mcp.tool()
def advanced_candle_pattern(
    exchange: str = "KUCOIN",
    base_timeframe: str = "15m",
    pattern_length: int = 3,
    min_size_increase: float = 10.0,
    limit: int = 15,
) -> dict:
    """Legacy alias for crypto_advanced_candle_pattern."""
    return _crypto_fn("crypto_advanced_candle_pattern")(
        exchange=exchange,
        base_timeframe=base_timeframe,
        pattern_length=pattern_length,
        min_size_increase=min_size_increase,
        limit=limit,
    )


@mcp.tool()
def volume_breakout_scanner(
    exchange: str = "KUCOIN",
    timeframe: str = "15m",
    volume_multiplier: float = 2.0,
    price_change_min: float = 3.0,
    limit: int = 25,
) -> list[dict]:
    """Legacy alias for crypto_volume_breakout_scanner."""
    return _crypto_fn("crypto_volume_breakout_scanner")(
        exchange=exchange,
        timeframe=timeframe,
        volume_multiplier=volume_multiplier,
        price_change_min=price_change_min,
        limit=limit,
    )


@mcp.tool()
def volume_confirmation_analysis(symbol: str, exchange: str = "KUCOIN", timeframe: str = "15m") -> dict:
    """Legacy alias for crypto_volume_confirmation_analysis."""
    return _crypto_fn("crypto_volume_confirmation_analysis")(symbol=symbol, exchange=exchange, timeframe=timeframe)


@mcp.tool()
def smart_volume_scanner(
    exchange: str = "KUCOIN",
    min_volume_ratio: float = 2.0,
    min_price_change: float = 2.0,
    rsi_range: str = "any",
    limit: int = 20,
) -> list[dict]:
    """Legacy alias for crypto_smart_volume_scanner."""
    return _crypto_fn("crypto_smart_volume_scanner")(
        exchange=exchange,
        min_volume_ratio=min_volume_ratio,
        min_price_change=min_price_change,
        rsi_range=rsi_range,
        limit=limit,
    )


@mcp.resource("exchanges://list")
def exchanges_list() -> str:
    """List available exchanges grouped by asset type categories."""
    categories: dict[str, set[str]] = {
        "Crypto": {
            "KUCOIN",
            "BINANCE",
            "BYBIT",
            "BITGET",
            "OKX",
            "COINBASE",
            "GATEIO",
            "HUOBI",
            "BITFINEX",
            "KRAKEN",
            "BITSTAMP",
        },
        "Stocks": {"NASDAQ", "NYSE", "BIST", "BURSA", "MYX", "KLSE", "ACE", "LEAP", "HKEX", "HK", "AMEX", "TSX"},
        "ETFs": {"AMEX", "TSX", "SP"},
        "Futures": {"CME_MINI", "CME", "CBOT", "CBOE"},
        "Indices": {"INDICES", "HSI", "SP", "TVC"},
    }

    exchange_to_categories: dict[str, tuple[str, ...]] = {
        "KUCOIN": ("Crypto",),
        "BINANCE": ("Crypto",),
        "BYBIT": ("Crypto",),
        "BITGET": ("Crypto",),
        "OKX": ("Crypto",),
        "COINBASE": ("Crypto",),
        "GATEIO": ("Crypto",),
        "HUOBI": ("Crypto",),
        "BITFINEX": ("Crypto",),
        "KRAKEN": ("Crypto",),
        "BITSTAMP": ("Crypto",),
        "NASDAQ": ("Stocks",),
        "NYSE": ("Stocks",),
        "BIST": ("Stocks",),
        "BURSA": ("Stocks",),
        "MYX": ("Stocks",),
        "KLSE": ("Stocks",),
        "ACE": ("Stocks",),
        "LEAP": ("Stocks",),
        "HKEX": ("Stocks",),
        "HK": ("Stocks",),
        "AMEX": ("Stocks", "ETFs"),
        "TSX": ("Stocks", "ETFs"),
        "CME_MINI": ("Futures",),
        "CME": ("Futures",),
        "CBOT": ("Futures",),
        "CBOE": ("Futures",),
        "HSI": ("Indices",),
        "SP": ("Indices", "ETFs"),
        "TVC": ("Indices",),
        "INDICES": ("Indices",),
    }

    try:
        coinlist_dir = os.path.join(os.path.dirname(__file__), "coinlist")
        if os.path.exists(coinlist_dir):
            for filename in os.listdir(coinlist_dir):
                if not filename.endswith(".txt"):
                    continue
                exchange_name = filename[:-4].upper()
                if exchange_name in {"ALL", ""}:
                    continue

                target_categories = exchange_to_categories.get(exchange_name)
                if target_categories is None:
                    # Best-effort heuristics for newly added coinlist files.
                    if exchange_name.startswith(("CME", "CBOT", "CBOE")):
                        target_categories = ("Futures",)
                    elif "INDEX" in exchange_name or exchange_name in {"HSI", "SP", "TVC"}:
                        target_categories = ("Indices",)
                    elif exchange_name in {"AMEX", "TSX"}:
                        target_categories = ("Stocks", "ETFs")
                    elif exchange_name in {"KUCOIN", "BINANCE", "BYBIT", "BITGET", "OKX", "COINBASE", "GATEIO", "HUOBI", "BITFINEX"}:
                        target_categories = ("Crypto",)
                    else:
                        target_categories = ("Stocks",)

                for category in target_categories:
                    categories[category].add(exchange_name)
    except Exception:
        # Keep defaults to remain robust even if coinlist scanning fails.
        pass

    order = ["Crypto", "Stocks", "ETFs", "Futures", "Indices"]
    lines = ["Available exchanges by asset type:"]
    lines.extend(f"{name}: {', '.join(sorted(categories[name]))}" for name in order)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="TradingView Screener MCP server")
    parser.add_argument("transport", choices=["stdio", "streamable-http"], default="stdio", nargs="?", help="Transport (default stdio)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()

    if os.environ.get("DEBUG_MCP"):
        import sys

        print(f"[DEBUG_MCP] pkg cwd={os.getcwd()} argv={sys.argv} file={__file__}", file=sys.stderr, flush=True)

    if args.transport == "stdio":
        mcp.run()
    else:
        try:
            mcp.settings.host = args.host
            mcp.settings.port = args.port
        except Exception:
            pass
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
