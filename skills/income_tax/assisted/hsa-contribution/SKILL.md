---
name: hsa-contribution
description: >-
  Activates when the user asks about HSA Contribution applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "HSA Contribution"
  ita_id: "ita_015"
  category: "health"
  outline: ita-rules/strategy-outlines/hsa-contribution.md
  config: ita-rules/strategy_runtime/configs/hsa-contribution.json
  recommended_tools:
    - name: assess_hsa_contribution_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_hsa_contribution_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# HSA Contribution

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/hsa-contribution.json`](ita-rules/strategy_runtime/configs/hsa-contribution.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/hsa-contribution.md`](ita-rules/strategy-outlines/hsa-contribution.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_hsa_contribution_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `max(0, max_hsa_contribution - hsa_contribution_made)`.

---

## Part 2 — Savings

Call **`estimate_hsa_contribution_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `max_hsa_contribution` (engine)
- `hsa_contribution_made` (user)
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
assess_hsa_contribution_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_hsa_contribution_savings
        │
        ▼
Show savings / cash outlay
```
