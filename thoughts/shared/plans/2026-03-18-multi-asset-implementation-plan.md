---
date: 2026-03-18
design: 2026-03-18-multi-asset-mcp-redesign.md
status: ready
---

# Multi-Asset MCP Redesign — Implementation Plan

## Phase 0: Foundation (Refactor + Validators + Symbols)

### Task 0.1: Expand Exchange Registry
**File:** `src/tradingview_mcp/core/utils/validators.py`
**Changes:**
- Add new entries to `EXCHANGE_SCREENER` dict:
  - `"cme_mini": "futures"`, `"cme": "futures"`, `"cbot": "futures"`
  - `"cboe": "cfd"`, `"sp": "cfd"`, `"tvc": "cfd"`
  - `"amex": "america"`, `"tsx": "canada"`
  - Keep all existing crypto + bist/nasdaq/nyse/malaysia/hongkong entries
- Add `EXCHANGE_ASSET_TYPE` dict mapping exchange keys to asset type strings: `"crypto"`, `"stock"`, `"etf"`, `"futures"`, `"index"`
- Add `get_asset_type(exchange: str) -> str` function
- Add `is_crypto_exchange(exchange: str) -> bool` helper
**Verify:** `python -c "from tradingview_mcp.core.utils.validators import EXCHANGE_SCREENER, get_asset_type; print(EXCHANGE_SCREENER['cme_mini']); print(get_asset_type('nasdaq'))"`

### Task 0.2: Create New Symbol List Files
**Files to create in** `src/tradingview_mcp/coinlist/`:

**amex.txt:**
```
AMEX:SPY
AMEX:SH
AMEX:GLD
AMEX:SLV
AMEX:SVIX
AMEX:UVIX
AMEX:SQQQ
AMEX:TQQQ
AMEX:DIA
AMEX:IWM
AMEX:XLF
AMEX:XLE
AMEX:XLK
AMEX:XLV
AMEX:XLI
AMEX:ARKK
AMEX:VXX
```

**cme.txt:**
```
CME_MINI:ES1!
CME_MINI:NQ1!
CME_MINI:YM1!
CME_MINI:RTY1!
CME:GC1!
CME:SI1!
CME:CL1!
CME:NG1!
CME:HG1!
CBOT:ZB1!
CBOT:ZN1!
CBOT:ZS1!
CBOT:ZC1!
CBOT:ZW1!
```

**indices.txt:**
```
CBOE:SPX
CBOE:VIX
CBOE:XSP
TVC:DJI
TVC:IXIC
TVC:RUT
TVC:FTSE
XETR:DAX
TVC:NI225
TVC:HSI
```

**tsx.txt:**
```
TSX:SU
TSX:RY
TSX:TD
TSX:ENB
TSX:CNR
TSX:BMO
TSX:BNS
TSX:CP
TSX:TRI
TSX:CSU
```

**Verify:** `python -c "from tradingview_mcp.core.services.coinlist import load_symbols; print(len(load_symbols('amex'))); print(len(load_symbols('cme')))"`

### Task 0.3: Rename coinlist.py to symbols.py (backward compatible)
**File:** `src/tradingview_mcp/core/services/coinlist.py` → keep as-is but add `symbols.py` as new module
**New file:** `src/tradingview_mcp/core/services/symbols.py`
**Changes:**
- Create `symbols.py` that imports and re-exports `load_symbols` from `coinlist.py`
- Add `format_symbol(exchange: str, symbol: str) -> str` function:
  - If symbol already contains `:`, return as-is
  - If crypto exchange and symbol doesn't end with `USDT`/`USDC`/`USD`, append `USDT`
  - Prepend `EXCHANGE:` prefix (uppercased)
- Add `get_screener_for_exchange(exchange: str) -> str` function (wraps EXCHANGE_SCREENER lookup with fallback)
**Verify:** `python -c "from tradingview_mcp.core.services.symbols import format_symbol; print(format_symbol('nasdaq', 'AAPL')); print(format_symbol('binance', 'BTC'))"`

### Task 0.4: Create tools/ directory with __init__.py
**Files to create:**
- `src/tradingview_mcp/tools/__init__.py` (empty)
- `src/tradingview_mcp/tools/shared.py` — shared analysis engine
**shared.py contents:**
- `fetch_and_analyze(exchange, timeframe, symbols, limit, filter_fn, sort_key, sort_reverse)` — generic scanner function
  - Sanitizes inputs
  - Resolves screener market from exchange
  - Calls `get_multiple_analysis` in batches of 200
  - Applies `compute_expanded_metrics` per symbol
  - Filters via `filter_fn`
  - Sorts by `sort_key`
  - Returns `[:limit]`
