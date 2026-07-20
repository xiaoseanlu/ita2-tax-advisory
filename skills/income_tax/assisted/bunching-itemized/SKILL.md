---
name: bunching-itemized
description: >-
  Activates when the user asks about Bunching Itemized Deductions applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Bunching Itemized Deductions"
  ita_id: "ita_008"
  category: "deduction"
  outline: ita-rules/strategy-outlines/bunching-itemized.md
  config: ita-rules/strategy_runtime/configs/bunching-itemized.json
  recommended_tools:
    - name: assess_bunching_itemized_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_bunching_itemized_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Bunching Itemized Deductions

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/bunching-itemized.json`](ita-rules/strategy_runtime/configs/bunching-itemized.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/bunching-itemized.md`](ita-rules/strategy-outlines/bunching-itemized.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_bunching_itemized_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_bunching_itemized_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `itemized_bunch_amount` (advisor)
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
assess_bunching_itemized_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_bunching_itemized_savings
        │
        ▼
Show savings / cash outlay
```
