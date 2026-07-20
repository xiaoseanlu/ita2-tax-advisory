# Donating Appreciated Stock — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/donate-appreciated-stock.json`](../../../../ita-rules/strategy_runtime/configs/donate-appreciated-stock.json)
Outline: [`ita-rules/strategy-outlines/donate-appreciated-stock.md`](../../../../ita-rules/strategy-outlines/donate-appreciated-stock.md)

## Tools

1. `assess_donate_appreciated_stock_applicability`
2. `estimate_donate_appreciated_stock_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `donation_fmv` | Donation FMV ($) | advisor | 0 |
| `unrealized_gain` | Unrealized gain avoided ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Donating Appreciated Stock to Charity/` before relying on savings-core output.
