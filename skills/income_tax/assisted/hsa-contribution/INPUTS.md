# HSA Contribution — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/hsa-contribution.json`](../../../../ita-rules/strategy_runtime/configs/hsa-contribution.json)
Outline: [`ita-rules/strategy-outlines/hsa-contribution.md`](../../../../ita-rules/strategy-outlines/hsa-contribution.md)

## Tools

1. `assess_hsa_contribution_applicability`
2. `estimate_hsa_contribution_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `max(0, max_hsa_contribution - hsa_contribution_made)`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `max_hsa_contribution` | Max HSA contribution ($) | engine | 4150 |
| `hsa_contribution_made` | HSA already contributed ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `HSA Contribution/` before relying on savings-core output.
