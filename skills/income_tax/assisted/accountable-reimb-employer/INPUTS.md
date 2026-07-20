# Accountable Reimbursement Plan as Employer — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/accountable-reimb-employer.json`](../../../../ita-rules/strategy_runtime/configs/accountable-reimb-employer.json)
Outline: [`ita-rules/strategy-outlines/accountable-reimb-employer.md`](../../../../ita-rules/strategy-outlines/accountable-reimb-employer.md)

## Tools

1. `assess_accountable_reimb_employer_applicability`
2. `estimate_accountable_reimb_employer_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `reimbursement_amount`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `reimbursement_amount` | Reimbursement amount ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Accountable Reimbursement Plan as Employer/` before relying on savings-core output.
