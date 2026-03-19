# WebSocket Data Integration Implementation Plan

**Goal:** Add real-time OHLCV bar data from TradingView's WebSocket API, enabling accurate intraday levels and analysis for futures and all markets.

**Architecture:** Three new service modules (auth, ws_client, data_provider) form a layered WebSocket stack. A new `tools/realtime.py` exposes three MCP tools (`realtime_levels`, `realtime_bars`, `realtime_analysis`). The existing screener-based tools remain untouched.

**Design:** `thoughts/shared/designs/2026-03-18-websocket-data-integration-design.md`

---

## Dependency Graph

```
Batch 1 (parallel): 1.1, 1.2           [config changes - no deps]
Batch 2 (parallel): 2.1, 2.2, 2.3      [core services - depend on batch 1]
Batch 3 (parallel): 3.1, 3.2           [data provider + its test - depends on batch 2]
Batch 4 (parallel): 4.1, 4.2           [tools + server wiring - depends on batch 3]
Batch 5 (parallel): 5.1                [integration smoke test - depends on batch 4]
```

---

## Batch 1: Configuration (parallel - 2 implementers)

All tasks in this batch have NO dependencies and run simultaneously.

### Task 1.1: Add websocket-client dependency
**File:** `pyproject.toml`
**Test:** none (config file)
**Depends:** none

The only change is adding `websocket-client` to the `dependencies` list.

```python
# In pyproject.toml, add "websocket-client>=1.6.0" to the dependencies array.
# The result should be:
#
# dependencies = [
#   "mcp[cli]>=1.12.0",
#   "tradingview-screener>=0.6.4",
#   "tradingview-ta>=3.3.0",
#   "finnhub-python>=2.4.0",
#   "websocket-client>=1.6.0",
# ]
```

After editing, run:
```bash
uv sync
```

**Verify:** `uv run python -c "import websocket; print(websocket.__version__)"`
**Commit:** `build: add websocket-client dependency for realtime data`

### Task 1.2: Auth token extraction service
**File:** `src/tradingview_mcp/core/services/tv_auth.py`
**Test:** `tests/test_tv_auth.py`
**Depends:** none

This module extracts the `auth_token` from a TradingView session cookie. It makes an HTTP GET to tradingview.com with the session cookie and scrapes the auth_token from the embedded JSON. It also supports `TV_SESSION_ID` env var as a fallback.

**Design decisions I'm making:**
- Using `urllib.request` (stdlib) instead of `requests` to avoid adding another dependency
- Caching the auth_token in a module-level dict keyed by session_id
- Regex pattern to extract auth_token from HTML: `"auth_token":"([^"]+)"`
- 10-second timeout on the HTTP request

```python
# tests/test_tv_auth.py
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
```

```python
# src/tradingview_mcp/core/services/tv_auth.py
"""Extract TradingView auth_token from session cookie.

The auth_token is required for WebSocket authentication. It is obtained by
loading tradingview.com with the user's sessionid cookie and scraping the
embedded JSON payload from the HTML response.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Dict, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_AUTH_TOKEN_CACHE: Dict[str, str] = {}

_AUTH_TOKEN_PATTERN = re.compile(r'"auth_token"\s*:\s*"([^"]+)"')

_TV_URL = "https://www.tradingview.com"
_HTTP_TIMEOUT = 10


def _parse_auth_token_from_html(html: str) -> Optional[str]:
    """Extract auth_token value from TradingView HTML page content."""
    if not html:
        return None
    match = _AUTH_TOKEN_PATTERN.search(html)
    return match.group(1) if match else None


def get_session_id(explicit: str = "") -> str:
    """Return the session ID to use: explicit param > env var > empty string."""
    if explicit:
        return explicit
    return os.environ.get("TV_SESSION_ID", "")


def extract_auth_token(session_id: str) -> Optional[str]:
    """Extract auth_token for a given TradingView session cookie.

    Returns the token string on success, or None on failure.
    Results are cached per session_id for the process lifetime.
    """
    if not session_id:
        return None

    cached = _AUTH_TOKEN_CACHE.get(session_id)
    if cached:
        return cached

    try:
        req = Request(
            _TV_URL,
            headers={
                "Cookie": f"sessionid={session_id}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Failed to fetch TradingView page for auth: %s", exc)
        return None

    token = _parse_auth_token_from_html(html)
    if token:
        _AUTH_TOKEN_CACHE[session_id] = token
    else:
        logger.warning("auth_token not found in TradingView HTML response")
    return token
```

**Verify:** `uv run pytest tests/test_tv_auth.py -v`
**Commit:** `feat(auth): add TradingView session cookie auth token extraction`

---

## Batch 2: Core WebSocket Services (parallel - 3 implementers)

All tasks in this batch depend on Batch 1 completing (need `websocket-client` installed and `tv_auth.py` available).

### Task 2.1: WebSocket client - protocol layer
**File:** `src/tradingview_mcp/core/services/ws_client.py`
**Test:** `tests/test_ws_client.py`
**Depends:** 1.1, 1.2

This is the low-level WebSocket client implementing TradingView's custom framing protocol. It handles connection, authentication, heartbeat, and message parsing.

**Design decisions I'm making:**
- TradingView framing: `~m~<length>~m~<payload>` — messages are length-prefixed
- Heartbeat: respond to `~h~<N>` with the same message
- Session IDs: `cs_` prefix + 12 random lowercase chars for chart sessions, `qs_` for quote sessions
- Timeframe mapping: `{"5m": "5", "15m": "15", "1h": "60", "4h": "240", "1D": "1D", "1W": "1W", "1M": "1M"}`
- Connection timeout: 10 seconds; recv timeout: 30 seconds
- All public methods return data or raise `ConnectionError` / `TimeoutError`

