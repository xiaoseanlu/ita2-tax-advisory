# Pass-through-Entity-Tax — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/ptet.json`](../../../../ita-rules/strategy_runtime/configs/ptet.json)
Outline: [`ita-rules/strategy-outlines/ptet.md`](../../../../ita-rules/strategy-outlines/ptet.md)

## Tools

1. `assess_ptet_applicability`
2. `estimate_ptet_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `ptet_deduction`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `ptet_deduction` | PTET deduction ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `PTET/` before relying on savings-core output.
