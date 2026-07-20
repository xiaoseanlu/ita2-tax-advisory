---
name: residential-energy-credit
description: >-
  Activates when the user asks about Residential Energy Credit applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Residential Energy Credit"
  ita_id: "ita_048"
  category: "credit"
  outline: ita-rules/strategy-outlines/residential-energy-credit.md
  config: ita-rules/strategy_runtime/configs/residential-energy-credit.json
  recommended_tools:
    - name: assess_residential_energy_credit_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_residential_energy_credit_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Residential Energy Credit

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/residential-energy-credit.json`](ita-rules/strategy_runtime/configs/residential-energy-credit.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/residential-energy-credit.md`](ita-rules/strategy-outlines/residential-energy-credit.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_residential_energy_credit_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `energy_credit_amount`.

---

## Part 2 — Savings

Call **`estimate_residential_energy_credit_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `credit` · Cash outlay: `none`

---

## Form fields

- `energy_expenditure` (user)
- `energy_credit_amount` (engine)
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
assess_residential_energy_credit_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_residential_energy_credit_savings
        │
        ▼
Show savings / cash outlay
```
