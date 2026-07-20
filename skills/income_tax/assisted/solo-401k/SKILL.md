---
name: solo-401k
description: >-
  Activates when the user asks whether a Solo 401(k) contribution makes sense
  for a self-employed person, how much more they can contribute, or what tax
  savings they would see from maximizing a Solo 401(k) elective deferral. Does
  not invent the engine maxSolo401kContributionAllowed, set up a plan, or
  recalculate the full return—savings come from the dedicated savings tool.
metadata:
  examples:
    - "Can we maximize a Solo 401k for this Schedule C filer?"
    - "How much Solo 401(k) room does my spouse still have?"
    - "What tax savings if we contribute another $27,000 to Solo 401k?"
    - "Why isn't Solo 401k recommended when they already have a SEP-IRA?"
  recommended_tools:
    - name: assess_solo401k_applicability
      description: >-
        Returns whether Solo 401(k) is applicable/recommended for taxpayer or
        spouse (SE/earned income, no-wages biz gate, SEP conflict, headroom).
    - name: estimate_solo401k_savings
      description: >-
        Returns SPE-faithful projected tax savings and cash outlay for a
        confirmed strategy_change (defaults to remaining employee headroom).
---

# Solo 401(k) contribution

Run this Skill in **two Tool parts**. Tools own limits and formulas.

See `INPUTS.md` for the full input contract.

---

## Part 1 — Applicability

Call **`assess_solo401k_applicability`** when the question is whether Solo 401(k)
can or should be modeled for **taxpayer** or **spouse**.

- Spouse requires married filing status (SPE `filingStatus` 2 or 5).
- Need positive SE or earned income and a qualifying solo business (no wages /
  S-Corp with W-2), or opposite-EIN wage match.
- Recommend needs `maxAllowedContribution > 0` and SEP rule: if `sepIRA > 0`
  must already have a Solo elective deferral.

Part 1 does **not** invent `maxSolo401kContributionAllowed` — pass the engine value.

---

## Part 2 — Savings

Call **`estimate_solo401k_savings`** when Part 1 is applicable (or product allows
estimate-only).

Default `strategy_change` = remaining employee headroom from shared 401(k) limit
math. Advisor may override downward.

Savings (SPE):

```
PROJECTED_TAX_SAVINGS = round(strategy_change × MARGINAL_RATE_TOTAL / 100)
CASH_OUTLAY = strategy_change − PROJECTED_TAX_SAVINGS
```

`MARGINAL_RATE_TOTAL` = fed + state + NYC (state/NYC zeroed for PA in added scope).
No SE/FICA savings modeled.

---

## Protocol

```
Person facts (taxpayer | spouse) + engine max + baselines
        │
        ▼
[Tool] assess_solo401k_applicability
        │
        ├── not applicable → done
        │
        ▼
Confirmed strategy_change (default = headroom)
+ marginal rates (from return)
        │
        ▼
[Tool] estimate_solo401k_savings
        │
        ▼
Show savings / cash outlay / warnings
```

---

## Guardrails

1. Core path is Tool-only (no LLM required for math).
2. Never invent `maxSolo401kContributionAllowed`.
3. Match SPE SEP conflict and married-spouse gates.
4. Label Tool savings as an estimate unless a full tax recalc is run afterward.