- `analyze_single(symbol, exchange, timeframe)` — single-symbol full analysis
  - Resolves screener, formats symbol
  - Calls `get_multiple_analysis` for one symbol
  - Returns full expanded metrics + composite signals
**Verify:** Import test: `python -c "from tradingview_mcp.tools.shared import fetch_and_analyze, analyze_single"`

### Task 0.5: Expand indicators.py
**File:** `src/tradingview_mcp/core/services/indicators.py`
**Changes:**
- Keep existing `compute_change`, `compute_bbw`, `compute_bb_rating_signal`, `compute_metrics` unchanged
- Add `compute_expanded_metrics(indicators: dict) -> dict | None` function that extracts:
  - All existing fields (price, change, bbw, rating, signal)
  - Trend: EMA10/20/50/100/200, SMA10/20/50/100/200, Supertrend, P.SAR, ADX, ADX+DI, ADX-DI, Ichimoku.BLine, Ichimoku.CLine
  - Momentum: RSI, MACD.macd, MACD.signal, Stoch.K, Stoch.D, CCI20, W.R, Mom, AO, HullMA9
  - Volatility: BB.upper, BB.lower, ATR, high, low
  - Volume: volume, volume (not much more available from TA)
  - Returns None on KeyError for required fields (open, close)
- Add `compute_composite_signals(metrics: dict) -> dict` function:
  - Trend strength from ADX: <20 "Ranging", 20-40 "Trending", >40 "Strong Trend"
  - Oscillator score: weighted RSI + Stoch + CCI + W.R → -100 to +100
  - Confluence signal: count of BUY/SELL across EMA crossovers, RSI zones, MACD cross, Supertrend direction → overall BUY/SELL/NEUTRAL with confidence %
- Add `compute_pivot_levels(indicators: dict) -> dict` function:
  - Extract Pivot.M.Classic.S1/S2/S3, R1/R2/R3, Middle
  - Extract Pivot.M.Fibonacci variants
  - Extract Pivot.M.Camarilla variants
  - Return structured dict with support/resistance levels
**Verify:** Unit test with mock indicator dict

## Phase 1: Tool Groups + Prefixed Names

### Task 1.1: Create crypto.py tool file
**File:** `src/tradingview_mcp/tools/crypto.py`
**Changes:**
- Define function `register_crypto_tools(mcp)` that takes the FastMCP instance
- Move/wrap all 10 existing tool functions from server.py into this file
- Register each with prefixed name: `@mcp.tool(name="crypto_top_gainers")`, etc.
- Default exchange for crypto tools: `"KUCOIN"`
- Use shared engine functions where possible
**Verify:** `python -c "from tradingview_mcp.tools.crypto import register_crypto_tools"`

### Task 1.2: Create stocks.py tool file
**File:** `src/tradingview_mcp/tools/stocks.py`
**Changes:**
- Define `register_stocks_tools(mcp)` function
- Tools: `stocks_top_gainers`, `stocks_top_losers`, `stocks_bollinger_scan`, `stocks_analysis`, `stocks_volume_breakout`, `stocks_smart_scanner`, `stocks_levels`
- Default exchange: `"NASDAQ"`
- Symbol normalization: no USDT append
- Use shared engine with `screener="america"`
**Verify:** `uv run python -c "from tradingview_mcp.tools.stocks import register_stocks_tools"`

### Task 1.3: Create futures.py tool file
**File:** `src/tradingview_mcp/tools/futures.py`
**Changes:**
- Define `register_futures_tools(mcp)` function
- Tools: `futures_analysis`, `futures_top_gainers`, `futures_top_losers`, `futures_volume_breakout`, `futures_levels`
- Default exchange: `"CME_MINI"`
- Symbol normalization: no USDT append, preserve `!` suffix
- Use shared engine with `screener="futures"`
**Verify:** `uv run python -c "from tradingview_mcp.tools.futures import register_futures_tools"`

