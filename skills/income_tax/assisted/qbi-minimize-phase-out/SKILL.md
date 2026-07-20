---
name: qbi-minimize-phase-out
description: >-
  Activates when the user asks about Optimize QBI applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "QBI Minimize Phase Out"
  ita_id: "ita_029"
  category: "business"
  outline: ita-rules/strategy-outlines/qbi-minimize-phase-out.md
  config: ita-rules/strategy_runtime/configs/qbi-minimize-phase-out.json
  recommended_tools:
    - name: assess_qbi_minimize_phase_out_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_qbi_minimize_phase_out_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Optimize QBI

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/qbi-minimize-phase-out.json`](ita-rules/strategy_runtime/configs/qbi-minimize-phase-out.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/qbi-minimize-phase-out.md`](ita-rules/strategy-outlines/qbi-minimize-phase-out.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_qbi_minimize_phase_out_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_qbi_minimize_phase_out_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `qbi_optimization_benefit` (advisor)
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
assess_qbi_minimize_phase_out_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_qbi_minimize_phase_out_savings
        │
        ▼
Show savings / cash outlay
```
