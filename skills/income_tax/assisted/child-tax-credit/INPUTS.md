# Child Tax Credit — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/child-tax-credit.json`](../../../../ita-rules/strategy_runtime/configs/child-tax-credit.json)
Outline: [`ita-rules/strategy-outlines/child-tax-credit.md`](../../../../ita-rules/strategy-outlines/child-tax-credit.md)

## Tools

1. `assess_child_tax_credit_applicability`
2. `estimate_child_tax_credit_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `lost_credit`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `lost_credit` | Lost / recoverable credit ($) | advisor | 0 |
| `qualifying_children` | Qualifying children | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `credit`
- Cash outlay mode: `none`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Child Tax Credit/` before relying on savings-core output.
