---
name: combined-business-travel
description: >-
  Activates when the user asks about Combine business and personal travel applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Combined Business and Personal Travel"
  ita_id: "ita_010"
  category: "deduction"
  outline: ita-rules/strategy-outlines/combined-business-travel.md
  config: ita-rules/strategy_runtime/configs/combined-business-travel.json
  recommended_tools:
    - name: assess_combined_business_travel_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_combined_business_travel_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Combine business and personal travel

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/combined-business-travel.json`](ita-rules/strategy_runtime/configs/combined-business-travel.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/combined-business-travel.md`](ita-rules/strategy-outlines/combined-business-travel.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_combined_business_travel_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_combined_business_travel_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `deductible_travel` (advisor)
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
assess_combined_business_travel_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_combined_business_travel_savings
        │
        ▼
Show savings / cash outlay
```
