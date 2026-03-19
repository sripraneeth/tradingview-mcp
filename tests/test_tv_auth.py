from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

from tradingview_mcp.core.services.tv_auth import (
    extract_auth_token,
    get_session_id,
    _parse_auth_token_from_html,
    _AUTH_TOKEN_CACHE,
)


class TestParseAuthTokenFromHtml:
    def test_extracts_token_from_valid_html(self) -> None:
        html = '<script>window.__INITIAL_STATE__={"auth_token":"abc123xyz","other":"val"}</script>'
        assert _parse_auth_token_from_html(html) == "abc123xyz"

    def test_extracts_token_with_long_jwt_like_value(self) -> None:
        token = "eyJhbGciOiJSUzUxMiIsImtpZCI6IkdaeFUiLCJ0eXAiOiJKV1QifQ.eyJ1c2VyX2lkIjoxMjM0NTY3fQ.signature"
        html = f'{{"auth_token":"{token}","plan":"pro"}}'
        assert _parse_auth_token_from_html(html) == token

    def test_returns_none_for_missing_token(self) -> None:
        html = "<html><body>No token here</body></html>"
        assert _parse_auth_token_from_html(html) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _parse_auth_token_from_html("") is None


class TestGetSessionId:
    def test_returns_explicit_session_id(self) -> None:
        assert get_session_id("my_session_123") == "my_session_123"

    def test_falls_back_to_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("TV_SESSION_ID", "env_session_456")
        assert get_session_id("") == "env_session_456"

    def test_returns_empty_when_nothing_set(self, monkeypatch) -> None:
        monkeypatch.delenv("TV_SESSION_ID", raising=False)
        assert get_session_id("") == ""


class TestExtractAuthToken:
    def setup_method(self) -> None:
        _AUTH_TOKEN_CACHE.clear()

    def test_returns_cached_token(self) -> None:
        _AUTH_TOKEN_CACHE["cached_session"] = "cached_token_value"
        result = extract_auth_token("cached_session")
        assert result == "cached_token_value"

    def test_returns_error_for_empty_session(self) -> None:
        result = extract_auth_token("")
        assert result is None

    @patch("tradingview_mcp.core.services.tv_auth.urlopen")
    def test_extracts_token_from_http_response(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = b'<script>{"auth_token":"fresh_token_abc"}</script>'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = extract_auth_token("valid_session_id")
        assert result == "fresh_token_abc"
        assert _AUTH_TOKEN_CACHE["valid_session_id"] == "fresh_token_abc"

    @patch("tradingview_mcp.core.services.tv_auth.urlopen")
    def test_returns_none_on_http_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = Exception("Connection refused")
        result = extract_auth_token("bad_session")
        assert result is None

    @patch("tradingview_mcp.core.services.tv_auth.urlopen")
    def test_returns_none_when_token_not_in_html(self, mock_urlopen) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>no token</html>"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = extract_auth_token("session_no_token")
        assert result is None
