# Tax loss harvesting (short-term) — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/tax-loss-harvesting-st.json`](../../../../ita-rules/strategy_runtime/configs/tax-loss-harvesting-st.json)
Outline: [`ita-rules/strategy-outlines/tax-loss-harvesting-st.md`](../../../../ita-rules/strategy-outlines/tax-loss-harvesting-st.md)

## Tools

1. `assess_tax_loss_harvesting_st_applicability`
2. `estimate_tax_loss_harvesting_st_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `short_term_loss` | Short-term loss harvested ($) | advisor | 0 |
| `short_term_gain` | Short-term gain offset ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Tax Loss Harvesting - ST/` before relying on savings-core output.