```python
# tests/test_ws_client.py
from __future__ import annotations

import json
import pytest

from tradingview_mcp.core.services.ws_client import (
    encode_message,
    decode_messages,
    generate_session_id,
    parse_timescale_update,
    TV_TIMEFRAME_MAP,
)


class TestEncodeMessage:
    def test_simple_string(self) -> None:
        result = encode_message("hello")
        assert result == "~m~5~m~hello"

    def test_json_payload(self) -> None:
        payload = json.dumps({"m": "set_auth_token", "p": ["token123"]})
        result = encode_message(payload)
        expected_len = len(payload)
        assert result == f"~m~{expected_len}~m~{payload}"

    def test_empty_string(self) -> None:
        result = encode_message("")
        assert result == "~m~0~m~"

    def test_unicode_payload(self) -> None:
        payload = "ES1!"
        result = encode_message(payload)
        assert result == f"~m~{len(payload)}~m~{payload}"


class TestDecodeMessages:
    def test_single_message(self) -> None:
        raw = "~m~5~m~hello"
        msgs = decode_messages(raw)
        assert msgs == ["hello"]

    def test_multiple_messages(self) -> None:
        raw = "~m~5~m~hello~m~5~m~world"
        msgs = decode_messages(raw)
        assert msgs == ["hello", "world"]

    def test_json_message(self) -> None:
        payload = json.dumps({"m": "du", "p": [1, 2, 3]})
        raw = f"~m~{len(payload)}~m~{payload}"
        msgs = decode_messages(raw)
        assert len(msgs) == 1
        parsed = json.loads(msgs[0])
        assert parsed["m"] == "du"

    def test_heartbeat_message(self) -> None:
        raw = "~m~3~m~~h~1"
        msgs = decode_messages(raw)
        # Heartbeat is ~h~1 which is 3 chars
        assert msgs == ["~h~1"]

    def test_empty_input(self) -> None:
        assert decode_messages("") == []

    def test_mixed_messages(self) -> None:
        msg1 = "~m~3~m~~h~5"
        payload = json.dumps({"m": "timescale_update"})
        msg2 = f"~m~{len(payload)}~m~{payload}"
        raw = msg1 + msg2
        msgs = decode_messages(raw)
        assert len(msgs) == 2
        assert msgs[0] == "~h~5"


class TestGenerateSessionId:
    def test_chart_session_prefix(self) -> None:
        sid = generate_session_id("cs")
        assert sid.startswith("cs_")
        assert len(sid) == 15  # cs_ + 12 chars

    def test_quote_session_prefix(self) -> None:
        sid = generate_session_id("qs")
        assert sid.startswith("qs_")
        assert len(sid) == 15

    def test_uniqueness(self) -> None:
        ids = {generate_session_id("cs") for _ in range(100)}
        assert len(ids) == 100  # all unique


class TestParseTimescaleUpdate:
    def test_parses_bar_data(self) -> None:
        # Simulated timescale_update payload structure from TradingView
        payload = {
            "m": "timescale_update",
            "p": [
                "cs_abc123",
                {
                    "sds_1": {
                        "s": [
                            {
                                "i": 0,
                                "v": [1710000000.0, 6650.0, 6660.0, 6640.0, 6655.0, 1234.0],
                            },
                            {
                                "i": 1,
                                "v": [1710000900.0, 6655.0, 6670.0, 6645.0, 6665.0, 2345.0],
                            },
                        ]
                    }
                },
            ],
        }
        bars = parse_timescale_update(payload)
        assert len(bars) == 2
        assert bars[0]["timestamp"] == 1710000000.0
        assert bars[0]["open"] == 6650.0
        assert bars[0]["high"] == 6660.0
        assert bars[0]["low"] == 6640.0
        assert bars[0]["close"] == 6655.0
        assert bars[0]["volume"] == 1234.0
        assert bars[1]["timestamp"] == 1710000900.0

    def test_returns_empty_for_invalid_payload(self) -> None:
        assert parse_timescale_update({}) == []
        assert parse_timescale_update({"m": "other"}) == []

    def test_handles_missing_series_data(self) -> None:
        payload = {"m": "timescale_update", "p": ["cs_abc", {}]}
        assert parse_timescale_update(payload) == []


class TestTimeframeMap:
    def test_all_timeframes_mapped(self) -> None:
        expected = {"5m", "15m", "1h", "4h", "1D", "1W", "1M"}
        assert set(TV_TIMEFRAME_MAP.keys()) == expected

    def test_minute_timeframes(self) -> None:
        assert TV_TIMEFRAME_MAP["5m"] == "5"
        assert TV_TIMEFRAME_MAP["15m"] == "15"

    def test_hour_timeframes(self) -> None:
        assert TV_TIMEFRAME_MAP["1h"] == "60"
        assert TV_TIMEFRAME_MAP["4h"] == "240"
```

