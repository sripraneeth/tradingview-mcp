from __future__ import annotations

from unittest.mock import patch, MagicMock
import time

import pytest

from tradingview_mcp.core.services.ws_data_provider import (
    WSDataProvider,
    _format_ws_symbol,
)


class TestFormatWsSymbol:
    def test_already_prefixed(self) -> None:
        assert _format_ws_symbol("CME_MINI:ES1!", "CME_MINI") == "CME_MINI:ES1!"

    def test_adds_exchange_prefix(self) -> None:
        assert _format_ws_symbol("ES1!", "CME_MINI") == "CME_MINI:ES1!"

    def test_uppercase_normalization(self) -> None:
        assert _format_ws_symbol("es1!", "cme_mini") == "CME_MINI:ES1!"

    def test_strips_whitespace(self) -> None:
        assert _format_ws_symbol("  NQ1!  ", "CME_MINI") == "CME_MINI:NQ1!"


class TestWSDataProvider:
    def test_get_bars_returns_cached_data(self) -> None:
        provider = WSDataProvider()
        fake_bars = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500}
        ]
        cache_key = ("CME_MINI:ES1!", "15")
        provider._cache[cache_key] = (time.monotonic(), fake_bars)

        result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="test")
        assert result == fake_bars

    def test_get_bars_cache_expired(self) -> None:
        provider = WSDataProvider()
        fake_bars = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500}
        ]
        cache_key = ("CME_MINI:ES1!", "15")
        # Set cache entry 60 seconds in the past (expired)
        provider._cache[cache_key] = (time.monotonic() - 60, fake_bars)

        new_bars = [
            {"timestamp": 2000, "open": 105, "high": 115, "low": 95, "close": 110, "volume": 600}
        ]

        mock_client = MagicMock()
        mock_client.connected = True
        mock_client.get_series.return_value = new_bars
        provider._client = mock_client

        with patch("tradingview_mcp.core.services.ws_data_provider.extract_auth_token", return_value="token"):
            result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="test")

        assert result == new_bars

    @patch("tradingview_mcp.core.services.ws_data_provider.extract_auth_token")
    def test_get_bars_connects_on_first_call(self, mock_auth) -> None:
        mock_auth.return_value = "test_token"

        provider = WSDataProvider()
        mock_client = MagicMock()
        mock_client.connected = False
        mock_client.get_series.return_value = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500}
        ]
        provider._client = mock_client

        result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="sess123")

        mock_client.connect.assert_called_once_with(auth_token="test_token")
        assert len(result) == 1

    @patch("tradingview_mcp.core.services.ws_data_provider.extract_auth_token")
    def test_get_bars_falls_back_to_anonymous_on_auth_failure(self, mock_auth) -> None:
        mock_auth.return_value = None
        provider = WSDataProvider()
        mock_client = MagicMock()
        mock_client.connected = False
        mock_client.get_series.return_value = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500}
        ]
        provider._client = mock_client

        result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="bad_sess")
        assert isinstance(result, list)
        mock_client.connect.assert_called_once_with(auth_token="unauthorized_user_token")

    def test_get_bars_allows_empty_session_id_in_anonymous_mode(self) -> None:
        provider = WSDataProvider()
        mock_client = MagicMock()
        mock_client.connected = False
        mock_client.get_series.return_value = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500}
        ]
        provider._client = mock_client

        result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="")
        assert isinstance(result, list)
        mock_client.connect.assert_called_once_with(auth_token="unauthorized_user_token")

    def test_get_session_levels_delegates_to_level_calc(self) -> None:
        provider = WSDataProvider()

        # Pre-populate cache with bars spanning two sessions
        bars = [
            # Prior session
            {"timestamp": 1000.0, "open": 6600, "high": 6680, "low": 6590, "close": 6650, "volume": 10000},
            {"timestamp": 1900.0, "open": 6650, "high": 6695, "low": 6630, "close": 6660, "volume": 12000},
            # Current session (after gap)
            {"timestamp": 20000.0, "open": 6665, "high": 6680, "low": 6655, "close": 6675, "volume": 8000},
            {"timestamp": 20900.0, "open": 6675, "high": 6690, "low": 6660, "close": 6685, "volume": 9000},
        ]
        cache_key = ("CME_MINI:ES1!", "15")
        provider._cache[cache_key] = (time.monotonic(), bars)

        result = provider.get_session_levels("ES1!", "CME_MINI", "15m", session_id="test")
        assert isinstance(result, dict)
        assert "prior_day_high" in result
        assert result["prior_day_high"] == 6695.0

    def test_get_bars_rejects_empty_series(self) -> None:
        provider = WSDataProvider()
        mock_client = MagicMock()
        mock_client.connected = True
        mock_client.get_series.return_value = []
        provider._client = mock_client
        provider._ensure_connected = lambda _sid: "forced reconnect failure"  # type: ignore[method-assign]

        result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="")
        assert isinstance(result, dict)
        assert "error" in result
