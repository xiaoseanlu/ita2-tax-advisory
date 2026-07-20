---
name: student-loan-employer
description: >-
  Activates when the user asks about Student loan payments made by employer applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Student loan payments made by employer"
  ita_id: "ita_011"
  category: "deduction"
  outline: ita-rules/strategy-outlines/student-loan-employer.md
  config: ita-rules/strategy_runtime/configs/student-loan-employer.json
  recommended_tools:
    - name: assess_student_loan_employer_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_student_loan_employer_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Student loan payments made by employer

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/student-loan-employer.json`](ita-rules/strategy_runtime/configs/student-loan-employer.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/student-loan-employer.md`](ita-rules/strategy-outlines/student-loan-employer.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_student_loan_employer_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `loan_payment_limit`.

---

## Part 2 — Savings

Call **`estimate_student_loan_employer_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `loan_payment_limit` (engine)
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
assess_student_loan_employer_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_student_loan_employer_savings
        │
        ▼
Show savings / cash outlay
```
