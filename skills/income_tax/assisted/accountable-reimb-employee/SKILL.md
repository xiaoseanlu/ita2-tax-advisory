---
name: accountable-reimb-employee
description: >-
  Activates when the user asks about Accountable Reimbursement Plan as Employee applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Accountable Reimbursement Plan as Employee"
  ita_id: "ita_006"
  category: "business"
  outline: ita-rules/strategy-outlines/accountable-reimb-employee.md
  config: ita-rules/strategy_runtime/configs/accountable-reimb-employee.json
  recommended_tools:
    - name: assess_accountable_reimb_employee_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_accountable_reimb_employee_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Accountable Reimbursement Plan as Employee

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/accountable-reimb-employee.json`](ita-rules/strategy_runtime/configs/accountable-reimb-employee.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/accountable-reimb-employee.md`](ita-rules/strategy-outlines/accountable-reimb-employee.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_accountable_reimb_employee_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `reimbursement_amount`.

---

## Part 2 — Savings

Call **`estimate_accountable_reimb_employee_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `reimbursement_amount` (advisor)
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
assess_accountable_reimb_employee_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_accountable_reimb_employee_savings
        │
        ▼
Show savings / cash outlay
```
