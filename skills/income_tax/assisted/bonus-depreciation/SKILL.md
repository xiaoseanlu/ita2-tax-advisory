---
name: bonus-depreciation
description: >-
  Activates when the user asks about Bonus depreciation applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Bonus Depreciation"
  ita_id: "ita_025"
  category: "business"
  outline: ita-rules/strategy-outlines/bonus-depreciation.md
  config: ita-rules/strategy_runtime/configs/bonus-depreciation.json
  recommended_tools:
    - name: assess_bonus_depreciation_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_bonus_depreciation_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Bonus depreciation

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/bonus-depreciation.json`](ita-rules/strategy_runtime/configs/bonus-depreciation.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/bonus-depreciation.md`](ita-rules/strategy-outlines/bonus-depreciation.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_bonus_depreciation_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `depreciation_expense`.

---

## Part 2 — Savings

Call **`estimate_bonus_depreciation_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `depreciation_expense` (advisor)
- `asset_basis` (user)
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
assess_bonus_depreciation_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_bonus_depreciation_savings
        │
        ▼
Show savings / cash outlay
```
