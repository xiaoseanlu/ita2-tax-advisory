# Bunching Itemized Deductions — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/bunching-itemized.json`](../../../../ita-rules/strategy_runtime/configs/bunching-itemized.json)
Outline: [`ita-rules/strategy-outlines/bunching-itemized.md`](../../../../ita-rules/strategy-outlines/bunching-itemized.md)

## Tools

1. `assess_bunching_itemized_applicability`
2. `estimate_bunching_itemized_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `itemized_bunch_amount` | Bunched itemized amount ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Bunching Itemized Deductions/` before relying on savings-core output.
