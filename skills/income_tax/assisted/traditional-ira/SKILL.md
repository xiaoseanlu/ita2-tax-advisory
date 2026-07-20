---
name: traditional-ira
description: >-
  Activates for Traditional IRA deductible contribution room and marginal-rate
  savings. Person-level (not W-2).
metadata:
  recommended_tools:
    - name: assess_traditional_ira_applicability
    - name: estimate_traditional_ira_savings
---

# Traditional IRA

See `INPUTS.md` and `ita-rules/traditional-ira-strategy.md`.

```
STRATEGY_CHANGE = maxIRAAllowed − iraContribution
PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE × MARGINAL_RATE_TOTAL / 100)
CASH_OUTLAY = STRATEGY_CHANGE − PROJECTED_TAX_SAVINGS
```

MA/NH/NJ/PA nonconforming states zero state/NYC for savings.

SPE anchor: change 2000 @ 37% → savings 740, cash 1260.
