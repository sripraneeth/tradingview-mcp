---
session: ses_2fc4
updated: 2026-03-19T01:30:43.232Z
---

# Session Summary

## Goal
Produce a comprehensive architecture analysis of the TradingView MCP server (structure, tool registration, tool patterns, core services, dependencies, WebSocket/realtime status, and test conventions) so a new WebSocket-based module can be designed to fit existing conventions.

## Constraints & Preferences
- Follow existing MCP registration and naming conventions (`register_*_tools`, `@mcp.tool()`, market-prefixed tool names).
- Preserve exact file paths and function names in the handoff.
- Focus on architecture and conventions needed to continue implementation seamlessly.
- No code modifications yet; analysis-only pass so far.
- User wants explicit coverage of: project structure, `server.py` registration pattern, `crypto.py` + `futures.py` return/error patterns, `screener_provider`, dependencies, WebSocket/realtime handling, and test patterns.

## Progress
### Done
- [x] Enumerated repository contents and Python/test files to map project structure.
- [x] Read core server entrypoint and registration flow in `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/server.py`.
- [x] Inspected tool modules and conventions:
  - `register_crypto_tools` in `tools/crypto.py`
  - `register_futures_tools` in `tools/futures.py`
  - `register_stocks_tools` in `tools/stocks.py`
  - `register_indices_tools` in `tools/indices.py`
  - `register_news_tools` in `tools/news.py`
  - shared abstractions in `tools/shared.py`
- [x] Inspected core service layer:
  - `fetch_screener_indicators` / `fetch_screener_multi_changes` in `core/services/screener_provider.py`
  - symbol/screener routing in `core/services/symbols.py`
  - metrics/pivots/composite signals in `core/services/indicators.py`
  - ORB logic in `core/services/orb_predictor.py`
  - news provider behavior in `core/services/news_provider.py`
  - symbol loading in `core/services/coinlist.py`
  - exchange/timeframe sanitization in `core/utils/validators.py`
- [x] Inspected tests to identify conventions and expected response schemas:
  - crypto/futures/indices/stocks/news/unit-level tests
  - legacy alias forwarding tests
  - levels schema normalization tests
  - indicator and validator tests
  - optional live integration smoke tests.
- [x] Checked dependencies in `pyproject.toml`:
  - runtime: `mcp[cli]`, `tradingview-screener`, `tradingview-ta`, `finnhub-python`
  - dev: `pytest`.
- [x] Searched for WebSocket/realtime code patterns across source:
  - no WebSocket implementation found (`websocket`, `ws://`, `wss://` absent)
  - only MCP transport modes found: `stdio` and `streamable-http`
  - `"timestamp": "real-time"` in `crypto_analysis` is label text, not streaming infra.

### In Progress
- [ ] Consolidating findings into the requested comprehensive architectural overview (with exact conventions and file-path references for designing a new WebSocket module).

### Blocked
- (none)

## Key Decisions
- **Use direct file inspection instead of assumptions**: Ensures exact conventions (function signatures, error payload shapes, registration patterns) are captured accurately for seamless extension.
- **Treat `tools/shared.py` as canonical pattern for non-crypto modules**: `fetch_and_analyze` and `analyze_single` are reused by stocks/futures/indices and define most shared behavior (sanitization, batching, metric shaping, tolerant failure handling).
- **Flag absence of native WebSocket implementation as an architectural gap**: Necessary to inform design of a new WebSocket-based module without conflicting with current synchronous pull model.
- **Keep analysis read-only**: No modifications were made, so follow-up can proceed from a clean baseline.

## Next Steps
1. Deliver the full requested architectural overview in final form, structured by the 7 user-requested sections.
2. Include a precise project tree summary (source, core services, tools, tests, packaging/entrypoints, coinlist data files).
3. Document `server.py` registration and alias-forwarding conventions, including transport behavior and `exchanges://list` resource pattern.
4. Detail `crypto.py` and `futures.py` signatures/returns/error-handling side-by-side (list returns vs dict error payloads, sanitization/clamping, exception handling style).
5. Explain `screener_provider` vs `tools/shared.py` responsibilities and when each abstraction is used.
6. Summarize test patterns and expected schema contracts to guide new WebSocket module tests.
7. Propose exact integration points for a WebSocket module (new service + new tools + server registration + tests) aligned with existing naming/error/schema conventions.

## Critical Context
- Current architecture is primarily **request/response pull-based** (TradingView TA/screener API calls), not push-streaming.
- `server.py` registers market tool groups via:
  - `register_crypto_tools(mcp)`
  - `register_stocks_tools(mcp)`
  - `register_futures_tools(mcp)`
  - `register_indices_tools(mcp)`
- Legacy aliases in `server.py` forward to crypto-prefixed tools via `_crypto_fn(name)` and `mcp._tool_manager.get_tool(name)`.
- Error handling conventions vary by module:
  - Shared analyzers often return structured `{"error": ...}` dicts (not raised outward).
  - Batch/screener scans frequently skip failed symbols/batches silently and return partial data.
  - Some helpers raise `RuntimeError` internally (especially in crypto helper functions), then tool wrappers convert to error payloads or empty lists.
- `tools/shared.py` provides key reusable conventions:
  - `_safe_get_multiple_analysis(...)` with optional `tv_session_id` cookie handling and backward compatibility for `cookies` arg.
  - symbol normalization to `EXCHANGE:SYMBOL`
  - batch size of 200 for `get_multiple_analysis`
  - optional expanded metrics resolution via `compute_expanded_metrics`.
- `core/services/screener_provider.py` uses `tradingview_screener.Query` directly and supports:
  - exchange scans or explicit ticker scans
  - timeframe suffix mapping (`5m->5`, `15m->15`, etc.)
  - multi-timeframe open/close change computation.
- No existing WebSocket implementation exists in source; MCP runtime transport supports `stdio` and `streamable-http`, not a realtime market-data websocket client/server.
- Tests use lightweight `DummyMCP` registries, monkeypatching, schema assertions, and error passthrough checks; this pattern should be mirrored for new module tests.

## File Operations
### Read
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/services/coinlist.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/services/indicators.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/services/news_provider.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/services/orb_predictor.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/services/screener_provider.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/services/symbols.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/core/utils/validators.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/server.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/tools/crypto.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/tools/futures.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/tools/indices.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/tools/news.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/tools/shared.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/src/tradingview_mcp/tools/stocks.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_crypto_tools.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_futures_tools.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_indicators.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_indices_tools.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_integration.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_legacy_aliases.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_levels_tools.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_news_tools.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_stocks_tools.py`
- `/Volumes/Research/ADO/GitHub/tradingview-mcp/tests/test_validators.py`

### Modified
- (none)
