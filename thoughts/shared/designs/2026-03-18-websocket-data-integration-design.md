---
date: 2026-03-18
topic: "WebSocket Data Integration for TradingView MCP"
status: validated
---

# WebSocket Data Integration for TradingView MCP

## Problem Statement

The current MCP server uses HTTP-based libraries (`tradingview-ta` and `tradingview-screener`) that only return daily-level indicator snapshots from TradingView's screener endpoint. This means:

- Futures intraday timeframes (5m, 15m, 30m) consistently fail for continuous contracts like ES1!, NQ1!, YM1!
- Pivot/support/resistance levels are calculated from daily OHLC, producing ranges too wide for intraday trading (e.g., 6,337–7,440 vs the actual session range of ~6,637–6,695)
- Custom indicators (LuxAlgo, Intraday High-Low Predictor) are inaccessible
- No real OHLCV bar data is available — only pre-computed indicator values

The user needs levels and analysis that match what they see on their TradingView charts.

## Constraints

- Must integrate with existing MCP server architecture (FastMCP, `register_*_tools` pattern)
- Must not break existing screener-based tools — additive only
- TradingView WebSocket API is undocumented/reverse-engineered — protocol can change
- Session cookies expire — need clear error messaging when auth fails
- Rate limits are undocumented — must be conservative (5-10s between heavy requests)
- TradingView ToS prohibits scraping — user accepts this risk for personal use
- Must work with user's existing TradingView session cookie

## Approach

Add a new WebSocket service layer that connects to `wss://data.tradingview.com/socket.io/websocket` using the user's session cookie. This runs alongside (not replacing) the existing screener-based tools.

**Why WebSocket over other approaches:**
- Only way to get real OHLCV bars at intraday timeframes for futures
- Only way to potentially read study/indicator output values
- Battle-tested protocol used by tvdatafeed (584 stars) and TradingView-API (2,900 stars)
- Session cookie authentication is already plumbed through the codebase

**Rejected alternatives:**
- TradingView Charting Library API: Requires commercial license, meant for embedding charts, doesn't expose data access
- Enhancing screener queries: Screener endpoint fundamentally doesn't serve OHLCV bars or intraday futures data

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   server.py                      │
│  register_realtime_tools(mcp)  ← NEW            │
│  register_crypto_tools(mcp)    ← existing        │
│  register_futures_tools(mcp)   ← existing        │
│  register_stocks_tools(mcp)    ← existing        │
│  register_indices_tools(mcp)   ← existing        │
└──────────┬──────────────────────┬────────────────┘
           │                      │
    ┌──────▼──────┐        ┌──────▼──────┐
    │ tools/      │        │ tools/      │
    │ realtime.py │  NEW   │ futures.py  │ existing
    └──────┬──────┘        └──────┬──────┘
           │                      │
    ┌──────▼──────────┐    ┌──────▼──────────┐
    │ core/services/  │    │ core/services/  │
    │ ws_client.py    │NEW │ screener_prov.  │ existing
    │ ws_data_prov.py │NEW │ indicators.py   │ existing
    └──────┬──────────┘    └─────────────────┘
           │
    ┌──────▼──────────┐
    │  TradingView    │
    │  WebSocket API  │
    │  wss://data.    │
    │  tradingview.com│
    └─────────────────┘
```

## Components

### 1. WebSocket Client — `core/services/ws_client.py`

**Responsibility:** Low-level WebSocket connection management and TradingView protocol handling.

- Connects to `wss://data.tradingview.com/socket.io/websocket?type=chart`
- Implements TradingView's custom framing protocol: `~m~<length>~m~<payload>`
- Handles authentication flow: session cookie → auth_token extraction → `set_auth_token`
- Manages heartbeat ping/pong to maintain connection
- Creates/destroys chart sessions (`cs_*`) and quote sessions (`qs_*`)
- Sends protocol messages: `resolve_symbol`, `create_series`, `create_study`, etc.
- Parses inbound messages: `timescale_update`, `du`, `series_completed`, `study_completed`
- Auto-reconnects on connection drop with exponential backoff

**Key design decisions:**
- Synchronous WebSocket (using `websocket-client` library) — matches existing sync patterns in the codebase
- Single connection per server instance, reused across tool calls
- Session IDs generated as random 12-char lowercase strings with `cs_`/`qs_` prefix

### 2. Data Provider — `core/services/ws_data_provider.py`

**Responsibility:** High-level data access interface built on the WebSocket client.

- `get_bars(symbol, exchange, timeframe, count)` → list of OHLCV dicts
- `get_quote(symbol, exchange)` → current price, change, volume
- `get_session_levels(symbol, exchange)` → computed intraday levels from real bars:
  - Prior day high/low/close
  - Current session open/high/low
  - Opening range levels (5min, 15min, 30min high/low)
  - VWAP from session bars
  - Camarilla/Fibonacci pivots from prior session OHLC
- Connection lifecycle: lazy connect on first call, reuse, reconnect on failure
- Caching layer: bars cached for 30 seconds to avoid redundant WebSocket requests

**Symbol resolution:**
- Maps user-friendly symbols to TradingView format: `ES1!` → `CME_MINI:ES1!`
- Reuses existing `core/services/symbols.py` for exchange/screener mapping where possible
- Adds futures-specific continuous contract handling

### 3. Realtime Tools — `tools/realtime.py`

**Responsibility:** MCP tool definitions that expose WebSocket data to the user.

Registered via `register_realtime_tools(mcp)` following existing conventions.

