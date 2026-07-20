---
name: real-estate-professional
description: >-
  Activates when the user asks about Real Estate Professional applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "realEstateProfessional"
  ita_id: "ita_001"
  category: "business"
  outline: ita-rules/strategy-outlines/real-estate-professional.md
  config: ita-rules/strategy_runtime/configs/real-estate-professional.json
  recommended_tools:
    - name: assess_real_estate_professional_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_real_estate_professional_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Real Estate Professional

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/real-estate-professional.json`](ita-rules/strategy_runtime/configs/real-estate-professional.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/real-estate-professional.md`](ita-rules/strategy-outlines/real-estate-professional.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_real_estate_professional_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_real_estate_professional_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `passive_loss_unlocked` (advisor)
- `strategy_change` (advisor)
- `federal_marginal_rate_pct` (engine)
- `state_marginal_rate_pct` (engine)
- `nyc_marginal_rate_pct` (engine)

---

## Protocol

```
Payload (engine + user + advisor fields)
        │
        ▼
assess_real_estate_professional_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_real_estate_professional_savings
        │
        ▼
Show savings / cash outlay
```
