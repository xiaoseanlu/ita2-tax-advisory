---
name: donor-advised-fund
description: >-
  Activates when the user asks about Donor Advised Fund To Time Contributions applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Donor Advised Fund To Time Contributions"
  ita_id: "ita_050"
  category: "charity"
  outline: ita-rules/strategy-outlines/donor-advised-fund.md
  config: ita-rules/strategy_runtime/configs/donor-advised-fund.json
  recommended_tools:
    - name: assess_donor_advised_fund_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_donor_advised_fund_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Donor Advised Fund To Time Contributions

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/donor-advised-fund.json`](ita-rules/strategy_runtime/configs/donor-advised-fund.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/donor-advised-fund.md`](ita-rules/strategy-outlines/donor-advised-fund.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_donor_advised_fund_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_donor_advised_fund_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `daf_contribution` (advisor)
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
assess_donor_advised_fund_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_donor_advised_fund_savings
        │
        ▼
Show savings / cash outlay
```
