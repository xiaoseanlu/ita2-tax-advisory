# Hire your Spouse — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/hire-your-spouse.json`](../../../../ita-rules/strategy_runtime/configs/hire-your-spouse.json)
Outline: [`ita-rules/strategy-outlines/hire-your-spouse.md`](../../../../ita-rules/strategy-outlines/hire-your-spouse.md)

## Tools

1. `assess_hire_your_spouse_applicability`
2. `estimate_hire_your_spouse_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `spouse_wages`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `spouse_wages` | Spouse wages ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Hire Your Spouse/` before relying on savings-core output.
