# 403(b) Employee Contribution — inputs

Source SPE: `403b Employee Contribution/employee-403b-contribution.spe`

Same retirement baseline fields as 401(k) EE (`max_401k_contribution_allowed`, baselines, absorption).

| Field | Meaning |
|-------|---------|
| `w2.wages_403b_contribution` | Current 403(b) deferral (recommend gate > 0) |
| `rates.resident_state` | `PA` or `NJ` zeros state/NYC in savings |

### SPE anchor

`strategy_change=17000`, total rate 20% → savings **3400**, cash **13600**.
