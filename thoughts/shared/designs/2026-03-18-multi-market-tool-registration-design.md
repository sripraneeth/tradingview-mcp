---
date: 2026-03-18
topic: "Multi-market tool registration and market-domain refactor"
status: draft
---

## Problem Statement

We need to evolve the MCP server from a crypto-first setup into a clean **multi-market** design without breaking existing clients.

The current server works, but several code paths still hardcode `crypto` market selection, and tool naming is unscoped. This makes expansion to stock markets fragile and harder to reason about.

## Constraints

- Preserve backward compatibility for existing tool callers.
- Keep one deployable MCP entrypoint for now to avoid operational complexity.
- Avoid large rewrites; target the smallest structural changes that unlock multi-market behavior.
- Respect current exchange normalization and timeframe sanitation behavior.

## Approach

I am choosing a **single FastMCP instance with explicit, prefixed tool names plus compatibility aliases**.

This gives us immediate namespace clarity while minimizing migration risk. In parallel, we centralize market-domain resolution so every data path uses exchange-to-market mapping instead of hardcoded crypto defaults.

I considered splitting into multiple MCP servers per domain, but rejected it for now because it introduces orchestration overhead and breaks the current simple startup model.

I also considered keeping current unprefixed names only, but rejected it because it scales poorly as we add stock- and market-specific scanners.

## Architecture

The architecture remains a **single process / single MCP server** with a clearer internal layering model:

- **Tool Layer:** Public MCP tools exposed with explicit naming policy.
- **Domain Resolution Layer:** Normalizes exchange and maps it to TradingView screener market.
- **Data Access Layer:** Thin wrappers around `tradingview-ta` and `tradingview-screener` query execution.
- **Metric/Transformation Layer:** Converts raw indicator payloads into stable response shapes.

This keeps transport and runtime unchanged while making market behavior deterministic.

## Components

### Tool Registration Component

Owns tool naming strategy and compatibility policy.

- Registers canonical prefixed names (e.g., `crypto_*`, `market_*`).
- Keeps legacy names as wrappers during migration period.
- Ensures future tools follow one naming contract.

### Market Resolver Component

Owns exchange → screener market mapping and fallback behavior.

- Uses normalized exchange keys.
- Produces a market domain token compatible with both TA and screener query flows.
- Eliminates direct `.set_markets("crypto")` hardcoding.

### Query Builder Component

Owns query construction for screener-backed scanners.

- Accepts market domain from resolver.
- Applies symbol mode or exchange scan mode consistently.
- Centralizes timeframe suffixing and selected columns.

### Response Normalizer Component

Owns output shape consistency across tools.

- Keeps stable field names for existing clients.
- Adds optional metadata for market domain only where needed.
- Avoids leaking provider-specific quirks to tool consumers.

## Data Flow

Request lifecycle for scanner and analysis tools:

1. Client invokes MCP tool.
2. Input sanitizer normalizes `exchange`, `timeframe`, and limits.
3. Market resolver determines screener market domain.
4. Data access/query builder executes TA or screener query with resolved domain.
5. Metric transformers compute indicators/ratings.
6. Response normalizer returns stable payload.

For legacy tools, the same flow applies; only registration alias differs.

## Error Handling

Error strategy is **layered and non-destructive**:

- **Validation errors:** return deterministic user-facing errors for invalid timeframe/exchange.
- **Provider failures:** isolate batch/query failures and continue where safe.
- **Empty data:** return empty arrays or structured “no data” responses, not crashes.
- **Mapping misses:** fallback to safe default market domain while emitting internal warning context.

This keeps behavior resilient under TradingView variability and rate limits.

## Testing Strategy

We validate behavior at three levels.

### Contract Tests

- Verify canonical tool names are exposed.
- Verify backward-compatible aliases remain available during migration.

### Domain Resolution Tests

- Verify exchange normalization maps to intended market domain.
- Verify non-crypto exchanges route through non-crypto market values.

### Query Path Tests

- Verify screener query builders use resolved market domain instead of hardcoded crypto.
- Verify TA call paths use correct `screener` and symbol format contract.

## Open Questions

- Alias sunset policy: how long we keep legacy unprefixed tool names.
- Whether to expose market domain in every response or only in debug metadata.
- Whether some tools should remain crypto-only by design for signal quality reasons.
