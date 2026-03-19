import pytest

from tradingview_mcp.core.services.symbols import format_symbol
from tradingview_mcp.core.utils.validators import (
    EXCHANGE_SCREENER,
    get_asset_type,
    is_crypto_exchange,
)


def test_exchange_registry_includes_expected_new_keys_and_screener_mappings() -> None:
    expected_mappings = {
        # Malaysia market aliases
        "bursa": "malaysia",
        "myx": "malaysia",
        "klse": "malaysia",
        "ace": "malaysia",
        "leap": "malaysia",
        # Hong Kong market aliases
        "hkex": "hongkong",
        "hk": "hongkong",
        "hsi": "hongkong",
    }

    for exchange, screener in expected_mappings.items():
        assert exchange in EXCHANGE_SCREENER
        assert EXCHANGE_SCREENER[exchange] == screener


@pytest.mark.parametrize(
    ("exchange", "expected_asset_type", "expected_is_crypto"),
    [
        ("binance", "crypto", True),
        ("nasdaq", "stock", False),
        ("cme", "futures", False),
        ("hsi", "index", False),
    ],
)
def test_get_asset_type_and_is_crypto_exchange(
    exchange: str,
    expected_asset_type: str,
    expected_is_crypto: bool,
) -> None:
    assert get_asset_type(exchange) == expected_asset_type
    assert is_crypto_exchange(exchange) is expected_is_crypto


def test_format_symbol_existing_prefixed_symbol_unchanged() -> None:
    assert format_symbol("binance", "KRAKEN:ETHUSD") == "KRAKEN:ETHUSD"


def test_format_symbol_crypto_btc_defaults_to_binance_usdt_pair() -> None:
    assert format_symbol("binance", "btc") == "BINANCE:BTCUSDT"


def test_format_symbol_stock_aapl_uses_nasdaq_prefix_without_usdt() -> None:
    assert format_symbol("nasdaq", "aapl") == "NASDAQ:AAPL"