```python
# src/tradingview_mcp/core/services/ws_client.py
"""Low-level WebSocket client for TradingView's charting data API.

Implements the custom framing protocol (~m~<len>~m~<payload>), heartbeat
handling, chart session management, and bar data parsing.
"""
from __future__ import annotations

import json
import logging
import random
import string
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket?type=chart"

TV_TIMEFRAME_MAP: Dict[str, str] = {
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1D": "1D",
    "1W": "1W",
    "1M": "1M",
}

_WS_CONNECT_TIMEOUT = 10
_WS_RECV_TIMEOUT = 30


def encode_message(payload: str) -> str:
    """Encode a payload into TradingView's ~m~ framing format."""
    return f"~m~{len(payload)}~m~{payload}"


def decode_messages(raw: str) -> List[str]:
    """Decode one or more ~m~-framed messages from a raw WebSocket string."""
    messages: List[str] = []
    if not raw:
        return messages

    pos = 0
    while pos < len(raw):
        # Expect ~m~ prefix
        if not raw[pos:].startswith("~m~"):
            break
        pos += 3  # skip ~m~

        # Read length digits until next ~m~
        len_end = raw.find("~m~", pos)
        if len_end == -1:
            break
        try:
            msg_len = int(raw[pos:len_end])
        except ValueError:
            break
        pos = len_end + 3  # skip second ~m~

        # Extract message body
        msg = raw[pos : pos + msg_len]
        messages.append(msg)
        pos += msg_len

    return messages


def generate_session_id(prefix: str = "cs") -> str:
    """Generate a random session ID with the given prefix (cs_ or qs_)."""
    suffix = "".join(random.choices(string.ascii_lowercase, k=12))
    return f"{prefix}_{suffix}"


def parse_timescale_update(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse bar data from a timescale_update message payload.

    Each bar is returned as: {timestamp, open, high, low, close, volume}.
    """
    if not isinstance(payload, dict) or payload.get("m") != "timescale_update":
        return []

    p = payload.get("p")
    if not isinstance(p, list) or len(p) < 2:
        return []

    data_block = p[1]
    if not isinstance(data_block, dict):
        return []

    bars: List[Dict[str, Any]] = []
    for series_key, series_data in data_block.items():
        if not isinstance(series_data, dict):
            continue
        s_list = series_data.get("s")
        if not isinstance(s_list, list):
            continue
        for item in s_list:
            v = item.get("v") if isinstance(item, dict) else None
            if not isinstance(v, list) or len(v) < 6:
                continue
            bars.append(
                {
                    "timestamp": v[0],
                    "open": v[1],
                    "high": v[2],
                    "low": v[3],
                    "close": v[4],
                    "volume": v[5],
                }
            )

    return bars


def _build_message(method: str, params: List[Any]) -> str:
    """Build a JSON-encoded TradingView protocol message."""
    return json.dumps({"m": method, "p": params})


class TVWebSocketClient:
    """Synchronous WebSocket client for TradingView chart data.

    Usage:
        client = TVWebSocketClient()
        client.connect(auth_token="...")
        bars = client.get_series("CME_MINI:ES1!", "15", count=100)
        client.disconnect()
    """

    def __init__(self) -> None:
        self._ws: Any = None  # websocket.WebSocket instance
        self._chart_session: str = ""
        self._connected: bool = False
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None

    def connect(self, auth_token: str) -> None:
        """Connect to TradingView WebSocket and authenticate."""
        import websocket  # lazy import to allow tests without the package

        ws = websocket.WebSocket()
        ws.connect(
            TV_WS_URL,
            timeout=_WS_CONNECT_TIMEOUT,
            origin="https://www.tradingview.com",
        )
        self._ws = ws
        self._connected = True

        # Authenticate
        self._send_raw(
            _build_message("set_auth_token", [auth_token])
        )

        # Create chart session
        self._chart_session = generate_session_id("cs")
        self._send_raw(
            _build_message("chart_create_session", [self._chart_session, ""])
        )

        logger.info("Connected to TradingView WebSocket, session=%s", self._chart_session)

    def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        self._ws = None
        self._connected = False
        self._chart_session = ""

    def get_series(
        self,
        full_symbol: str,
        timeframe_tv: str,
        count: int = 100,
        timeout: float = _WS_RECV_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """Request OHLCV bars for a symbol and wait for the response.

        Args:
            full_symbol: TradingView symbol like "CME_MINI:ES1!"
            timeframe_tv: TradingView timeframe string like "15" or "1D"
            count: Number of bars to request
            timeout: Max seconds to wait for data

        Returns:
            List of bar dicts with keys: timestamp, open, high, low, close, volume

        Raises:
            ConnectionError: If not connected
            TimeoutError: If no data received within timeout
        """
        if not self.connected:
            raise ConnectionError("WebSocket is not connected")

        series_id = "sds_1"

        # Resolve symbol
        self._send_raw(
            _build_message(
                "resolve_symbol",
                [
                    self._chart_session,
                    "sds_sym_1",
                    f'={{"symbol":"{full_symbol}","adjustment":"splits"}}',
                ],
            )
        )

        # Create series
        self._send_raw(
            _build_message(
                "create_series",
                [
                    self._chart_session,
                    series_id,
                    "s1",
                    "sds_sym_1",
                    timeframe_tv,
                    count,
                ],
            )
        )

        # Wait for timescale_update
        all_bars: List[Dict[str, Any]] = []
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            try:
                self._ws.settimeout(min(remaining, 5.0))
                raw = self._ws.recv()
            except Exception:
                continue

            if not raw:
                continue

            messages = decode_messages(raw)
            for msg_str in messages:
                # Handle heartbeat
                if msg_str.startswith("~h~"):
                    self._send_raw(msg_str)
                    continue

                try:
                    msg = json.loads(msg_str)
                except (json.JSONDecodeError, TypeError):
                    continue

                if isinstance(msg, dict):
                    if msg.get("m") == "timescale_update":
                        bars = parse_timescale_update(msg)
                        all_bars.extend(bars)

                    if msg.get("m") == "series_completed":
                        # Data is complete
                        return all_bars

        if all_bars:
            return all_bars

        raise TimeoutError(f"Timed out waiting for bar data for {full_symbol}")

    def _send_raw(self, payload: str) -> None:
        """Send a framed message over the WebSocket."""
        if self._ws is None:
            raise ConnectionError("WebSocket is not connected")
        framed = encode_message(payload)
        self._ws.send(framed)
```

**Verify:** `uv run pytest tests/test_ws_client.py -v`
**Commit:** `feat(ws): add TradingView WebSocket client with protocol framing`

### Task 2.2: Level calculation utilities
**File:** `src/tradingview_mcp/core/services/level_calc.py`
**Test:** `tests/test_level_calculations.py`
**Depends:** none (pure computation, no imports from this project)

This module contains pure functions for computing intraday trading levels from OHLCV bar data. Separated from the data provider for testability.

**Design decisions I'm making:**
- Session boundary detection: bars with timestamp gap > 4 hours mark a new session (handles overnight gaps for futures)
- VWAP: cumulative (price * volume) / cumulative volume across session bars
- Opening range: first N bars of the current session (5min = 1 bar if 5m tf, 3 bars if 5m for 15min OR, etc.)
- Camarilla pivots: standard formula from prior day OHLC
- Fibonacci pivots: standard formula from prior day OHLC

