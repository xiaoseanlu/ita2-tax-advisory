---
name: fsa-contribution
description: >-
  Activates when the user asks about Flex Spending Account applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "FSA Contribution"
  ita_id: "ita_013"
  category: "health"
  outline: ita-rules/strategy-outlines/fsa-contribution.md
  config: ita-rules/strategy_runtime/configs/fsa-contribution.json
  recommended_tools:
    - name: assess_fsa_contribution_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_fsa_contribution_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Flex Spending Account

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/fsa-contribution.json`](ita-rules/strategy_runtime/configs/fsa-contribution.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/fsa-contribution.md`](ita-rules/strategy-outlines/fsa-contribution.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_fsa_contribution_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Default `strategy_change` = `max(0, employee_max_fsa_contribution - baseline_amount)`.

---

## Part 2 — Savings

Call **`estimate_fsa_contribution_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `employee_max_fsa_contribution` (engine)
- `baseline_amount` (user)
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
assess_fsa_contribution_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_fsa_contribution_savings
        │
        ▼
Show savings / cash outlay
```
