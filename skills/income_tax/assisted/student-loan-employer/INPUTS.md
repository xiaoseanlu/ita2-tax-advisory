# Student loan payments made by employer — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/student-loan-employer.json`](../../../../ita-rules/strategy_runtime/configs/student-loan-employer.json)
Outline: [`ita-rules/strategy-outlines/student-loan-employer.md`](../../../../ita-rules/strategy-outlines/student-loan-employer.md)

## Tools

1. `assess_student_loan_employer_applicability`
2. `estimate_student_loan_employer_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `loan_payment_limit`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `loan_payment_limit` | Employer loan payment limit ($) | engine | 5250 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Student loan payments made by employer/` before relying on savings-core output.
