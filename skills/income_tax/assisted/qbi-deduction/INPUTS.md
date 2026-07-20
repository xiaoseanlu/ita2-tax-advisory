# QBI Deduction — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/qbi-deduction.json`](../../../../ita-rules/strategy_runtime/configs/qbi-deduction.json)
Outline: [`ita-rules/strategy-outlines/qbi-deduction.md`](../../../../ita-rules/strategy-outlines/qbi-deduction.md)

## Tools

1. `assess_qbi_deduction_applicability`
2. `estimate_qbi_deduction_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `qbi_deduction_amount`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `qbi_deduction_amount` | QBI deduction amount ($) | engine | 0 |
| `qualified_business_income` | Qualified business income ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `QBI/` before relying on savings-core output.
