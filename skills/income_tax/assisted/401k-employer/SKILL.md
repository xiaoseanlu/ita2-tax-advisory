---
name: 401k-employer
description: >-
  Activates when the user asks about 401(k) employer matching headroom, whether
  a W-2 qualifies for an employer match increase, or projected tax savings from
  that match. Does not invent engine limits — pass max401kContributionAllowed
  and combined401KLimit.
metadata:
  examples:
    - "Is there employer 401k match room on this W-2?"
    - "How much should the client contribute to capture the full employer match?"
  recommended_tools:
    - name: assess_401k_employer_applicability
      description: SPE applicability/recommend gates for 401(k) ER match.
    - name: estimate_401k_employer_savings
      description: SPE projected tax savings; CASH_OUTLAY always 0.
---

# 401(k) Employer Contribution

Two Tool parts. See `INPUTS.md` and `ita-rules/401k-employer-strategy.md`.

## Part 1 — Applicability

`assess_401k_employer_applicability` — pool: active W-2 with wages; applicable when `wages401k <= employer_headroom`; recommend when no 403(b)/457(b), `match > 0`.

## Part 2 — Savings

`estimate_401k_employer_savings`

```
employer_headroom = max(combined401KLimit − combined_limit_absorbed, 0)
match = min(wgFedwages × 5%, employer_headroom)
STRATEGY_CHANGE = round(min(max401kAllowed, min(match, employer_headroom)))
PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE × MARGINAL_RATE_TOTAL / 100)
CASH_OUTLAY = 0
```

SPE anchor: 7500 @ 33% → savings 2475, cash 0.
