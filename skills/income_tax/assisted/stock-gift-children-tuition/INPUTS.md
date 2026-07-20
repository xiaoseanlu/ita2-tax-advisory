# Stock Gift For Childrens Tution — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/stock-gift-children-tuition.json`](../../../../ita-rules/strategy_runtime/configs/stock-gift-children-tuition.json)
Outline: [`ita-rules/strategy-outlines/stock-gift-children-tuition.md`](../../../../ita-rules/strategy-outlines/stock-gift-children-tuition.md)

## Tools

1. `assess_stock_gift_children_tuition_applicability`
2. `estimate_stock_gift_children_tuition_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `gift_fmv` | Stock gift FMV ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Stock gift for childrens tuition/` before relying on savings-core output.