```python
# tests/test_level_calculations.py
from __future__ import annotations

import pytest

from tradingview_mcp.core.services.level_calc import (
    compute_session_levels,
    compute_vwap,
    compute_camarilla_pivots,
    compute_fibonacci_pivots,
    compute_classic_pivots,
    split_sessions,
)


def _make_bar(ts: float, o: float, h: float, l: float, c: float, v: float) -> dict:
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}


# --- Session splitting ---

class TestSplitSessions:
    def test_single_session(self) -> None:
        bars = [
            _make_bar(1000.0, 100, 105, 95, 102, 500),
            _make_bar(1900.0, 102, 108, 100, 106, 600),
            _make_bar(2800.0, 106, 110, 104, 109, 700),
        ]
        sessions = split_sessions(bars, gap_seconds=14400)
        assert len(sessions) == 1
        assert len(sessions[0]) == 3

    def test_two_sessions_with_gap(self) -> None:
        bars = [
            _make_bar(1000.0, 100, 105, 95, 102, 500),
            _make_bar(1900.0, 102, 108, 100, 106, 600),
            # Gap of 20000 seconds (> 4 hours)
            _make_bar(21900.0, 110, 115, 108, 113, 800),
            _make_bar(22800.0, 113, 118, 112, 116, 900),
        ]
        sessions = split_sessions(bars, gap_seconds=14400)
        assert len(sessions) == 2
        assert len(sessions[0]) == 2
        assert len(sessions[1]) == 2

    def test_empty_bars(self) -> None:
        assert split_sessions([], gap_seconds=14400) == []


# --- VWAP ---

class TestComputeVwap:
    def test_basic_vwap(self) -> None:
        bars = [
            _make_bar(1000, 100, 105, 95, 102, 1000),
            _make_bar(1900, 102, 108, 100, 106, 2000),
        ]
        # typical_price = (H+L+C)/3
        # bar1: (105+95+102)/3 = 100.667, * 1000 = 100666.67
        # bar2: (108+100+106)/3 = 104.667, * 2000 = 209333.33
        # vwap = (100666.67 + 209333.33) / 3000 = 103.333
        vwap = compute_vwap(bars)
        assert vwap is not None
        assert abs(vwap - 103.333) < 0.01

    def test_single_bar(self) -> None:
        bars = [_make_bar(1000, 100, 110, 90, 105, 500)]
        vwap = compute_vwap(bars)
        # (110+90+105)/3 = 101.667
        assert vwap is not None
        assert abs(vwap - 101.667) < 0.01

    def test_zero_volume(self) -> None:
        bars = [_make_bar(1000, 100, 110, 90, 105, 0)]
        assert compute_vwap(bars) is None

    def test_empty_bars(self) -> None:
        assert compute_vwap([]) is None


# --- Pivot calculations ---

class TestClassicPivots:
    def test_standard_calculation(self) -> None:
        # PP = (H + L + C) / 3 = (110 + 90 + 105) / 3 = 101.667
        pivots = compute_classic_pivots(high=110.0, low=90.0, close=105.0)
        assert abs(pivots["pivot"] - 101.667) < 0.01
        assert abs(pivots["s1"] - (2 * 101.667 - 110)) < 0.01  # 93.333
        assert abs(pivots["r1"] - (2 * 101.667 - 90)) < 0.01   # 113.333


class TestCamarillaPivots:
    def test_standard_calculation(self) -> None:
        pivots = compute_camarilla_pivots(high=110.0, low=90.0, close=105.0)
        r = 110.0 - 90.0  # range = 20
        assert abs(pivots["s1"] - (105.0 - r * 1.1 / 12)) < 0.01
        assert abs(pivots["r1"] - (105.0 + r * 1.1 / 12)) < 0.01
        assert abs(pivots["s3"] - (105.0 - r * 1.1 / 4)) < 0.01
        assert abs(pivots["r3"] - (105.0 + r * 1.1 / 4)) < 0.01


class TestFibonacciPivots:
    def test_standard_calculation(self) -> None:
        pivots = compute_fibonacci_pivots(high=110.0, low=90.0, close=105.0)
        pp = (110.0 + 90.0 + 105.0) / 3  # 101.667
        r = 110.0 - 90.0  # 20
        assert abs(pivots["pivot"] - pp) < 0.01
        assert abs(pivots["s1"] - (pp - 0.382 * r)) < 0.01
        assert abs(pivots["r1"] - (pp + 0.382 * r)) < 0.01


# --- Full session levels ---

class TestComputeSessionLevels:
    def test_computes_all_level_types(self) -> None:
        # Prior session bars
        prior_bars = [
            _make_bar(1000.0, 6600, 6680, 6590, 6650, 10000),
            _make_bar(1900.0, 6650, 6695, 6630, 6670, 12000),
            _make_bar(2800.0, 6670, 6690, 6640, 6660, 11000),
        ]
        # Current session bars (after gap)
        current_bars = [
            _make_bar(20000.0, 6665, 6680, 6655, 6675, 8000),
            _make_bar(20900.0, 6675, 6690, 6660, 6685, 9000),
            _make_bar(21800.0, 6685, 6700, 6670, 6695, 7000),
        ]
        all_bars = prior_bars + current_bars

        levels = compute_session_levels(all_bars, gap_seconds=14400)

        assert levels is not None
        # Prior day levels
        assert levels["prior_day_high"] == 6695.0
        assert levels["prior_day_low"] == 6590.0
        assert levels["prior_day_close"] == 6660.0

        # Current session
        assert levels["session_open"] == 6665.0
        assert levels["session_high"] == 6700.0
        assert levels["session_low"] == 6655.0

        # VWAP should be present
        assert "session_vwap" in levels
        assert levels["session_vwap"] is not None

        # Pivots should be present
        assert "classic_pivots" in levels
        assert "fibonacci_pivots" in levels
        assert "camarilla_pivots" in levels

    def test_returns_none_for_insufficient_data(self) -> None:
        # Only one session, no prior day data
        bars = [_make_bar(1000.0, 100, 110, 90, 105, 500)]
        levels = compute_session_levels(bars, gap_seconds=14400)
        assert levels is None

    def test_returns_none_for_empty_bars(self) -> None:
        assert compute_session_levels([], gap_seconds=14400) is None
```

