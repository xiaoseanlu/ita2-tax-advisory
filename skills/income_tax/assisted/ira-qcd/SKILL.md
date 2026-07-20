---
name: ira-qcd
description: >-
  Activates when the user asks about IRA QCD applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "IRA QCD"
  ita_id: "ita_051"
  category: "charity"
  outline: ita-rules/strategy-outlines/ira-qcd.md
  config: ita-rules/strategy_runtime/configs/ira-qcd.json
  recommended_tools:
    - name: assess_ira_qcd_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_ira_qcd_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# IRA QCD

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/ira-qcd.json`](ita-rules/strategy_runtime/configs/ira-qcd.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/ira-qcd.md`](ita-rules/strategy-outlines/ira-qcd.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_ira_qcd_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `qcd_amount`.

---

## Part 2 — Savings

Call **`estimate_ira_qcd_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `qcd_amount` (advisor)
- `ira_balance` (user)
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
assess_ira_qcd_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_ira_qcd_savings
        │
        ▼
Show savings / cash outlay
```
