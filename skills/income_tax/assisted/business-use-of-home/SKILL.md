---
name: business-use-of-home
description: >-
  Activates when the user asks about Business Use of Home applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "business use of home"
  ita_id: "ita_009"
  category: "deduction"
  outline: ita-rules/strategy-outlines/business-use-of-home.md
  config: ita-rules/strategy_runtime/configs/business-use-of-home.json
  recommended_tools:
    - name: assess_business_use_of_home_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_business_use_of_home_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Business Use of Home

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/business-use-of-home.json`](ita-rules/strategy_runtime/configs/business-use-of-home.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/business-use-of-home.md`](ita-rules/strategy-outlines/business-use-of-home.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_business_use_of_home_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `home_office_deduction`.

---

## Part 2 — Savings

Call **`estimate_business_use_of_home_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `home_office_deduction` (advisor)
- `business_use_pct` (user)
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
assess_business_use_of_home_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_business_use_of_home_savings
        │
        ▼
Show savings / cash outlay
```