```python
# src/tradingview_mcp/core/services/level_calc.py
"""Pure computation functions for intraday trading levels from OHLCV bars.

All functions are stateless and have no external dependencies.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def split_sessions(
    bars: List[Dict[str, Any]], gap_seconds: int = 14400
) -> List[List[Dict[str, Any]]]:
    """Split bars into sessions based on timestamp gaps.

    A new session starts when the gap between consecutive bars exceeds
    gap_seconds (default 4 hours = 14400s).
    """
    if not bars:
        return []

    sessions: List[List[Dict[str, Any]]] = [[bars[0]]]
    for i in range(1, len(bars)):
        gap = bars[i]["timestamp"] - bars[i - 1]["timestamp"]
        if gap > gap_seconds:
            sessions.append([bars[i]])
        else:
            sessions[-1].append(bars[i])

    return sessions


def compute_vwap(bars: List[Dict[str, Any]]) -> Optional[float]:
    """Compute VWAP from a list of OHLCV bars.

    VWAP = sum(typical_price * volume) / sum(volume)
    where typical_price = (high + low + close) / 3
    """
    if not bars:
        return None

    cum_tp_vol = 0.0
    cum_vol = 0.0

    for bar in bars:
        vol = float(bar.get("volume", 0))
        if vol <= 0:
            continue
        tp = (float(bar["high"]) + float(bar["low"]) + float(bar["close"])) / 3.0
        cum_tp_vol += tp * vol
        cum_vol += vol

    if cum_vol <= 0:
        return None

    return round(cum_tp_vol / cum_vol, 4)


def compute_classic_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Compute classic pivot points from prior session OHLC."""
    pp = (high + low + close) / 3.0
    return {
        "pivot": round(pp, 4),
        "s1": round(2 * pp - high, 4),
        "s2": round(pp - (high - low), 4),
        "s3": round(low - 2 * (high - pp), 4),
        "r1": round(2 * pp - low, 4),
        "r2": round(pp + (high - low), 4),
        "r3": round(high + 2 * (pp - low), 4),
    }


def compute_fibonacci_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Compute Fibonacci pivot points from prior session OHLC."""
    pp = (high + low + close) / 3.0
    r = high - low
    return {
        "pivot": round(pp, 4),
        "s1": round(pp - 0.382 * r, 4),
        "s2": round(pp - 0.618 * r, 4),
        "s3": round(pp - 1.000 * r, 4),
        "r1": round(pp + 0.382 * r, 4),
        "r2": round(pp + 0.618 * r, 4),
        "r3": round(pp + 1.000 * r, 4),
    }


def compute_camarilla_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """Compute Camarilla pivot points from prior session OHLC."""
    r = high - low
    return {
        "s1": round(close - r * 1.1 / 12, 4),
        "s2": round(close - r * 1.1 / 6, 4),
        "s3": round(close - r * 1.1 / 4, 4),
        "s4": round(close - r * 1.1 / 2, 4),
        "r1": round(close + r * 1.1 / 12, 4),
        "r2": round(close + r * 1.1 / 6, 4),
        "r3": round(close + r * 1.1 / 4, 4),
        "r4": round(close + r * 1.1 / 2, 4),
    }


def _session_ohlc(bars: List[Dict[str, Any]]) -> Dict[str, float]:
    """Extract session-level OHLC from a list of bars."""
    if not bars:
        return {}
    return {
        "open": float(bars[0]["open"]),
        "high": max(float(b["high"]) for b in bars),
        "low": min(float(b["low"]) for b in bars),
        "close": float(bars[-1]["close"]),
    }


def compute_session_levels(
    bars: List[Dict[str, Any]], gap_seconds: int = 14400
) -> Optional[Dict[str, Any]]:
    """Compute comprehensive intraday levels from OHLCV bars.

    Requires at least 2 sessions (prior + current) to compute levels.
    Returns None if insufficient data.

    Output includes:
    - prior_day_high/low/close
    - session_open/high/low
    - session_vwap
    - classic_pivots, fibonacci_pivots, camarilla_pivots
    - opening_range (first bar of current session)
    """
    if not bars:
        return None

    sessions = split_sessions(bars, gap_seconds=gap_seconds)
    if len(sessions) < 2:
        return None

    prior_session = sessions[-2]
    current_session = sessions[-1]

    prior_ohlc = _session_ohlc(prior_session)
    current_ohlc = _session_ohlc(current_session)

    if not prior_ohlc or not current_ohlc:
        return None

    prior_h = prior_ohlc["high"]
    prior_l = prior_ohlc["low"]
    prior_c = prior_ohlc["close"]

    # Opening range from first bar of current session
    first_bar = current_session[0]
    opening_range = {
        "high": float(first_bar["high"]),
        "low": float(first_bar["low"]),
    }

    return {
        "prior_day_high": prior_h,
        "prior_day_low": prior_l,
        "prior_day_close": prior_c,
        "session_open": current_ohlc["open"],
        "session_high": current_ohlc["high"],
        "session_low": current_ohlc["low"],
        "session_vwap": compute_vwap(current_session),
        "opening_range": opening_range,
        "classic_pivots": compute_classic_pivots(prior_h, prior_l, prior_c),
        "fibonacci_pivots": compute_fibonacci_pivots(prior_h, prior_l, prior_c),
        "camarilla_pivots": compute_camarilla_pivots(prior_h, prior_l, prior_c),
    }
```

**Verify:** `uv run pytest tests/test_level_calculations.py -v`
**Commit:** `feat(levels): add pure level calculation functions for intraday pivots and VWAP`

### Task 2.3: WebSocket data provider (high-level interface)
**File:** `src/tradingview_mcp/core/services/ws_data_provider.py`
**Test:** `tests/test_ws_data_provider.py`
**Depends:** 1.1, 1.2, 2.1, 2.2

This is the high-level data access layer that tools call. It manages connection lifecycle, caching, and delegates to `ws_client.py` and `level_calc.py`.

**Design decisions I'm making:**
- Singleton pattern: module-level `_provider` instance, lazy-initialized
- Cache: dict keyed by `(symbol, exchange, timeframe)` with 30-second TTL
- Connection reuse: single `TVWebSocketClient` instance, reconnect on failure
- Symbol resolution: `ES1!` + `CME_MINI` -> `CME_MINI:ES1!` (simple prefix, no USDT appending)
- Retry: one retry with 5-second delay on connection failure

```python
# tests/test_ws_data_provider.py
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
    def test_get_bars_returns_error_dict_on_auth_failure(self, mock_auth) -> None:
        mock_auth.return_value = None

        provider = WSDataProvider()
        provider._client = MagicMock()
        provider._client.connected = False

        result = provider.get_bars("ES1!", "CME_MINI", "15m", count=100, session_id="bad_sess")
        assert isinstance(result, dict)
        assert "error" in result

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
```

