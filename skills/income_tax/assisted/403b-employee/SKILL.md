---
name: 403b-employee
description: >-
  Activates for 403(b) employee deferral headroom and tax savings on a W-2.
  Uses shared 401(k)/403(b) employee headroom from engine limits.
metadata:
  recommended_tools:
    - name: assess_403b_employee_applicability
    - name: estimate_403b_employee_savings
---

# 403(b) Employee Contribution

See `INPUTS.md` and `ita-rules/403b-employee-strategy.md`.

```
STRATEGY_CHANGE = min(wgFedwages, employee_headroom)
PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE × MARGINAL_RATE_TOTAL / 100)
CASH_OUTLAY = STRATEGY_CHANGE − PROJECTED_TAX_SAVINGS
```

Recommend: `wages403bContribution > 0` and headroom `> 0`. PA/NJ added scope zeros state/NYC.

SPE anchor: 17000 @ 20% → savings 3400, cash 13600.
