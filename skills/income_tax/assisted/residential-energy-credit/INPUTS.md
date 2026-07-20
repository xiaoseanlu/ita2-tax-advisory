# Residential Energy Credit — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/residential-energy-credit.json`](../../../../ita-rules/strategy_runtime/configs/residential-energy-credit.json)
Outline: [`ita-rules/strategy-outlines/residential-energy-credit.md`](../../../../ita-rules/strategy-outlines/residential-energy-credit.md)

## Tools

1. `assess_residential_energy_credit_applicability`
2. `estimate_residential_energy_credit_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `energy_credit_amount`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `energy_expenditure` | Energy expenditure ($) | user | 0 |
| `energy_credit_amount` | Energy credit amount ($) | engine | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `credit`
- Cash outlay mode: `none`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Residential Energy Credit/` before relying on savings-core output.
