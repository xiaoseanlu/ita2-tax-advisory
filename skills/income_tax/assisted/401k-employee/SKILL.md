---
name: 401k-employee
description: >-
  Activates when the user asks whether a W-2 401(k) employee elective deferral
  can be increased, how much headroom remains after shared 401(k)/403(b)/Solo
  baselines, or what tax savings that increase would produce. Does not invent
  engine max401kContributionAllowed or combined401KLimit — pass those in.
metadata:
  examples:
    - "Can we maximize the 401k deferral on this W-2?"
    - "How much more 401(k) employee contribution room does the taxpayer have?"
    - "What tax savings if we increase Box 12-D by $22,500?"
    - "Why isn't 401k EE recommended when this W-2 already has a 403(b)?"
  recommended_tools:
    - name: assess_401k_employee_applicability
      description: >-
        Returns whether a W-2 is applicable/recommended for 401(k) EE
        (deleteNextYear, wages, spouse marriedMAGI, 403b/457b gates, headroom).
    - name: estimate_401k_employee_savings
      description: >-
        Returns SPE-faithful projected tax savings and cash outlay for
        STRATEGY_CHANGE = min(wgFedwages, employee_headroom) (or advisor override).
---

# 401(k) Employee Contribution

Run this Skill in **two Tool parts**. Tools own limits and formulas from SPE.

See `INPUTS.md` and `ita-rules/401k-employee-strategy.md`.

---

## Part 1 — Applicability

Call **`assess_401k_employee_applicability`** for a specific W-2.

- Pool: `deleteNextYear == 0` and `wgFedwages > 0`
- Applicable: `wages401kContribution <= employee_headroom` (spouse needs filingStatus 2|5)
- Recommended: also `wages403bContribution == 0`, `wg457b == 0`, headroom `> 0`

Part 1 does **not** invent `max401kContributionAllowed` — pass the engine value.

---

## Part 2 — Savings

Call **`estimate_401k_employee_savings`**.

Default `strategy_change` = `min(wgFedwages, employee_headroom)`.

```
PROJECTED_TAX_SAVINGS = round(strategy_change × MARGINAL_RATE_TOTAL / 100)
CASH_OUTLAY = strategy_change − PROJECTED_TAX_SAVINGS
```

PA residents: state/NYC zeroed for savings (added-scope SPE behavior).

---

## Protocol

```
W-2 + engine max/combined + baselines + filing status
        │
        ▼
[Tool] assess_401k_employee_applicability
        │
        ├── not applicable → done
        │
        ▼
Confirmed strategy_change (default = min(wages, headroom))
        │
        ▼
[Tool] estimate_401k_employee_savings
```
