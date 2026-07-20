# Hire Your Kids — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/hire-your-kids.json`](../../../../ita-rules/strategy_runtime/configs/hire-your-kids.json)
Outline: [`ita-rules/strategy-outlines/hire-your-kids.md`](../../../../ita-rules/strategy-outlines/hire-your-kids.md)

## Tools

1. `assess_hire_your_kids_applicability`
2. `estimate_hire_your_kids_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `max_hiring_allowed`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `max_hiring_allowed` | Max hiring allowed ($) | engine | 0 |
| `kid_wages_paid` | Kid wages already paid ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Hire Your Kids/` before relying on savings-core output.
