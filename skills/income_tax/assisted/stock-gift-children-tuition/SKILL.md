---
name: stock-gift-children-tuition
description: >-
  Activates when the user asks about Stock Gift For Childrens Tution applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Stock gift for childrens tuition"
  ita_id: null
  category: "capital"
  outline: ita-rules/strategy-outlines/stock-gift-children-tuition.md
  config: ita-rules/strategy_runtime/configs/stock-gift-children-tuition.json
  recommended_tools:
    - name: assess_stock_gift_children_tuition_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_stock_gift_children_tuition_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Stock Gift For Childrens Tution

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/stock-gift-children-tuition.json`](ita-rules/strategy_runtime/configs/stock-gift-children-tuition.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/stock-gift-children-tuition.md`](ita-rules/strategy-outlines/stock-gift-children-tuition.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_stock_gift_children_tuition_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_stock_gift_children_tuition_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `gift_fmv` (advisor)
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
assess_stock_gift_children_tuition_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_stock_gift_children_tuition_savings
        │
        ▼
Show savings / cash outlay
```
