# Mega Backdoor Roth — inputs

| Field | Meaning |
|-------|---------|
| `w2.wages_401k_contribution` / `wages_403b_contribution` / `wg_457b` | Max-out check vs prior year |
| `retirement.max_solo_401k_allowed` | Total §415-style cap (engine) |
| `retirement.current_year_max_401k_allowed` | Current EE deferral limit |
| `retirement.prior_year_max_401k` | Prior-year EE limit for max-out gate |
| `retirement.modified_agi` / `retirement.roth_phase_out` | Phase-out recommend gate |

Savings always **0**; cash equals strategy change.
