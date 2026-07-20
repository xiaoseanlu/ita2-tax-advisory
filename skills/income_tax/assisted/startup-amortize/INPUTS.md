# Startup Amortize — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/startup-amortize.json`](../../../../ita-rules/strategy_runtime/configs/startup-amortize.json)
Outline: [`ita-rules/strategy-outlines/startup-amortize.md`](../../../../ita-rules/strategy-outlines/startup-amortize.md)

## Tools

1. `assess_startup_amortize_applicability`
2. `estimate_startup_amortize_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `startup_amortize_amount`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `startup_amortize_amount` | Startup amortize amount ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Startup Amortize/` before relying on savings-core output.
