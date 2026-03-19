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
from typing import Any, Dict, List

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
        pos += msg_len

        # TradingView heartbeat payloads are sometimes framed as:
        # ~m~3~m~~h~1
        # where length=3 covers "~h~" and the heartbeat id follows directly.
        # Capture that trailing id until the next frame delimiter.
        if msg == "~h~" and pos < len(raw):
            next_frame = raw.find("~m~", pos)
            if next_frame == -1:
                msg += raw[pos:]
                pos = len(raw)
            else:
                msg += raw[pos:next_frame]
                pos = next_frame

        messages.append(msg)

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
    for _, series_data in data_block.items():
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
        self._send_raw(_build_message("set_auth_token", [auth_token]))

        # Create chart session
        self._chart_session = generate_session_id("cs")
        self._send_raw(_build_message("chart_create_session", [self._chart_session, ""]))

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
