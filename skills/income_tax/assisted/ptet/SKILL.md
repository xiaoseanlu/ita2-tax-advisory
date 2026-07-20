---
name: ptet
description: >-
  Activates when the user asks about Pass-through-Entity-Tax applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "PTET"
  ita_id: null
  category: "business"
  outline: ita-rules/strategy-outlines/ptet.md
  config: ita-rules/strategy_runtime/configs/ptet.json
  recommended_tools:
    - name: assess_ptet_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_ptet_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Pass-through-Entity-Tax

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/ptet.json`](ita-rules/strategy_runtime/configs/ptet.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/ptet.md`](ita-rules/strategy-outlines/ptet.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_ptet_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `ptet_deduction`.

---

## Part 2 — Savings

Call **`estimate_ptet_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `ptet_deduction` (advisor)
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
assess_ptet_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_ptet_savings
        │
        ▼
Show savings / cash outlay
```
