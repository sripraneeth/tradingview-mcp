---
date: 2026-03-18
topic: "Multi-asset MCP redesign with specialized tool groups, expanded indicators, and news integration"
status: validated
supersedes: 2026-03-18-multi-market-tool-registration-design.md
---

## Problem Statement

The MCP server currently serves crypto-only analysis. We need to expand it to support **stocks, indices, futures, and ETFs** with the same quality of analysis, plus add a **news/sentiment layer** that TradingView's API does not provide.

Additionally, the current indicator coverage is thin (~15 indicators used out of 90+ available). Users with professional chart setups (EMA, Supertrend, MACD Strategy, Bollinger Bands, RSI, LuxAlgo, S&D Levels, Pi Intraday Predictor) expect richer analysis output.

## Constraints

- Zero breaking changes for existing crypto tool consumers.
- Single deployable MCP server process (one FastMCP instance).
- No custom Pine Script indicators accessible via API (LuxAlgo, Pi Predictor, S&D Levels are proprietary). Must approximate with available built-in indicators.
- TradingView TA library does NOT support index analysis directly (known limitation documented in issues #67, #84). Indices must use the screener path or CFD/futures equivalents.
- News requires an external API — TradingView libraries have zero news functionality (confirmed via source inspection).

## Approach

**Single FastMCP instance with 5 prefixed tool groups** plus a shared analysis engine.

Each asset class gets its own tool file with tools registered using explicit `name=` prefixes (`crypto_*`, `stocks_*`, `futures_*`, `indices_*`, `news_*`). Legacy unprefixed names remain as aliases pointing to crypto tools during migration.

The core analysis logic is extracted into a shared engine so each tool group is thin configuration over common code.

News integration uses **Finnhub API** as primary source (free tier: 60 calls/min, company news + sentiment scores, market news). Fallback: Alpha Vantage News Sentiment API.

I rejected splitting into multiple MCP servers because it adds orchestration overhead. I rejected keeping a single generic `AI_analysis` tool because specialized tools give AI agents better intent matching.

## Architecture

Single process, single FastMCP server, modular internal structure:

```
src/tradingview_mcp/
├── server.py                    # FastMCP instance, imports & registers all tool groups
├── core/
│   ├── services/
│   │   ├── symbols.py           # Renamed from coinlist.py — generic symbol loader
│   │   ├── indicators.py        # Expanded — 40+ indicator extraction
│   │   ├── screener_provider.py # Updated — market-aware screener queries
│   │   ├── news_provider.py     # NEW — Finnhub API integration
│   │   └── orb_predictor.py     # NEW — Opening Range Breakout calculator
│   └── utils/
│       └── validators.py        # Expanded exchange registry + asset type detection
├── tools/
│   ├── crypto.py                # crypto_* tools (extracted from current server.py)
│   ├── stocks.py                # stocks_* tools
│   ├── indices.py               # indices_* tools
│   ├── futures.py               # futures_* tools
│   ├── news.py                  # news_* tools
│   └── shared.py                # Shared analysis engine (fetch → compute → filter → sort)
├── coinlist/                    # Symbol universe files
│   ├── binance.txt              # Existing crypto
│   ├── kucoin.txt               # Existing crypto
│   ├── nasdaq.txt               # NEW — top stocks
│   ├── nyse.txt                 # NEW — top stocks
│   ├── amex.txt                 # NEW — ETFs (SPY, GLD, SH, SVIX, UVIX)
│   ├── cme.txt                  # NEW — futures (ES1!, NQ1!, etc.)
│   ├── indices.txt              # NEW — global indices
│   └── ...existing crypto files
```

## Components

### 1. Expanded Exchange Registry (validators.py)

Owns exchange → screener market mapping, asset type classification, and symbol normalization rules.

New mappings (verified via live scanner probes):

| Exchange Key | Screener Domain | Asset Type | Example Symbols |
|---|---|---|---|
| `cme_mini` | `futures` | futures | `CME_MINI:ES1!`, `CME_MINI:NQ1!` |
| `cme` | `futures` | futures | `CME:GC1!`, `CME:CL1!` |
| `cbot` | `futures` | futures | `CBOT:ZB1!`, `CBOT:ZN1!` |
| `cboe` | `cfd` | index | `CBOE:SPX`, `CBOE:VIX`, `CBOE:XSP` |
| `amex` | `america` | stock/etf | `AMEX:SPY`, `AMEX:GLD`, `AMEX:SH`, `AMEX:SVIX`, `AMEX:UVIX` |
| `nasdaq` | `america` | stock | `NASDAQ:AAPL`, `NASDAQ:MSFT`, `NASDAQ:NVDA`, `NASDAQ:QQQ` |
| `nyse` | `america` | stock | `NYSE:SU` |
| `tsx` | `canada` | stock | `TSX:SU` |
| All existing crypto exchanges | `crypto` | crypto | unchanged |

Asset type detection function: given an exchange key, returns `crypto`, `stock`, `etf`, `futures`, or `index`. This drives symbol normalization (only crypto appends `USDT`).

### 2. Symbol Universe Files

New symbol list files for non-crypto assets:

**amex.txt** — ETFs and volatility products:
`AMEX:SPY`, `AMEX:SH`, `AMEX:GLD`, `AMEX:SLV`, `AMEX:SVIX`, `AMEX:UVIX`, `AMEX:SQQQ`, `AMEX:TQQQ`, `AMEX:DIA`, `AMEX:IWM`, `AMEX:XLF`, `AMEX:XLE`, `AMEX:XLK`

**nasdaq.txt** — Top tech + growth stocks:
`NASDAQ:AAPL`, `NASDAQ:MSFT`, `NASDAQ:NVDA`, `NASDAQ:AMZN`, `NASDAQ:GOOGL`, `NASDAQ:META`, `NASDAQ:TSLA`, `NASDAQ:QQQ`, `NASDAQ:AVGO`, `NASDAQ:AMD`, `NASDAQ:NFLX`, `NASDAQ:COST`, `NASDAQ:INTC`

**cme.txt** — Key futures contracts:
`CME_MINI:ES1!`, `CME_MINI:NQ1!`, `CME_MINI:YM1!`, `CME:GC1!`, `CME:SI1!`, `CME:CL1!`, `CBOT:ZB1!`, `CBOT:ZN1!`

**indices.txt** — Major global indices:
`CBOE:SPX`, `CBOE:VIX`, `CBOE:XSP`, `TVC:DJI`, `TVC:IXIC`, `TVC:RUT`

**nyse.txt** — Blue chip stocks:
`NYSE:JPM`, `NYSE:BAC`, `NYSE:WMT`, `NYSE:JNJ`, `NYSE:UNH`, `NYSE:V`, `NYSE:MA`, `NYSE:PG`, `NYSE:HD`, `NYSE:DIS`, `NYSE:SU`

### 3. Expanded Indicator Engine (indicators.py)

Currently extracts ~15 indicators. Expanding to full suite organized by category:

**Trend Indicators:**
- EMA (10, 20, 50, 100, 200)
- SMA (10, 20, 50, 100, 200)
- Supertrend
- Ichimoku (Conversion, Base, Lead A, Lead B)
- Parabolic SAR (P.SAR)
- ADX, +DI, -DI

**Momentum Indicators:**
- RSI
- MACD (macd, signal, histogram)
- Stochastic (K, D)
- CCI (20)
- Williams %R
- Momentum (10)
- ROC (Rate of Change)

**Volatility Indicators:**
- Bollinger Bands (upper, lower, width — already core)
- ATR (14)
- High/Low range (daily, weekly)

**Volume Indicators:**
- Volume
- Volume SMA20
- VWMA (Volume Weighted Moving Average)

**Support/Resistance (approximating S&D Levels):**
- Pivot Points Classic (S1/S2/S3, R1/R2/R3, P)
- Pivot Points Fibonacci
- Pivot Points Camarilla
- Monthly, Weekly, Daily variants

**Composite Signals (approximating LuxAlgo):**
- Trend Strength Score: ADX + directional movement → "Ranging", "Trending", "Strong Trend" with percentage
- Multi-Indicator Confluence: weighted combination of RSI + Stochastic + MACD + Supertrend → BUY/SELL/NEUTRAL with confidence score
- Oscillator Matrix: RSI + CCI + Williams %R + Stochastic combined into a -100 to +100 composite score

### 4. Opening Range Breakout Predictor (orb_predictor.py)

Approximates the Pi Intraday High-Low Predictor visible on user's chart.

Logic:
1. Fetch the first N-minute candle range after session open (configurable: 5, 15, 30 min).
2. Calculate range = high - low of opening candle.
3. Apply multipliers to project predicted levels:
   - Small Range: open_high ± (range × 0.5), open_low ± (range × 0.5)
   - Range: open_high ± (range × 1.0), open_low ± (range × 1.0)
   - Large Range: open_high ± (range × 1.5), open_low ± (range × 1.5)
4. Optionally weight by ATR for volatility-adjusted predictions.

Returns: predicted high/low for small/medium/large range scenarios.

Limitation: requires intraday data which `get_multiple_analysis` provides as snapshot, not historical candles. For accurate ORB, we use the current session's open + ATR to estimate. This is an approximation, not exact.

### 5. News Provider (news_provider.py)

Primary: **Finnhub API** (`finnhub-python` package).

Capabilities:
- `market_news(category="general")` — market-wide headlines
- `company_news(symbol, from_date, to_date)` — per-ticker news
- `news_sentiment(symbol)` — pre-computed sentiment scores per article
- Response includes: headline, source, url, datetime, summary, sentiment

Configuration:
- API key via `FINNHUB_API_KEY` environment variable
- Free tier: 60 API calls/minute, sufficient for MCP usage
- Graceful degradation: if key not set, news tools return informative error

Fallback: If Finnhub is unavailable, consider Alpha Vantage `NEWS_SENTIMENT` endpoint as secondary source.

### 6. Tool Groups

#### crypto_* (extracted from current server.py)
- `crypto_top_gainers` — existing top_gainers logic
- `crypto_top_losers` — existing top_losers logic
- `crypto_bollinger_scan` — existing bollinger_scan logic
- `crypto_rating_filter` — existing rating_filter logic
- `crypto_analysis` — existing coin_analysis, expanded indicators
- `crypto_consecutive_candles` — existing consecutive_candles_scan
- `crypto_advanced_pattern` — existing advanced_candle_pattern
- `crypto_volume_breakout` — existing volume_breakout_scanner
- `crypto_volume_analysis` — existing volume_confirmation_analysis
- `crypto_smart_scanner` — existing smart_volume_scanner

Legacy aliases: `top_gainers` → `crypto_top_gainers`, `coin_analysis` → `crypto_analysis`, etc.

#### stocks_* (new)
- `stocks_top_gainers` — top movers on NASDAQ/NYSE/AMEX
- `stocks_top_losers` — biggest decliners
- `stocks_bollinger_scan` — squeeze detection on stocks
- `stocks_analysis` — full indicator suite for any stock symbol
- `stocks_volume_breakout` — volume + price breakout on stocks
- `stocks_smart_scanner` — multi-indicator confluence on stocks
- `stocks_levels` — pivot point support/resistance levels

#### futures_* (new)
- `futures_analysis` — full indicator suite for futures
- `futures_top_gainers` — top movers in futures universe
- `futures_top_losers` — biggest decliners
- `futures_volume_breakout` — volume breakout on futures
- `futures_orb_predictor` — Opening Range Breakout predicted levels
- `futures_levels` — pivot point support/resistance

#### indices_* (new)
- `indices_analysis` — full indicator suite for indices (via screener/CFD path)
- `indices_bollinger_scan` — squeeze detection on indices
- `indices_rating_filter` — BB rating filter on indices
- `indices_levels` — pivot point support/resistance

Note: indices have a known limitation with `tradingview-ta` direct analysis. We route through the screener path (`set_markets("cfd")` or `set_markets("america")`) to get indicator data.

#### news_* (new)
- `news_market_sentiment` — overall market news + sentiment summary
- `news_ticker_impact` — news for a specific symbol with sentiment scores
- `news_breaking` — latest N breaking headlines across markets

### 7. Shared Analysis Engine (tools/shared.py)

Extracts the common pattern used by all scanner/analysis tools:

1. Sanitize inputs (exchange, timeframe, limits)
2. Resolve market domain from exchange
3. Load symbol universe (or use provided symbol)
4. Fetch data via `get_multiple_analysis` or screener query
5. Compute expanded metrics
6. Apply filters (BBW threshold, rating, volume ratio, etc.)
7. Sort and limit results
8. Return normalized response

Each tool group file becomes thin: just configuration (default exchange, asset type, tool name) calling into shared engine functions.

### 8. Auth Cookie Passthrough

Add optional `tv_session_id` parameter to tools that use the `tradingview-screener` Query path. This enables:
- Access to premium screener data
- More reliable data for some exchanges
- Extended symbol coverage

Implementation: pass as `cookies={"sessionid": tv_session_id}` to `q.get_scanner_data(cookies=...)`.

For basic `get_multiple_analysis` calls (majority of tools), no auth needed.

## Data Flow

### Scanner Tool Flow (e.g., stocks_top_gainers)
```
Client calls stocks_top_gainers(exchange="NASDAQ", timeframe="1D", limit=10)
  → sanitize_inputs("NASDAQ", "1D", 10)
  → resolve_market("nasdaq") → "america"
  → load_symbols("nasdaq") → ["NASDAQ:AAPL", "NASDAQ:MSFT", ...]
  → get_multiple_analysis(screener="america", interval="1D", symbols=[...])
  → compute_expanded_metrics(raw_indicators) for each symbol
  → sort by changePercent descending
  → return top 10 with full indicator payload
```

### Single-Symbol Analysis Flow (e.g., futures_analysis)
```
Client calls futures_analysis(symbol="ES1!", exchange="CME_MINI", timeframe="30m")
  → resolve_market("cme_mini") → "futures"
  → format_symbol("CME_MINI", "ES1!") → "CME_MINI:ES1!"
  → get_multiple_analysis(screener="futures", interval="30m", symbols=["CME_MINI:ES1!"])
  → compute_expanded_metrics(raw_indicators)
  → compute_composite_signals(metrics)
  → compute_pivot_levels(metrics)
  → return full analysis payload
```

### News Flow (e.g., news_ticker_impact)
```
Client calls news_ticker_impact(symbol="AAPL", limit=10)
  → finnhub.company_news("AAPL", from=today-7d, to=today)
  → for each article: extract headline, source, datetime, sentiment
  → compute aggregate sentiment score
  → return { articles: [...], aggregate_sentiment: {...}, symbol: "AAPL" }
```

### ORB Predictor Flow (e.g., futures_orb_predictor)
```
Client calls futures_orb_predictor(symbol="ES1!", exchange="CME_MINI")
  → fetch current session OHLCV + ATR via get_multiple_analysis
  → calculate opening range from open + ATR-based estimate
  → apply small/medium/large multipliers
  → return predicted high/low levels for each range tier
```

## Error Handling

**Validation errors:** Return deterministic user-facing errors for invalid exchange/timeframe/symbol. Include list of valid options in error message.

**Missing symbol lists:** Return `{"error": "No symbols configured for exchange X", "available_exchanges": [...]}`.

**Provider failures:** Per-batch swallowing for scanner tools (existing pattern). Single-symbol tools return structured error with details.

**News API failures:**
- Missing API key: `{"error": "News service not configured. Set FINNHUB_API_KEY environment variable."}`
- API error: `{"error": "News service unavailable", "fallback": "technical_analysis_only"}`
- Rate limit: `{"error": "News API rate limit reached. Try again in 60 seconds."}`

**Index analysis limitations:** If direct TA analysis fails for an index symbol, automatically retry via screener/CFD path. Return partial data with warning if some indicators unavailable.

**Auth required:** If screener query fails with auth error and no session provided: `{"error": "TradingView session required for this query. Pass tv_session_id parameter."}`.

## Testing Strategy

### Unit Tests
- Expanded exchange registry validation (all new exchanges map correctly)
- Asset type detection (crypto vs stock vs futures vs index)
- Symbol normalization (USDT append only for crypto)
- Indicator extraction for expanded set
- Composite signal calculation
- ORB predictor math
- Pivot point calculation

### Integration Tests (per tool group)
- One real API call per asset class to verify end-to-end
- `crypto_analysis("BTCUSDT", "BINANCE")` — baseline
- `stocks_analysis("AAPL", "NASDAQ")` — stocks
- `futures_analysis("ES1!", "CME_MINI")` — futures
- `indices_analysis("SPX", "CBOE")` — indices (may need screener path)

### Mock Tests
- News provider with mocked Finnhub responses
- Scanner tools with mocked `get_multiple_analysis` returns
- Error path coverage (missing symbols, API failures, rate limits)

### Contract Tests
- All prefixed tool names are registered and discoverable
- Legacy aliases still work
- Response shapes are consistent across tool groups

## Dependencies

New package additions to `pyproject.toml`:
- `finnhub-python` — Finnhub API client for news/sentiment

No other new dependencies. All indicator data comes from existing `tradingview-ta` and `tradingview-screener` libraries.

## Migration Plan

Phase 1 (P0): Refactor server.py into modular structure, expand validators, create symbol lists. All existing tools continue working with no name changes.

Phase 2 (P1): Register prefixed tool names. Legacy names become aliases. Add stocks, futures, indices tool groups. Expand indicator engine.

Phase 3 (P2): Add news provider and news tools. Add ORB predictor. Add composite signal scoring.

Phase 4 (P3): Add pivot point levels tools. Polish response formats. Comprehensive test suite.

## Open Questions

- Finnhub free tier rate limit (60/min) may be tight if multiple news tools are called rapidly. Consider caching recent news responses for 5 minutes.
- Index analysis reliability via screener/CFD path needs validation — `tradingview-ta` explicitly warns indices are not fully supported.
- Legacy alias sunset timeline — suggest keeping for 3 months minimum.
