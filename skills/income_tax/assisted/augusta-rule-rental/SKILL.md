---
name: augusta-rule-rental
description: >-
  Activates when the user asks about Augusta Rule - tax-free rental income applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Augusta Rule-Rental Income (Tax Free)"
  ita_id: "ita_018"
  category: "business"
  outline: ita-rules/strategy-outlines/augusta-rule-rental.md
  config: ita-rules/strategy_runtime/configs/augusta-rule-rental.json
  recommended_tools:
    - name: assess_augusta_rule_rental_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_augusta_rule_rental_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Augusta Rule - tax-free rental income

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/augusta-rule-rental.json`](ita-rules/strategy_runtime/configs/augusta-rule-rental.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/augusta-rule-rental.md`](ita-rules/strategy-outlines/augusta-rule-rental.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_augusta_rule_rental_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `tax_free_rental_income`.

---

## Part 2 — Savings

Call **`estimate_augusta_rule_rental_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `tax_free_rental_income` (advisor)
- `days_rented` (user)
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
assess_augusta_rule_rental_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_augusta_rule_rental_savings
        │
        ▼
Show savings / cash outlay
```
