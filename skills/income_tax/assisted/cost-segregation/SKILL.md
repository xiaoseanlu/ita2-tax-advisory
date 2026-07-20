---
name: cost-segregation
description: >-
  Activates when the user asks about Cost Segregation Study applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Cost Segregation Study"
  ita_id: "ita_027"
  category: "business"
  outline: ita-rules/strategy-outlines/cost-segregation.md
  config: ita-rules/strategy_runtime/configs/cost-segregation.json
  recommended_tools:
    - name: assess_cost_segregation_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_cost_segregation_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Cost Segregation Study

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/cost-segregation.json`](ita-rules/strategy_runtime/configs/cost-segregation.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/cost-segregation.md`](ita-rules/strategy-outlines/cost-segregation.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_cost_segregation_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `accelerated_deduction`.

---

## Part 2 — Savings

Call **`estimate_cost_segregation_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `accelerated_deduction` (advisor)
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
assess_cost_segregation_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_cost_segregation_savings
        │
        ▼
Show savings / cash outlay
```
