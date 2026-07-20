---
name: startup-expense
description: >-
  Activates when the user asks about Startup Expense applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Startup Expense"
  ita_id: "ita_031"
  category: "business"
  outline: ita-rules/strategy-outlines/startup-expense.md
  config: ita-rules/strategy_runtime/configs/startup-expense.json
  recommended_tools:
    - name: assess_startup_expense_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_startup_expense_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Startup Expense

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/startup-expense.json`](ita-rules/strategy_runtime/configs/startup-expense.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/startup-expense.md`](ita-rules/strategy-outlines/startup-expense.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_startup_expense_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `startup_expense`.

---

## Part 2 — Savings

Call **`estimate_startup_expense_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `startup_expense` (advisor)
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
assess_startup_expense_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_startup_expense_savings
        │
        ▼
Show savings / cash outlay
```
