# ES1 → SPX Quick Prompts

Use these two prompts for fast daily execution.

---

## 1) Daily Full Map (Premarket)

```text
Build my ES1→SPX daily map now.

Inputs:
- ES symbol: ES1!
- SPX symbol: SP:SPX
- Timeframes: ES 5m + 30m, SPX 1D

Compute:
1) ES prior day high/low/close
2) ES opening ranges: 5m, 15m, 30m
3) ES VWAP (current session)
4) ES Camarilla (R4..S4)
5) ES Classic pivots (R3..S3 + Pivot)
6) Offset = SPX_last_close - ES_prior_close
7) Project all ES levels to SPX (SPX_level = ES_level + offset)

Output:
- ES levels table
- Projected SPX levels table
- Bull plan (trigger, 2 targets, invalidation)
- Bear plan (trigger, 2 targets, invalidation)
- Range plan (boundaries + fail condition)
```

---

## 2) Quick Live Update

```text
Quick ES1→SPX update now.

Return only:
- Active regime: bull / bear / range
- ES vs VWAP: above / below / at
- Opening range status: holding / break / failed break
- Next 2 ES targets + projected SPX targets
- Invalidation level (ES and SPX)

Constraints:
- Max 8 bullets
- Actionable levels only
```
