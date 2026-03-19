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
