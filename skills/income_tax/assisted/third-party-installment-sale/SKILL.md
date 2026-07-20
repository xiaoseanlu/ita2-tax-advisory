---
name: third-party-installment-sale
description: >-
  Activates when the user asks about Third party installment sale applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Third Party Installment Sale"
  ita_id: "ita_024"
  category: "capital"
  outline: ita-rules/strategy-outlines/third-party-installment-sale.md
  config: ita-rules/strategy_runtime/configs/third-party-installment-sale.json
  recommended_tools:
    - name: assess_third_party_installment_sale_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_third_party_installment_sale_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Third party installment sale

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/third-party-installment-sale.json`](ita-rules/strategy_runtime/configs/third-party-installment-sale.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/third-party-installment-sale.md`](ita-rules/strategy-outlines/third-party-installment-sale.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_third_party_installment_sale_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_third_party_installment_sale_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `installment_deferral` (advisor)
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
assess_third_party_installment_sale_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_third_party_installment_sale_savings
        │
        ▼
Show savings / cash outlay
```
