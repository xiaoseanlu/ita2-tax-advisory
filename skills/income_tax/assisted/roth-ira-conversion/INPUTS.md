# Roth IRA Conversion — inputs

| Field | Meaning |
|-------|---------|
| `person.ira_contribution` / `total_401k_contribution` / `total_403b_contribution` / `total_457b_contribution` | Recommend if any > 0 |
| `estimate_mode` | `tax_cost` or `growth` |
| `strategy_change` | Conversion amount (tax_cost) |
| `growth.amount` / `growth_rate_pct` / `years` / `retirement_rate_pct` | Growth calculator inputs |
| `rates.nj_pension_exclusion_factor` | NJ partial conformity (decimal, e.g. 0.47917) |

### tax_cost example

change 2000 @ 37% → savings **-740**, cash **-740**.
