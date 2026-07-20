---
name: hire-your-kids
description: >-
  Activates when the user asks about Hire Your Kids applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Hire Your Kids"
  ita_id: "ita_020"
  category: "business"
  outline: ita-rules/strategy-outlines/hire-your-kids.md
  config: ita-rules/strategy_runtime/configs/hire-your-kids.json
  recommended_tools:
    - name: assess_hire_your_kids_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_hire_your_kids_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Hire Your Kids

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/hire-your-kids.json`](ita-rules/strategy_runtime/configs/hire-your-kids.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/hire-your-kids.md`](ita-rules/strategy-outlines/hire-your-kids.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_hire_your_kids_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `max_hiring_allowed`.

---

## Part 2 — Savings

Call **`estimate_hire_your_kids_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `max_hiring_allowed` (engine)
- `kid_wages_paid` (user)
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
assess_hire_your_kids_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_hire_your_kids_savings
        │
        ▼
Show savings / cash outlay
```
