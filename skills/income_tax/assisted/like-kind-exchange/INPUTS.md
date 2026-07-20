# Like-kind exchange — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/like-kind-exchange.json`](../../../../ita-rules/strategy_runtime/configs/like-kind-exchange.json)
Outline: [`ita-rules/strategy-outlines/like-kind-exchange.md`](../../../../ita-rules/strategy-outlines/like-kind-exchange.md)

## Tools

1. `assess_like_kind_exchange_applicability`
2. `estimate_like_kind_exchange_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `deferred_gain` | Deferred gain ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Like Kind Exchange/` before relying on savings-core output.
