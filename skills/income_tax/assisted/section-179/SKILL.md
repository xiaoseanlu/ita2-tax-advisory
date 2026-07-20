---
name: section-179
description: >-
  Activates when the user asks about Section 179 applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Section 179"
  ita_id: "ita_026"
  category: "business"
  outline: ita-rules/strategy-outlines/section-179.md
  config: ita-rules/strategy_runtime/configs/section-179.json
  recommended_tools:
    - name: assess_section_179_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_section_179_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Section 179

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/section-179.json`](ita-rules/strategy_runtime/configs/section-179.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/section-179.md`](ita-rules/strategy-outlines/section-179.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_section_179_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `section_179_expense`.

---

## Part 2 — Savings

Call **`estimate_section_179_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `section_179_expense` (advisor)
- `qualifying_property_cost` (user)
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
assess_section_179_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_section_179_savings
        │
        ▼
Show savings / cash outlay
```
