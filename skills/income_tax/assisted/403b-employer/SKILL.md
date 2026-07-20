---
name: 403b-employer
description: >-
  Activates for 403(b) employer matching on W-2s where the employee already
  defers to a 403(b). Match capped by employee headroom.
metadata:
  recommended_tools:
    - name: assess_403b_employer_applicability
    - name: estimate_403b_employer_savings
---

# 403(b) Employer Contribution

See `INPUTS.md` and `ita-rules/403b-employer-strategy.md`.

```
match = min(wgFedwages × 5%, employee_headroom)
STRATEGY_CHANGE = round(min(max401kAllowed, min(match, employee_headroom)))
CASH_OUTLAY = 0
```

Recommend: `wages403b > 0` and `match > 0`. NJ added scope zeros state/NYC.

SPE anchor: 2250 @ 20% → savings 450, cash 0.