### Task 1.4: Create indices.py tool file
**File:** `src/tradingview_mcp/tools/indices.py`
**Changes:**
- Define `register_indices_tools(mcp)` function
- Tools: `indices_analysis`, `indices_bollinger_scan`, `indices_rating_filter`, `indices_levels`
- Default exchange: `"CBOE"`
- Use shared engine with `screener="cfd"` (known workaround for index limitation)
- Add fallback: if direct analysis fails, try screener query path
**Verify:** `uv run python -c "from tradingview_mcp.tools.indices import register_indices_tools"`

### Task 1.5: Refactor server.py to use tool modules
**File:** `src/tradingview_mcp/server.py`
**Changes:**
- Keep FastMCP instance creation and `main()` function
- Remove all tool function bodies (moved to tools/*.py)
- Import and call `register_crypto_tools(mcp)`, `register_stocks_tools(mcp)`, etc.
- Keep legacy aliases: register unprefixed names that call crypto versions
  - `@mcp.tool(name="top_gainers")` → calls `crypto_top_gainers`
  - `@mcp.tool(name="coin_analysis")` → calls `crypto_analysis`
  - etc.
- Keep helper functions that are shared (`_map_indicators`, `_percent_change`, `_tf_to_tv_resolution`) or move them to `tools/shared.py`
- Update `exchanges_list` resource to include all new exchanges
**Verify:** `uv run python -m tradingview_mcp.server --help` (should start without errors)

### Task 1.6: Update screener_provider.py for multi-market
**File:** `src/tradingview_mcp/core/services/screener_provider.py`
**Changes:**
- `fetch_screener_indicators()`: add `market` parameter (default `"crypto"` for backward compat), replace hardcoded `.set_markets('crypto')` with `.set_markets(market)`
- `fetch_screener_multi_changes()`: same — add `market` parameter
- Update all callers to pass market from exchange resolver
**Verify:** `uv run python -c "from tradingview_mcp.core.services.screener_provider import fetch_screener_indicators"`

### Task 1.7: Update pyproject.toml package data
**File:** `pyproject.toml`
**Changes:**
- Ensure `coinlist/*.txt` glob still picks up new files (amex.txt, cme.txt, indices.txt, tsx.txt)
- It should already work since the pattern is `"coinlist/*.txt"` — verify
**Verify:** `uv build` and check the wheel includes new txt files

## Phase 2: News + ORB Predictor + Composite Signals

### Task 2.1: Add finnhub dependency
**File:** `pyproject.toml`
**Changes:**
- Add `"finnhub-python>=2.4.0"` to `dependencies` list
**Verify:** `uv sync && python -c "import finnhub"`

### Task 2.2: Create news_provider.py
**File:** `src/tradingview_mcp/core/services/news_provider.py`
**Changes:**
- `FINNHUB_API_KEY` read from `os.environ.get("FINNHUB_API_KEY")`
- `is_news_available() -> bool` — checks if API key is set
- `get_market_news(category: str = "general", limit: int = 20) -> list[dict]` — calls `finnhub_client.general_news(category)`
- `get_ticker_news(symbol: str, days_back: int = 7, limit: int = 10) -> list[dict]` — calls `finnhub_client.company_news(symbol, from, to)`
- `get_news_sentiment(symbol: str) -> dict` — calls `finnhub_client.news_sentiment(symbol)` if available
- Each function returns normalized dicts: `{headline, source, url, datetime, summary, sentiment_score}`
- Error handling: catch API errors, return structured error dicts
**Verify:** `FINNHUB_API_KEY=test python -c "from tradingview_mcp.core.services.news_provider import is_news_available; print(is_news_available())"`

### Task 2.3: Create news.py tool file
**File:** `src/tradingview_mcp/tools/news.py`
**Changes:**
- Define `register_news_tools(mcp)` function
- `news_market_sentiment(category, limit)` — overall market news + aggregate sentiment
- `news_ticker_impact(symbol, limit)` — per-ticker news with sentiment scores
- `news_breaking(limit)` — latest breaking headlines across all categories
- Each tool checks `is_news_available()` first, returns config error if not
**Verify:** Register and list tools

### Task 2.4: Create orb_predictor.py
**File:** `src/tradingview_mcp/core/services/orb_predictor.py`
**Changes:**
- `calculate_orb_levels(open_price, high, low, atr, session_open=None) -> dict`:
  - range_estimate = ATR if no session candle data, else (high - low) of opening period
  - small_range_high = open + (range × 0.5)
  - small_range_low = open - (range × 0.5)
  - range_high = open + (range × 1.0)
  - range_low = open - (range × 1.0)
  - large_range_high = open + (range × 1.5)
  - large_range_low = open - (range × 1.5)
  - Return dict with all 6 levels + metadata
**Verify:** Unit test with known values

### Task 2.5: Add ORB predictor tool to futures.py
**File:** `src/tradingview_mcp/tools/futures.py`
**Changes:**
- Add `futures_orb_predictor(symbol, exchange, timeframe)` tool
- Fetches current OHLCV + ATR via `get_multiple_analysis`
- Calls `calculate_orb_levels`
- Returns predicted levels
**Verify:** `futures_orb_predictor(symbol="ES1!", exchange="CME_MINI")`

### Task 2.6: Wire composite signals into analysis tools
**File:** `src/tradingview_mcp/tools/shared.py`
**Changes:**
- `analyze_single()` now also calls `compute_composite_signals()` and `compute_pivot_levels()`
- Response includes: `trend_strength`, `oscillator_score`, `confluence_signal`, `support_resistance_levels`
**Verify:** Call any `*_analysis` tool and check response includes composite fields

## Phase 3: Polish + Tests

### Task 3.1: Add levels tools to each group
**Files:** `tools/stocks.py`, `tools/futures.py`, `tools/indices.py`
**Changes:**
- Each group gets a `{group}_levels(symbol, exchange, timeframe)` tool
- Calls `analyze_single` → extracts `compute_pivot_levels` portion
- Returns structured support/resistance levels (Classic, Fibonacci, Camarilla)
**Verify:** Call `stocks_levels(symbol="AAPL", exchange="NASDAQ")`

### Task 3.2: Add auth cookie passthrough
**Files:** `tools/shared.py`, `tools/*.py` (all tool files using screener)
**Changes:**
- Add optional `tv_session_id: str = ""` parameter to tools that use screener queries
- Pass as `cookies={"sessionid": tv_session_id}` when non-empty
- Update screener_provider functions to accept and pass cookies
**Verify:** Call tool with and without session_id

### Task 3.3: Create comprehensive test suite
**Files to create:**
- `tests/test_validators.py` — exchange registry, asset type detection, symbol formatting
- `tests/test_indicators.py` — expanded metrics, composite signals, pivot levels
- `tests/test_crypto_tools.py` — crypto tool group (mock API responses)
- `tests/test_stocks_tools.py` — stocks tool group
- `tests/test_futures_tools.py` — futures tool group
- `tests/test_indices_tools.py` — indices tool group
- `tests/test_news_tools.py` — news tools with mocked Finnhub
- `tests/test_orb_predictor.py` — ORB calculator unit tests
- `tests/test_integration.py` — one real API call per asset class (smoke test)
- `tests/test_legacy_aliases.py` — unprefixed names still work
**Verify:** `uv run pytest tests/`

### Task 3.4: Update README.md
**File:** `README.md`
**Changes:**
- Add new tool groups to Available Tools section
- Add stocks/futures/indices/ETF examples
- Add news tools section
- Update Supported Markets table
- Add FINNHUB_API_KEY configuration instructions
- Add note about legacy aliases
**Verify:** Read and review

### Task 3.5: Update exchanges_list resource
**File:** `src/tradingview_mcp/server.py` (or wherever resource is registered)
**Changes:**
- `exchanges_list` resource returns all exchanges grouped by asset type
- Include new exchanges: CME_MINI, CME, CBOT, CBOE, AMEX, TSX
- Group output: Crypto, Stocks, ETFs, Futures, Indices
**Verify:** Call `exchanges://list` resource

## Execution Order

Tasks within each phase can be parallelized where they don't share files:

**P0 parallel batch 1:** Task 0.1, 0.2, 0.4 (different files)
**P0 sequential after batch 1:** Task 0.3, 0.5 (depend on 0.1)

**P1 parallel batch 1:** Task 1.1, 1.2, 1.3, 1.4 (separate tool files)
**P1 sequential after batch 1:** Task 1.5, 1.6, 1.7 (depend on tool files existing)

**P2 parallel batch 1:** Task 2.1, 2.4 (independent)
**P2 sequential:** Task 2.2 (after 2.1), 2.3 (after 2.2), 2.5 (after 2.4), 2.6

**P3 parallel batch 1:** Task 3.1, 3.2, 3.4 (independent)
**P3 sequential:** Task 3.3 (after all tools exist), 3.5
