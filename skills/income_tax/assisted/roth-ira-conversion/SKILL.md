---
name: roth-ira-conversion
description: >-
  Activates for Roth conversion planning — tax cost of converting pre-tax
  assets or growth comparison at retirement.
metadata:
  recommended_tools:
    - name: assess_roth_ira_conversion_applicability
    - name: estimate_roth_ira_conversion_savings
---

# Roth IRA Conversion

See `INPUTS.md` and `ita-rules/roth-ira-conversion-strategy.md`.

Two estimate modes via `estimate_mode`:

- **tax_cost** — negative savings (tax due); PA zeros state; NJ pension exclusion factor on state portion
- **growth** — `fv = amount × (1+r/100)^years`; savings = round(fv × retirement_rate/100); cash 0

Applicability: taxpayer always; spouse only when `filingStatus == 2`.
