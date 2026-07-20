# 401(k) Employer Contribution — inputs

Source SPE: `401k Employer Contribution/employer-401k-contribution.spe`

## Part 1 — `assess_401k_employer_applicability`

| Field | Meaning |
|-------|---------|
| `w2.wg_fed_wages` | Box 1 wages |
| `w2.wages_401k_contribution` | Current EE deferral (applicability cap) |
| `w2.wages_403b_contribution` / `w2.wg_457b` | Must be 0 to recommend |
| `retirement.max_401k_contribution_allowed` | Engine GlotaxPayerMaxAllowedContribution |
| `retirement.combined_401k_limit` | Combined §415 cap |
| `retirement.combined_limit_absorbed` | Combined absorption counter |

## Part 2 — `estimate_401k_employer_savings`

Add `rates.*` and optional `strategy_change`.

### SPE anchor

`strategy_change=7500`, `MARGINAL_RATE_TOTAL=33` → savings **2475**, cash **0**.
