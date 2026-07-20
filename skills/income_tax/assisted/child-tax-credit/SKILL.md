---
name: child-tax-credit
description: >-
  Activates when the user asks about Child Tax Credit applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Child Tax Credit"
  ita_id: "ita_047"
  category: "credit"
  outline: ita-rules/strategy-outlines/child-tax-credit.md
  config: ita-rules/strategy_runtime/configs/child-tax-credit.json
  recommended_tools:
    - name: assess_child_tax_credit_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_child_tax_credit_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Child Tax Credit

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/child-tax-credit.json`](ita-rules/strategy_runtime/configs/child-tax-credit.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/child-tax-credit.md`](ita-rules/strategy-outlines/child-tax-credit.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_child_tax_credit_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `lost_credit`.

---

## Part 2 — Savings

Call **`estimate_child_tax_credit_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `credit` · Cash outlay: `none`

---

## Form fields

- `lost_credit` (advisor)
- `qualifying_children` (user)
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
assess_child_tax_credit_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_child_tax_credit_savings
        │
        ▼
Show savings / cash outlay
```
