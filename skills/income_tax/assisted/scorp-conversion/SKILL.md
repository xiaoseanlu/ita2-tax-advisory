---
name: scorp-conversion
description: >-
  Activates when the user asks whether an S-Corp election makes sense for their
  self-employed business, whether they can or should model converting Schedule C
  (or similar SE income) to an S corporation, or what tax savings they would see
  after paying themselves a reasonable wage. Does not file Form 2553, choose or
  invent reasonable compensation, run general entity comparisons outside S-Corp
  conversion, or recalculate the full return—savings estimates come from the
  dedicated savings tool given confirmed inputs.
metadata:
  examples:
    - "Does an S-Corp election make sense for my Schedule C?"
    - "Can we convert this consulting business to an S corporation?"
    - "What SE tax would we save if I take a reasonable salary from an S-Corp?"
    - "Is S-Corp conversion applicable for my spouse's Side hustle?"
    - "Why isn't S-Corp showing much savings when I already have a large W-2?"
  recommended_tools:
    - name: assess_scorp_applicability
      description: >-
        Returns whether the self-employed activity is applicable and recommended
        for S-Corp conversion modeling (SE earnings and ownership gates). Does
        not require a reasonable wage.
    - name: estimate_scorp_savings
      description: >-
        Returns an SPE-faithful estimated tax savings breakdown for converting
        the activity, given a confirmed reasonable wage and the owner's other
        wages already counting toward the Social Security wage base.
---

# S-Corp conversion

When the user asks about S-Corp election / conversion for a self-employed
business, run this Skill in **two Tool parts**. Do not put dollar thresholds or
tax formulas in this playbook—Tools own that logic.

See `INPUTS.md` for the full input contract and `STRATEGY.md` for the SPE logic deep-dive.

---

## Part 1 — Applicability

Call **`assess_scorp_applicability`** when the question is whether conversion can
or should be modeled.

Pass the activity facts (Schedule C / F / partnership SE), including **who owns
it**: `taxpayer`, `spouse`, or `joint`.

- If `applicable` is false → stop; use Tool `reasons` (e.g. non-SE or non-positive
  net earnings). Do not soft-override.
- If applicable but not `recommended` → may still estimate only if the product
  allows; do not present as a top recommendation.
- If recommended → proceed only after a **confirmed** reasonable wage for Part 2.

Part 1 does **not** need `reasonable_wage`.

---

## Part 2 — Savings

Call **`estimate_scorp_savings`** only when:

1. Part 1 is applicable (or product explicitly allows estimate-only), and  
2. The advisor has confirmed `reasonable_wage`.

Also pass rates that reflect the **same person** who owns the Schedule C:

- `rates.income_already_taxed_by_ss` — that person's W-2 (and other) wages already
  subject to Social Security for the year. If they are near the SS wage base,
  Social Security savings from dropping SE income are limited.
- Marginal rates and SS wage base for the tax year.

Surface Tool outputs as-is: savings breakdown, wage vs S-Corp split, warnings
(including low/no SS headroom or weak economics when income is thin/negative).

If `reasonable_wage` is missing → ask the advisor; **do not invent a wage**.

---

## Protocol

```
Activity facts (incl. taxpayer | spouse | joint)
        │
        ▼
[Tool] assess_scorp_applicability
        │
        ├── not applicable → done
        │
        ▼
Confirmed reasonable_wage
+ owner's wages already toward SS wage base (when known)
        │
        ▼
[Tool] estimate_scorp_savings
        │
        ▼
Show savings / warnings (+ optional apply + full return recalc)
```

---

## Guardrails

1. Core path is Tool-only (no LLM required for applicable / savings math).
2. Never invent `reasonable_wage`.
3. Match SS wage-base inputs to the Schedule C **owner** (taxpayer vs spouse).
4. Label Tool savings as an estimate unless a full tax recalc is run afterward.

---

## Runner

```bash
# Part 1
python3 skills/income_tax/assisted/scorp-conversion/scripts/run_agent.py \
  --tool-only --example --assess-only

# Part 1 + Part 2
python3 skills/income_tax/assisted/scorp-conversion/scripts/run_agent.py \
  --tool-only --example --reasonable-wage 70000
```
