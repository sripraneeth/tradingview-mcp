# ES1 → SPX Playbook Prompts

Use these prompts daily to generate projected SPX levels from ES1 futures.

---

## Prompt 1 — Premarket Full Map

```text
Build my ES1→SPX premarket map for today.

Inputs:
- ES symbol: ES1!
- SPX symbol: SP:SPX
- Timeframes: ES 5m + 30m, SPX 1D

Required calculations:
1) ES prior day high/low/close
2) ES opening ranges: 5m, 15m, 30m
3) ES current session VWAP
4) ES Camarilla levels (R4..S4)
5) ES Classic pivots (R3..S3 + Pivot)
6) ES→SPX offset using: offset = SPX_last_close - ES_prior_close
7) Project ES levels to SPX with: SPX_level = ES_level + offset

Output format:
- Section A: ES key levels table
- Section B: Projected SPX key levels table
- Section C: 3 scenarios (bull/bear/range) with trigger, targets, invalidation
- Section D: Key U.S. event windows in ET for today
```

---

## Prompt 2 — Post-Open Update (15–30 min after open)

```text
Update my live ES1→SPX playbook now.

Use latest data and return:
- ES position vs VWAP (above/below/at)
- Opening range status (holding, breakout, failed breakout)
- Active regime: bull / bear / range
- Next 2 ES targets + equivalent SPX targets
- Invalidation level (ES and SPX)

Constraints:
- Keep output to max 8 bullets
- No long explanation, only actionable levels
```

---

## Prompt 3 — 8:30 ET Data Reaction

```text
Recompute ES1→SPX map immediately after 8:30 ET data release.

Need:
1) New session high/low and range expansion vs pre-release range
2) Updated VWAP location
3) Acceptance vs rejection decision:
   - Acceptance = price holds beyond breakout level for at least 2 consecutive 5m bars
   - Rejection = price snaps back inside opening range
4) Continuation targets and fail level

Output:
- Decision: ACCEPTANCE or REJECTION
- Trade map: Long setup + Short setup with exact ES/SPX levels
```

---

## Prompt 4 — Midday Re-Anchor

```text
It is midday. Re-anchor ES1→SPX levels using current session structure.

Compute and return:
- Current session high/low midpoint
- VWAP distance in points from current price
- Nearest 3 resistance and 3 support levels (ES + projected SPX)
- Probability bias (bull/bear/neutral) based on:
  - price vs VWAP
  - higher highs/higher lows or lower highs/lower lows on 30m

Return as:
- Bias line
- Compact levels table
- One sentence execution plan
```

---

## Prompt 5 — End-of-Day Prep for Next Session

```text
Create tomorrow’s ES1→SPX projected levels from today’s completed session.

Must include:
1) Final session high/low/close (ES)
2) Next-day Camarilla levels (ES and projected SPX)
3) Next-day Classic pivots (ES and projected SPX)
4) Tomorrow’s expected opening zones (5m/15m/30m reference)
5) Top 3 upside and top 3 downside levels to watch first

Format:
- Clean table + short checklist for tomorrow morning
```

---

## Prompt 6 — Single-Command Master Prompt

```text
You are my ES1→SPX trading assistant.

Task:
Build a complete intraday playbook using ES1 futures and project levels to SPX.

Data requirements:
- Pull ES1 bars at 5m and 30m
- Pull SPX daily close
- Use latest session data only

Calculations:
- ES prior day H/L/C
- ES opening ranges: 5m, 15m, 30m
- ES VWAP
- ES Camarilla R4..S4
- ES Classic pivots R3..S3 + Pivot
- Offset = SPX_last_close - ES_prior_close
- Project all ES levels to SPX using the offset

Decision model:
- Bull if price is above VWAP and above OR high
- Bear if price is below VWAP and below OR low
- Else range

Output exactly in this structure:
1) ES levels table
2) Projected SPX levels table
3) Active regime (bull/bear/range)
4) Bull plan: trigger, targets (2), invalidation
5) Bear plan: trigger, targets (2), invalidation
6) Event risk times in ET for today
7) One-line summary bias
```

---

## Quick Usage Notes

- Best run times:
  - 30–60 min before U.S. cash open
  - 15–30 min after open
  - Right after major data releases (8:30 ET / 10:00 ET)
- If ES and SPX diverge unusually, recalculate offset using latest reliable SPX cash reference.
- On high-volatility days, prioritize Camarilla R3/S3 and OR break/hold behavior.
