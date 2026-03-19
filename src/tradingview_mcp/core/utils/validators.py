from __future__ import annotations
import os
from typing import Set

ALLOWED_TIMEFRAMES: Set[str] = {"5m", "15m", "1h", "4h", "1D", "1W", "1M"}
EXCHANGE_SCREENER = {
    "all": "crypto",
    "huobi": "crypto",
    "kucoin": "crypto",
    "coinbase": "crypto",
    "gateio": "crypto",
    "binance": "crypto",
    "bitfinex": "crypto",
    "bitget": "crypto",
    "bybit": "crypto",
    "okx": "crypto",
    "bist": "turkey",
    "nasdaq": "america",
    # Malaysia Stock Market Support
    "bursa": "malaysia",
    "myx": "malaysia",
    "klse": "malaysia",
    "ace": "malaysia",      # ACE Market (Access, Certainty, Efficiency)
    "leap": "malaysia",     # LEAP Market (Leading Entrepreneur Accelerator Platform)
    # Hong Kong Stock Market Support
    "hkex": "hongkong",     # Hong Kong Exchange
    "hk": "hongkong",       # Hong Kong (alternate)
    "hsi": "hongkong",      # Hang Seng Index constituents
    "nyse": "america",
    "cme_mini": "futures",
    "cme": "futures",
    "cbot": "futures",
    "cboe": "cfd",
    "sp": "cfd",
    "tvc": "cfd",
    "amex": "america",
    "tsx": "canada",
}

EXCHANGE_ASSET_TYPE = {
    "all": "crypto",
    "huobi": "crypto",
    "kucoin": "crypto",
    "coinbase": "crypto",
    "gateio": "crypto",
    "binance": "crypto",
    "bitfinex": "crypto",
    "bitget": "crypto",
    "bybit": "crypto",
    "okx": "crypto",
    "bist": "stock",
    "nasdaq": "stock",
    "bursa": "stock",
    "myx": "stock",
    "klse": "stock",
    "ace": "stock",
    "leap": "stock",
    "hkex": "stock",
    "hk": "stock",
    "hsi": "index",
    "nyse": "stock",
    "cme_mini": "futures",
    "cme": "futures",
    "cbot": "futures",
    "cboe": "index",
    "sp": "index",
    "tvc": "index",
    "amex": "etf",
    "tsx": "stock",
}

# Get absolute path to coinlist directory relative to this module
# This file is at: src/tradingview_mcp/core/utils/validators.py
# We want: src/tradingview_mcp/coinlist/
_this_file = __file__
_utils_dir = os.path.dirname(_this_file)  # core/utils
_core_dir = os.path.dirname(_utils_dir)   # core  
_package_dir = os.path.dirname(_core_dir) # tradingview_mcp
COINLIST_DIR = os.path.join(_package_dir, 'coinlist')


def sanitize_timeframe(tf: str, default: str = "5m") -> str:
    if not tf:
        return default
    tfs = tf.strip()
    return tfs if tfs in ALLOWED_TIMEFRAMES else default


def sanitize_exchange(ex: str, default: str = "kucoin") -> str:
    if not ex:
        return default
    exs = ex.strip().lower()
    return exs if exs in EXCHANGE_SCREENER else default


def get_asset_type(exchange: str) -> str:
    if not exchange:
        return "crypto"
    exs = exchange.strip().lower()
    return EXCHANGE_ASSET_TYPE.get(exs, "crypto")


def is_crypto_exchange(exchange: str) -> bool:
    return get_asset_type(exchange) == "crypto"