**Tool: `realtime_levels`**
- Parameters: `symbol` (required), `exchange` (default CME_MINI), `timeframe` (default 30m), `tv_session_id` (required)
- Returns: Session-based support/resistance levels computed from actual bars
- Output includes: prior day H/L/C, opening range levels, session VWAP, intraday pivots
- Matches the tight ranges users see on their charts (e.g., 6,637–6,695 for ES)

**Tool: `realtime_bars`**
- Parameters: `symbol` (required), `exchange` (default CME_MINI), `timeframe` (default 15m), `count` (default 100, max 5000), `tv_session_id` (required)
- Returns: Raw OHLCV bar data as list of dicts with timestamp, open, high, low, close, volume

**Tool: `realtime_analysis`**
- Parameters: `symbol` (required), `exchange` (default CME_MINI), `timeframe` (default 15m), `tv_session_id` (required)
- Returns: Technical analysis computed from real bars — RSI, MACD, Bollinger Bands, EMAs, etc.
- Reuses `core/services/indicators.py` computation functions where possible, fed with real OHLCV data

**Error handling:**
- All tools return `{"error": "..."}` dicts on failure (matching existing convention)
- Clear error messages for: session expired, symbol not found, connection timeout, rate limited
- Falls back gracefully — never raises exceptions to the MCP framework

### 4. Authentication Module — `core/services/tv_auth.py`

**Responsibility:** Extract auth_token from TradingView session cookie.

- Takes `sessionid` cookie string
- Makes HTTP GET to `https://www.tradingview.com` with cookie
- Scrapes `auth_token` from embedded JSON in page HTML
- Caches the auth_token (valid for session lifetime)
- Returns clear error if session is expired or invalid
- Also supports `TV_SESSION_ID` environment variable as default

## Data Flow

### Getting Intraday Levels (Primary Use Case)

1. User calls `realtime_levels(symbol="ES1!", tv_session_id="...")`
2. `tools/realtime.py` validates inputs, calls `ws_data_provider.get_session_levels()`
3. Provider checks if WebSocket is connected; if not, calls `tv_auth.py` to get auth_token
4. `ws_client.py` connects to WebSocket, authenticates, creates chart session
5. Client sends `resolve_symbol` → `create_series` for 30m bars (100 bars = ~2 trading days)
6. Client receives `timescale_update` with bar data, waits for `series_completed`
7. Provider parses bars, identifies prior session and current session boundaries
8. Provider computes: prior day H/L/C, opening range, session VWAP, intraday pivots
9. Tool formats response matching existing output patterns and returns to user

### Connection Reuse

- First call establishes WebSocket connection and chart session
- Subsequent calls reuse the same connection
- New symbols use `resolve_symbol` + `create_series` on the existing chart session
- If connection drops, next call triggers auto-reconnect

## Error Handling

| Error Scenario | Handling |
|---|---|
| Session cookie expired | Return `{"error": "TradingView session expired. Please provide a fresh sessionid cookie."}` |
| Symbol not found | Return `{"error": "Symbol CME_MINI:XYZ not found on TradingView"}` |
| WebSocket connection timeout | Retry once with 5s delay, then return error |
| Rate limited / throttled | Return `{"error": "TradingView rate limit hit. Wait 30 seconds and retry."}` |
| No session ID provided | Return `{"error": "tv_session_id is required for realtime tools. Get it from your browser cookies."}` |
| Heartbeat timeout | Auto-reconnect, retry the request |
| Malformed response data | Log warning, return `{"error": "Unexpected response format from TradingView"}` |

## Testing Strategy

### Unit Tests (`tests/test_realtime_tools.py`)
- Mock WebSocket responses with pre-recorded TradingView message payloads
- Test framing protocol encode/decode (`~m~<len>~m~` format)
- Test bar parsing from `timescale_update` responses
- Test level calculations from known bar data
- Test error handling for all failure scenarios
- Use `DummyMCP` pattern matching existing tests

### Integration Tests (`tests/test_realtime_integration.py`)
- Opt-in tests that require `TV_SESSION_ID` environment variable
- Connect to real WebSocket, pull ES1! bars, verify data shape
- Marked with `@pytest.mark.skipif` when no session is configured

### Level Calculation Tests (`tests/test_level_calculations.py`)
- Pure computation tests with known OHLCV input data
- Verify prior day H/L/C extraction
- Verify opening range calculation
- Verify VWAP computation
- Verify pivot calculations match expected values

## Dependencies

New dependency to add to `pyproject.toml`:
- `websocket-client` — synchronous WebSocket client library (well-maintained, 3.5k stars)

No other new dependencies required. HTTP requests for auth use Python's built-in `urllib` or existing `requests` if already available.

## Configuration

```
# Environment variable (recommended — set once)
TV_SESSION_ID=74mebzwbarieviszuloge07x7uhspfco

# Or pass per-call via tool parameter
tv_session_id="74mebzwbarieviszuloge07x7uhspfco"
```

Tool parameter takes precedence over environment variable when both are set.

## Open Questions

1. **Study/indicator support in Phase 1?** — I'm deferring custom indicator reading (LuxAlgo, etc.) to a follow-up. Phase 1 focuses on OHLCV bars and computed levels. The WebSocket protocol supports `create_study` but parsing arbitrary Pine Script output is complex.

2. **Connection pooling** — Single connection should suffice for now. If the user needs to query many symbols rapidly, we may need connection pooling later.

3. **Session cookie refresh** — Currently the user must manually provide a new cookie when it expires. An auto-refresh mechanism could be built later using `rookiepy` to read browser cookies, but that adds complexity and platform-specific dependencies.