```python
# src/tradingview_mcp/core/services/ws_data_provider.py
"""High-level data provider built on the TradingView WebSocket client.

Manages connection lifecycle, caching, and provides clean interfaces
for tools to request bars, quotes, and computed levels.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from tradingview_mcp.core.services.tv_auth import extract_auth_token, get_session_id
from tradingview_mcp.core.services.ws_client import TVWebSocketClient, TV_TIMEFRAME_MAP
from tradingview_mcp.core.services.level_calc import compute_session_levels

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30
_RETRY_DELAY_SECONDS = 5


def _format_ws_symbol(symbol: str, exchange: str) -> str:
    """Format symbol for WebSocket requests: EXCHANGE:SYMBOL."""
    sym = (symbol or "").strip().upper()
    ex = (exchange or "").strip().upper()
    if ":" in sym:
        return sym
    return f"{ex}:{sym}"


class WSDataProvider:
    """High-level interface for fetching real-time data via TradingView WebSocket.

    Manages a single WebSocket connection with lazy initialization,
    automatic reconnection, and a 30-second bar cache.
    """

    def __init__(self) -> None:
        self._client: TVWebSocketClient = TVWebSocketClient()
        self._cache: Dict[Tuple[str, str], Tuple[float, Any]] = {}

    def _ensure_connected(self, session_id: str) -> Optional[str]:
        """Ensure WebSocket is connected. Returns error string or None on success."""
        if self._client.connected:
            return None

        sid = get_session_id(session_id)
        if not sid:
            return "tv_session_id is required for realtime tools. Get it from your browser cookies."

        auth_token = extract_auth_token(sid)
        if not auth_token:
            return "TradingView session expired. Please provide a fresh sessionid cookie."

        try:
            self._client.connect(auth_token=auth_token)
        except Exception as exc:
            logger.warning("WebSocket connection failed: %s", exc)
            return f"WebSocket connection failed: {exc}"

        return None

    def _get_cached(self, cache_key: Tuple[str, str]) -> Optional[Any]:
        """Return cached data if still valid, else None."""
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > _CACHE_TTL_SECONDS:
            return None
        return data

    def get_bars(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        count: int = 100,
        session_id: str = "",
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """Fetch OHLCV bars. Returns list of bar dicts or error dict."""
        full_symbol = _format_ws_symbol(symbol, exchange)
        tf_tv = TV_TIMEFRAME_MAP.get(timeframe, timeframe)
        cache_key = (full_symbol, tf_tv)

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        err = self._ensure_connected(session_id)
        if err:
            return {"error": err}

        for attempt in range(2):
            try:
                bars = self._client.get_series(
                    full_symbol=full_symbol,
                    timeframe_tv=tf_tv,
                    count=count,
                )
                self._cache[cache_key] = (time.monotonic(), bars)
                return bars
            except (ConnectionError, TimeoutError) as exc:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, full_symbol, exc)
                if attempt == 0:
                    # Reconnect and retry once
                    self._client.disconnect()
                    err = self._ensure_connected(session_id)
                    if err:
                        return {"error": err}
                    time.sleep(_RETRY_DELAY_SECONDS)
                else:
                    return {"error": f"Failed to fetch bars for {full_symbol}: {exc}"}
            except Exception as exc:
                return {"error": f"Unexpected error fetching bars for {full_symbol}: {exc}"}

        return {"error": f"Failed to fetch bars for {full_symbol}"}

    def get_session_levels(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        session_id: str = "",
    ) -> Union[Dict[str, Any], Dict[str, str]]:
        """Compute intraday session levels from real bar data.

        Returns level dict or error dict.
        """
        bars_result = self.get_bars(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            count=200,  # ~2 trading days of 30m bars
            session_id=session_id,
        )

        if isinstance(bars_result, dict) and "error" in bars_result:
            return bars_result

        if not isinstance(bars_result, list) or len(bars_result) == 0:
            return {"error": f"No bar data received for {_format_ws_symbol(symbol, exchange)}"}

        levels = compute_session_levels(bars_result)
        if levels is None:
            return {
                "error": "Insufficient data to compute session levels. Need at least 2 trading sessions."
            }

        levels["symbol"] = _format_ws_symbol(symbol, exchange)
        levels["bar_count"] = len(bars_result)
        return levels

    def disconnect(self) -> None:
        """Disconnect the WebSocket client."""
        self._client.disconnect()
        self._cache.clear()


# Module-level singleton, lazily used by tools
_provider: Optional[WSDataProvider] = None


def get_provider() -> WSDataProvider:
    """Get or create the singleton WSDataProvider instance."""
    global _provider
    if _provider is None:
        _provider = WSDataProvider()
    return _provider
```

**Verify:** `uv run pytest tests/test_ws_data_provider.py -v`
**Commit:** `feat(provider): add WebSocket data provider with caching and auto-reconnect`

---

## Batch 3: MCP Tools (parallel - 2 implementers)

### Task 3.1: Realtime tool definitions
**File:** `src/tradingview_mcp/tools/realtime.py`
**Test:** `tests/test_realtime_tools.py`
**Depends:** 2.3 (imports ws_data_provider)

Three MCP tools: `realtime_levels`, `realtime_bars`, `realtime_analysis`. Follows the exact same `register_*_tools(mcp)` pattern as `tools/futures.py`.

**Design decisions I'm making:**
- `realtime_analysis` computes RSI, MACD, Bollinger Bands, EMAs from raw bars using simple formulas (not reusing `indicators.py` which expects screener-format dicts). This keeps the realtime tools self-contained.
- All tools validate `tv_session_id` and return clear error if missing
- Exchange default: `CME_MINI` (primary use case is futures)

