# Dependent Care Reimbursement — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/dependent-care-reimbursement.json`](../../../../ita-rules/strategy_runtime/configs/dependent-care-reimbursement.json)
Outline: [`ita-rules/strategy-outlines/dependent-care-reimbursement.md`](../../../../ita-rules/strategy-outlines/dependent-care-reimbursement.md)

## Tools

1. `assess_dependent_care_reimbursement_applicability`
2. `estimate_dependent_care_reimbursement_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `max(0, max_dcb_contribution - baseline_amount)`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `max_dcb_contribution` | Max dependent care benefit ($) | engine | 5000 |
| `baseline_amount` | Current DCFSA contribution ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Dependent Care Reimbursement/` before relying on savings-core output.
