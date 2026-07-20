# Bonus depreciation — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/bonus-depreciation.json`](../../../../ita-rules/strategy_runtime/configs/bonus-depreciation.json)
Outline: [`ita-rules/strategy-outlines/bonus-depreciation.md`](../../../../ita-rules/strategy-outlines/bonus-depreciation.md)

## Tools

1. `assess_bonus_depreciation_applicability`
2. `estimate_bonus_depreciation_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `depreciation_expense`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `depreciation_expense` | Bonus depreciation expense ($) | advisor | 0 |
| `asset_basis` | Asset basis ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Bonus Depreciation/` before relying on savings-core output.
