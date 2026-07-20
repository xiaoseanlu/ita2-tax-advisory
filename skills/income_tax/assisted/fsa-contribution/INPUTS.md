# Flex Spending Account — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/fsa-contribution.json`](../../../../ita-rules/strategy_runtime/configs/fsa-contribution.json)
Outline: [`ita-rules/strategy-outlines/fsa-contribution.md`](../../../../ita-rules/strategy-outlines/fsa-contribution.md)

## Tools

1. `assess_fsa_contribution_applicability`
2. `estimate_fsa_contribution_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `max(0, employee_max_fsa_contribution - baseline_amount)`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `employee_max_fsa_contribution` | Employee max FSA ($) | engine | 3200 |
| `baseline_amount` | Current FSA contribution ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `FSA Contribution/` before relying on savings-core output.