```python
# tests/test_realtime_tools.py
from __future__ import annotations

from unittest.mock import patch, MagicMock
import time

import pytest

from tradingview_mcp.tools import realtime


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator


class TestRegisterRealtimeTools:
    def test_registers_all_required_tools(self) -> None:
        mcp = DummyMCP()
        realtime.register_realtime_tools(mcp)
        required = {"realtime_levels", "realtime_bars", "realtime_analysis"}
        assert required.issubset(set(mcp.tools.keys()))


class TestRealtimeBars:
    def setup_method(self) -> None:
        self.mcp = DummyMCP()
        realtime.register_realtime_tools(self.mcp)
        self.tool = self.mcp.tools["realtime_bars"]

    def test_returns_error_without_session_id(self) -> None:
        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", count=100, tv_session_id="")
        assert "error" in result

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_bars_on_success(self, mock_get_provider) -> None:
        fake_bars = [
            {"timestamp": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 500},
            {"timestamp": 1900, "open": 105, "high": 115, "low": 95, "close": 110, "volume": 600},
        ]
        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = fake_bars
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", count=100, tv_session_id="test_session")

        assert result["symbol"] == "CME_MINI:ES1!"
        assert result["timeframe"] == "15m"
        assert len(result["bars"]) == 2
        assert result["bar_count"] == 2

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_error_from_provider(self, mock_get_provider) -> None:
        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = {"error": "Session expired"}
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", count=100, tv_session_id="test")
        assert result == {"error": "Session expired"}


class TestRealtimeLevels:
    def setup_method(self) -> None:
        self.mcp = DummyMCP()
        realtime.register_realtime_tools(self.mcp)
        self.tool = self.mcp.tools["realtime_levels"]

    def test_returns_error_without_session_id(self) -> None:
        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="30m", tv_session_id="")
        assert "error" in result

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_levels_on_success(self, mock_get_provider) -> None:
        fake_levels = {
            "prior_day_high": 6695.0,
            "prior_day_low": 6590.0,
            "prior_day_close": 6660.0,
            "session_open": 6665.0,
            "session_high": 6700.0,
            "session_low": 6655.0,
            "session_vwap": 6680.0,
            "opening_range": {"high": 6680.0, "low": 6655.0},
            "classic_pivots": {"pivot": 6648.33},
            "fibonacci_pivots": {"pivot": 6648.33},
            "camarilla_pivots": {"s1": 6650.0},
            "symbol": "CME_MINI:ES1!",
            "bar_count": 50,
        }
        mock_provider = MagicMock()
        mock_provider.get_session_levels.return_value = fake_levels
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="30m", tv_session_id="test")
        assert result["prior_day_high"] == 6695.0
        assert result["session_vwap"] == 6680.0


class TestRealtimeAnalysis:
    def setup_method(self) -> None:
        self.mcp = DummyMCP()
        realtime.register_realtime_tools(self.mcp)
        self.tool = self.mcp.tools["realtime_analysis"]

    def test_returns_error_without_session_id(self) -> None:
        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", tv_session_id="")
        assert "error" in result

    @patch("tradingview_mcp.tools.realtime.get_provider")
    def test_returns_analysis_on_success(self, mock_get_provider) -> None:
        # Generate 30 bars for indicator computation
        fake_bars = []
        for i in range(30):
            fake_bars.append({
                "timestamp": 1000 + i * 900,
                "open": 100 + i * 0.5,
                "high": 102 + i * 0.5,
                "low": 98 + i * 0.5,
                "close": 101 + i * 0.5,
                "volume": 1000 + i * 10,
            })

        mock_provider = MagicMock()
        mock_provider.get_bars.return_value = fake_bars
        mock_get_provider.return_value = mock_provider

        result = self.tool(symbol="ES1!", exchange="CME_MINI", timeframe="15m", tv_session_id="test")

        assert result["symbol"] == "CME_MINI:ES1!"
        assert "analysis" in result
        analysis = result["analysis"]
        assert "rsi" in analysis
        assert "sma_20" in analysis
        assert "latest_bar" in result
```

