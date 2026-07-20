# IRA QCD — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/ira-qcd.json`](../../../../ita-rules/strategy_runtime/configs/ira-qcd.json)
Outline: [`ita-rules/strategy-outlines/ira-qcd.md`](../../../../ita-rules/strategy-outlines/ira-qcd.md)

## Tools

1. `assess_ira_qcd_applicability`
2. `estimate_ira_qcd_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `qcd_amount`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `qcd_amount` | QCD amount ($) | advisor | 0 |
| `ira_balance` | IRA balance ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `IRA QCD/` before relying on savings-core output.
