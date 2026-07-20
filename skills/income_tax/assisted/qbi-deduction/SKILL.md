---
name: qbi-deduction
description: >-
  Activates when the user asks about QBI Deduction applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "QBI"
  ita_id: "ita_028"
  category: "business"
  outline: ita-rules/strategy-outlines/qbi-deduction.md
  config: ita-rules/strategy_runtime/configs/qbi-deduction.json
  recommended_tools:
    - name: assess_qbi_deduction_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_qbi_deduction_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# QBI Deduction

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/qbi-deduction.json`](ita-rules/strategy_runtime/configs/qbi-deduction.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/qbi-deduction.md`](ita-rules/strategy-outlines/qbi-deduction.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_qbi_deduction_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `qbi_deduction_amount`.

---

## Part 2 — Savings

Call **`estimate_qbi_deduction_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `qbi_deduction_amount` (engine)
- `qualified_business_income` (user)
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
assess_qbi_deduction_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_qbi_deduction_savings
        │
        ▼
Show savings / cash outlay
```