```python
# src/tradingview_mcp/tools/realtime.py
"""MCP tool definitions for real-time WebSocket data.

Provides realtime_levels, realtime_bars, and realtime_analysis tools
that use TradingView's WebSocket API for actual OHLCV bar data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from tradingview_mcp.core.services.ws_data_provider import get_provider


def _validate_session(tv_session_id: str) -> Optional[Dict[str, str]]:
    """Return error dict if session ID is missing, else None."""
    if not tv_session_id.strip():
        return {
            "error": "tv_session_id is required for realtime tools. "
            "Get it from your browser cookies (TradingView sessionid)."
        }
    return None


def _format_symbol(symbol: str, exchange: str) -> str:
    """Format symbol with exchange prefix."""
    sym = (symbol or "").strip().upper()
    ex = (exchange or "").strip().upper()
    if ":" in sym:
        return sym
    return f"{ex}:{sym}"


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Compute RSI from a list of close prices."""
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 3)


def _compute_sma(values: List[float], period: int) -> Optional[float]:
    """Compute Simple Moving Average."""
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 4)


def _compute_ema(values: List[float], period: int) -> Optional[float]:
    """Compute Exponential Moving Average."""
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for val in values[period:]:
        ema = (val - ema) * multiplier + ema
    return round(ema, 4)


def _compute_macd(
    closes: List[float],
) -> Optional[Dict[str, Optional[float]]]:
    """Compute MACD (12, 26, 9)."""
    if len(closes) < 26:
        return None

    ema12 = _compute_ema(closes, 12)
    ema26 = _compute_ema(closes, 26)
    if ema12 is None or ema26 is None:
        return None

    macd_line = round(ema12 - ema26, 4)
    # Signal line needs MACD history; simplified: just return current MACD
    return {"macd": macd_line, "signal": None, "histogram": None}


def _compute_bollinger(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> Optional[Dict[str, float]]:
    """Compute Bollinger Bands."""
    if len(closes) < period:
        return None
    window = closes[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std = variance**0.5
    return {
        "upper": round(sma + std_dev * std, 4),
        "middle": round(sma, 4),
        "lower": round(sma - std_dev * std, 4),
        "width": round((2 * std_dev * std) / sma, 6) if sma else None,
    }


def _build_analysis(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build technical analysis from raw OHLCV bars."""
    closes = [float(b["close"]) for b in bars]

    return {
        "rsi": _compute_rsi(closes),
        "sma_20": _compute_sma(closes, 20),
        "ema_20": _compute_ema(closes, 20),
        "ema_50": _compute_ema(closes, 50),
        "ema_200": _compute_ema(closes, 200),
        "macd": _compute_macd(closes),
        "bollinger": _compute_bollinger(closes),
        "bar_count": len(bars),
    }


def register_realtime_tools(mcp: Any) -> None:
    """Register realtime WebSocket-based tools on a FastMCP instance."""

    @mcp.tool()
    def realtime_bars(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        count: int = 100,
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return raw OHLCV bar data from TradingView WebSocket.

        Parameters:
            symbol: Trading symbol (e.g., "ES1!", "NQ1!", "BTCUSDT")
            exchange: Exchange name (default CME_MINI)
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            count: Number of bars (default 100, max 5000)
            tv_session_id: TradingView session cookie (required)
        """
        err = _validate_session(tv_session_id)
        if err:
            return err

        count_clamped = max(1, min(int(count), 5000))
        provider = get_provider()
        result = provider.get_bars(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            count=count_clamped,
            session_id=tv_session_id,
        )

        if isinstance(result, dict) and "error" in result:
            return result

        return {
            "symbol": _format_symbol(symbol, exchange),
            "exchange": exchange.strip().lower(),
            "timeframe": timeframe,
            "bar_count": len(result),
            "bars": result,
        }

    @mcp.tool()
    def realtime_levels(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "30m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return session-based support/resistance levels computed from real OHLCV bars.

        Includes prior day H/L/C, opening range, session VWAP, and intraday pivots
        (Classic, Fibonacci, Camarilla). These match the tight ranges visible on
        TradingView charts, unlike screener-based daily pivots.

        Parameters:
            symbol: Trading symbol (e.g., "ES1!", "NQ1!")
            exchange: Exchange name (default CME_MINI)
            timeframe: Timeframe for bar data (default 30m)
            tv_session_id: TradingView session cookie (required)
        """
        err = _validate_session(tv_session_id)
        if err:
            return err

        provider = get_provider()
        return provider.get_session_levels(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            session_id=tv_session_id,
        )

    @mcp.tool()
    def realtime_analysis(
        symbol: str,
        exchange: str = "CME_MINI",
        timeframe: str = "15m",
        tv_session_id: str = "",
    ) -> Dict[str, Any]:
        """Return technical analysis computed from real OHLCV bars via WebSocket.

        Computes RSI, MACD, Bollinger Bands, and moving averages from actual
        bar data rather than screener snapshots.

        Parameters:
            symbol: Trading symbol (e.g., "ES1!", "NQ1!", "BTCUSDT")
            exchange: Exchange name (default CME_MINI)
            timeframe: One of 5m, 15m, 1h, 4h, 1D, 1W, 1M
            tv_session_id: TradingView session cookie (required)
        """
        err = _validate_session(tv_session_id)
        if err:
            return err

        provider = get_provider()
        bars_result = provider.get_bars(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            count=300,  # enough for EMA200 + buffer
            session_id=tv_session_id,
        )

        if isinstance(bars_result, dict) and "error" in bars_result:
            return bars_result

        if not isinstance(bars_result, list) or len(bars_result) == 0:
            return {"error": f"No bar data received for {_format_symbol(symbol, exchange)}"}

        analysis = _build_analysis(bars_result)

        latest = bars_result[-1]
        return {
            "symbol": _format_symbol(symbol, exchange),
            "exchange": exchange.strip().lower(),
            "timeframe": timeframe,
            "analysis": analysis,
            "latest_bar": latest,
        }
```

**Verify:** `uv run pytest tests/test_realtime_tools.py -v`
**Commit:** `feat(tools): add realtime_bars, realtime_levels, realtime_analysis MCP tools`

### Task 3.2: Wire realtime tools into server.py
**File:** `src/tradingview_mcp/server.py` (MODIFY)
**Test:** none (existing test infrastructure covers registration)
**Depends:** 3.1

Add the import and registration call for realtime tools.

**Changes to make:**

1. Add import at line 13 (after the indices import):
```python
from tradingview_mcp.tools.realtime import register_realtime_tools
```

2. Add registration call inside `_register_all_tools()` at line 29 (after `register_indices_tools(mcp)`):
```python
    register_realtime_tools(mcp)
```

The full modified function becomes:
```python
from tradingview_mcp.tools.realtime import register_realtime_tools

# ... existing imports ...

def _register_all_tools() -> None:
    register_crypto_tools(mcp)
    register_stocks_tools(mcp)
    register_futures_tools(mcp)
    register_indices_tools(mcp)
    register_realtime_tools(mcp)
```

**Verify:** `uv run python -c "from tradingview_mcp.server import mcp; print([t for t in mcp._tool_manager._tools if t.startswith('realtime')])"` (or simply `uv run pytest tests/ -v --tb=short` to ensure nothing breaks)
**Commit:** `feat(server): register realtime WebSocket tools`

---

## Batch 4: Verification (sequential - 1 implementer)

### Task 4.1: Full test suite run
**File:** none (verification only)
**Test:** all tests
**Depends:** 3.1, 3.2

Run the complete test suite to verify nothing is broken:

```bash
uv run pytest tests/ -v --tb=short
```

Expected: All existing tests pass. All new tests pass:
- `tests/test_tv_auth.py` - 7 tests
- `tests/test_ws_client.py` - 13 tests
- `tests/test_level_calculations.py` - 12 tests
- `tests/test_ws_data_provider.py` - 5 tests
- `tests/test_realtime_tools.py` - 8 tests

**Commit:** none (verification only)

---

## Summary

| Batch | Tasks | Files Created/Modified | Parallel Implementers |
|-------|-------|----------------------|----------------------|
| 1 | 1.1, 1.2 | `pyproject.toml`, `tv_auth.py` + test | 2 |
| 2 | 2.1, 2.2, 2.3 | `ws_client.py`, `level_calc.py`, `ws_data_provider.py` + tests | 3 |
| 3 | 3.1, 3.2 | `realtime.py` + test, `server.py` (modify) | 2 |
| 4 | 4.1 | none (verification) | 1 |

**Total new files:** 4 source + 5 test = 9 files
**Total modified files:** 2 (`pyproject.toml`, `server.py`)
**Total micro-tasks:** 8 implementation + 1 verification = 9
