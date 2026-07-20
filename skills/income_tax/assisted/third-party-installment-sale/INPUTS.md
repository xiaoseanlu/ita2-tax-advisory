# Third party installment sale — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/third-party-installment-sale.json`](../../../../ita-rules/strategy_runtime/configs/third-party-installment-sale.json)
Outline: [`ita-rules/strategy-outlines/third-party-installment-sale.md`](../../../../ita-rules/strategy-outlines/third-party-installment-sale.md)

## Tools

1. `assess_third_party_installment_sale_applicability`
2. `estimate_third_party_installment_sale_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `installment_deferral` | Tax deferred via installment ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Third Party Installment Sale/` before relying on savings-core output.
