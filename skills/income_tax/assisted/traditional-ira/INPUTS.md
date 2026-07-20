# Traditional IRA — inputs

| Field | Meaning |
|-------|---------|
| `person.earned_income` | Applicability (> 0) |
| `person.ira_contribution` | Current contribution |
| `person.max_ira_allowed` | Engine maxIRAContributionAllowed |
| `person.roth_cont` | Must be 0 to recommend |
| `person.has_plan` / `person.ira_magi` / `person.ira_phase_out_begin` | Deductibility phase-out |

### SPE anchor

max 6000, contributed 4000 → change **2000** @ 37% → savings **740**, cash **1260**.
