# Section 179 — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/section-179.json`](../../../../ita-rules/strategy_runtime/configs/section-179.json)
Outline: [`ita-rules/strategy-outlines/section-179.md`](../../../../ita-rules/strategy-outlines/section-179.md)

## Tools

1. `assess_section_179_applicability`
2. `estimate_section_179_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `section_179_expense`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `section_179_expense` | Section 179 expense ($) | advisor | 0 |
| `qualifying_property_cost` | Qualifying property cost ($) | user | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Section 179/` before relying on savings-core output.
