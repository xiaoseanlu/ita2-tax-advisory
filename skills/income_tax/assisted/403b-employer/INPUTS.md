# 403(b) Employer Contribution — inputs

Source SPE: `403b Employer Contribution/employer-403b-contribution.spe`

| Field | Meaning |
|-------|---------|
| `w2.wages_403b_contribution` | Must be > 0 to recommend |
| `retirement.*` | Shared employee headroom (same as 403b EE) |
| `rates.resident_state` | `NJ` zeros state/NYC in savings |

### SPE anchor

`strategy_change=2250`, total rate 20% → savings **450**, cash **0**.
