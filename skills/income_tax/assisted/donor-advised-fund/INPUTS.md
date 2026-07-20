# Donor Advised Fund To Time Contributions — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/donor-advised-fund.json`](../../../../ita-rules/strategy_runtime/configs/donor-advised-fund.json)
Outline: [`ita-rules/strategy-outlines/donor-advised-fund.md`](../../../../ita-rules/strategy-outlines/donor-advised-fund.md)

## Tools

1. `assess_donor_advised_fund_applicability`
2. `estimate_donor_advised_fund_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `daf_contribution` | DAF contribution ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Donor Advised Fund To Time Contributions/` before relying on savings-core output.
