# Augusta Rule - tax-free rental income — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/augusta-rule-rental.json`](../../../../ita-rules/strategy_runtime/configs/augusta-rule-rental.json)
Outline: [`ita-rules/strategy-outlines/augusta-rule-rental.md`](../../../../ita-rules/strategy-outlines/augusta-rule-rental.md)

## Tools

1. `assess_augusta_rule_rental_applicability`
2. `estimate_augusta_rule_rental_savings`

## Form fields (from runtime config)

**strategy_change_expr:** `tax_free_rental_income`

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `tax_free_rental_income` | Tax-free rental income ($) | advisor | 0 |
| `days_rented` | Days rented | user | 14 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `Augusta Rule-Rental Income (Tax Free)/` before relying on savings-core output.
