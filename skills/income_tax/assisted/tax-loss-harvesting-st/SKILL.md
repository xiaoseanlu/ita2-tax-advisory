---
name: tax-loss-harvesting-st
description: >-
  Activates when the user asks about Tax loss harvesting (short-term) applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Tax Loss Harvesting - ST"
  ita_id: "ita_023"
  category: "capital"
  outline: ita-rules/strategy-outlines/tax-loss-harvesting-st.md
  config: ita-rules/strategy_runtime/configs/tax-loss-harvesting-st.json
  recommended_tools:
    - name: assess_tax_loss_harvesting_st_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_tax_loss_harvesting_st_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Tax loss harvesting (short-term)

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/tax-loss-harvesting-st.json`](ita-rules/strategy_runtime/configs/tax-loss-harvesting-st.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/tax-loss-harvesting-st.md`](ita-rules/strategy-outlines/tax-loss-harvesting-st.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_tax_loss_harvesting_st_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_tax_loss_harvesting_st_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `short_term_loss` (advisor)
- `short_term_gain` (user)
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
assess_tax_loss_harvesting_st_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_tax_loss_harvesting_st_savings
        │
        ▼
Show savings / cash outlay
```
