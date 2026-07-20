---
name: mega-backdoor-roth
description: >-
  Activates when Roth IRA phase-out applies, deferrals maxed at prior-year
  employee limit, and after-tax mega contribution room remains.
metadata:
  recommended_tools:
    - name: assess_mega_backdoor_roth_applicability
    - name: estimate_mega_backdoor_roth_savings
---

# Mega Backdoor Roth

See `INPUTS.md` and `ita-rules/mega-backdoor-roth-strategy.md`.

```
megaMaxAllowed = maxSolo401kAllowed − currentYearMax401kAllowed
STRATEGY_CHANGE = megaMaxAllowed
PROJECTED_TAX_SAVINGS = 0
CASH_OUTLAY = STRATEGY_CHANGE
```

Recommend: `modified_agi > roth_phase_out`, wages > 0, and 401k/403b/457b ≥ prior_year_max_401k.
