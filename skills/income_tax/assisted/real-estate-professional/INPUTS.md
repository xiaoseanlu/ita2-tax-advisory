# Real Estate Professional — inputs by Skill part

**Status:** implemented (savings-core).

Config: [`ita-rules/strategy_runtime/configs/real-estate-professional.json`](../../../../ita-rules/strategy_runtime/configs/real-estate-professional.json)
Outline: [`ita-rules/strategy-outlines/real-estate-professional.md`](../../../../ita-rules/strategy-outlines/real-estate-professional.md)

## Tools

1. `assess_real_estate_professional_applicability`
2. `estimate_real_estate_professional_savings`

## Form fields (from runtime config)

**require_advisor_strategy_change:** true

| Field | Label | Source | Default |
|-------|-------|--------|--------|
| `passive_loss_unlocked` | Passive loss unlocked ($) | advisor | 0 |
| `strategy_change` | Strategy change ($) | advisor |  |
| `federal_marginal_rate_pct` | Federal marginal rate (%) | engine | 24 |
| `state_marginal_rate_pct` | State marginal rate (%) | engine | 0 |
| `nyc_marginal_rate_pct` | NYC marginal rate (%) | engine | 0 |


## Savings formula

- Mode: `marginal_x_change`
- Cash outlay mode: `contribution`
- `projected_tax_savings = round(strategy_change × marginal_rate / 100)` (credit mode: savings = strategy_change)

Full SPE gates are not ported — verify applicability in `realEstateProfessional/` before relying on savings-core output.
