---
name: backdoor-roth-ira
description: >-
  Activates when nondeductible IRA basis exists and a backdoor Roth conversion
  may be appropriate. Savings always zero in SPE.
metadata:
  recommended_tools:
    - name: assess_backdoor_roth_ira_applicability
    - name: estimate_backdoor_roth_ira_savings
---

# Backdoor Roth IRA

See `INPUTS.md` and `ita-rules/backdoor-roth-ira-strategy.md`.

```
STRATEGY_CHANGE default = 0
PROJECTED_TAX_SAVINGS = 0
CASH_OUTLAY = STRATEGY_CHANGE
```

Recommend: `non_deductible_ira > 0` (spouse needs married filing).
