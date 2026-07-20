---
name: roth-ira-contribution
description: >-
  Activates when the user asks about Roth IRA contribution applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Roth IRA Contribution"
  ita_id: "ita_041"
  category: "retirement"
  outline: ita-rules/strategy-outlines/roth-ira-contribution.md
  config: ita-rules/strategy_runtime/configs/roth-ira-contribution.json
  recommended_tools:
    - name: assess_roth_ira_contribution_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_roth_ira_contribution_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Roth IRA contribution

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/roth-ira-contribution.json`](ita-rules/strategy_runtime/configs/roth-ira-contribution.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/roth-ira-contribution.md`](ita-rules/strategy-outlines/roth-ira-contribution.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_roth_ira_contribution_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `max(0, max_roth_ira - roth_contribution_made)`.

---

## Part 2 — Savings

Call **`estimate_roth_ira_contribution_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `max_roth_ira` (engine)
- `roth_contribution_made` (user)
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
assess_roth_ira_contribution_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_roth_ira_contribution_savings
        │
        ▼
Show savings / cash outlay
```
