# Business Use of Home — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/business-use-of-home.json`](../../../../ita-rules/strategy_runtime/configs/business-use-of-home.json)
Outline: [`ita-rules/strategy-outlines/business-use-of-home.md`](../../../../ita-rules/strategy-outlines/business-use-of-home.md)

## Tools

1. `assess_business_use_of_home_applicability`
2. `estimate_business_use_of_home_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `home_office_deduction`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `home_office_deduction` | Home office deduction ($) | advisor | 0 |
| `business_use_pct` | Business use (%) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `business use of home/` before relying on savings-core output.
