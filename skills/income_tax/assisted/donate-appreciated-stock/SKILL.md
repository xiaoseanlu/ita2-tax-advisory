---
name: donate-appreciated-stock
description: >-
  Activates when the user asks about Donating Appreciated Stock applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Donating Appreciated Stock to Charity"
  ita_id: "ita_049"
  category: "charity"
  outline: ita-rules/strategy-outlines/donate-appreciated-stock.md
  config: ita-rules/strategy_runtime/configs/donate-appreciated-stock.json
  recommended_tools:
    - name: assess_donate_appreciated_stock_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_donate_appreciated_stock_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Donating Appreciated Stock

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/donate-appreciated-stock.json`](ita-rules/strategy_runtime/configs/donate-appreciated-stock.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/donate-appreciated-stock.md`](ita-rules/strategy-outlines/donate-appreciated-stock.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_donate_appreciated_stock_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_donate_appreciated_stock_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `donation_fmv` (advisor)
- `unrealized_gain` (user)
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
assess_donate_appreciated_stock_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_donate_appreciated_stock_savings
        │
        ▼
Show savings / cash outlay
```
