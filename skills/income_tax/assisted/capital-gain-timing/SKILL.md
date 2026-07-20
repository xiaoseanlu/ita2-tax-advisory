---
name: capital-gain-timing
description: >-
  Activates when the user asks about Capital gain timing applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Capital Gain Timing"
  ita_id: "ita_019"
  category: "capital"
  outline: ita-rules/strategy-outlines/capital-gain-timing.md
  config: ita-rules/strategy_runtime/configs/capital-gain-timing.json
  recommended_tools:
    - name: assess_capital_gain_timing_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_capital_gain_timing_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Capital gain timing

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/capital-gain-timing.json`](ita-rules/strategy_runtime/configs/capital-gain-timing.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/capital-gain-timing.md`](ita-rules/strategy-outlines/capital-gain-timing.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_capital_gain_timing_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_capital_gain_timing_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `deferred_gain` (advisor)
- `strategy_change` (advisor)
- `federal_marginal_rate_pct` (engine)
- `state_marginal_rate_pct` (engine)
- `nyc_marginal_rate_pct` (engine)

---

## Protocol

```
Payload (engine + user + advisor fields)
        │
        ▼
assess_capital_gain_timing_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_capital_gain_timing_savings
        │
        ▼
Show savings / cash outlay
```
