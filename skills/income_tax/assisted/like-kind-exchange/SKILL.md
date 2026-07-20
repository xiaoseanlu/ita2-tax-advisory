---
name: like-kind-exchange
description: >-
  Activates when the user asks about Like-kind exchange applicability, recommendation,
  or projected tax savings. Uses savings-core runtime (marginal rate × strategy change).
metadata:
  status: outlined
  fidelity: none
  spe_folder: "Like Kind Exchange"
  ita_id: "ita_017"
  category: "capital"
  outline: ita-rules/strategy-outlines/like-kind-exchange.md
  config: ita-rules/strategy_runtime/configs/like-kind-exchange.json
  recommended_tools:
    - name: assess_like_kind_exchange_applicability
      description: Returns whether strategy is applicable/recommended (strategy_change > 0).
    - name: estimate_like_kind_exchange_savings
      description: Returns projected tax savings and cash outlay (savings-core formula).
---

# Like-kind exchange

**Status:** implemented (savings-core fidelity).

Deterministic tools delegate to [`strategy_runtime`](../../../../ita-rules/strategy_runtime/engine.py).
Field definitions: [`ita-rules/strategy_runtime/configs/like-kind-exchange.json`](ita-rules/strategy_runtime/configs/like-kind-exchange.json).

See `INPUTS.md` and [`ita-rules/strategy-outlines/like-kind-exchange.md`](ita-rules/strategy-outlines/like-kind-exchange.md) for SPE context.

---

## Part 1 — Applicability

Call **`assess_like_kind_exchange_applicability`** with form fields from the config.
Applicable when `strategy_change > 0` after defaults/expression.
Advisor must supply `strategy_change` > 0.

---

## Part 2 — Savings

Call **`estimate_like_kind_exchange_savings`** when applicable.

```
projected_tax_savings = round(strategy_change × marginal_rate_total / 100)
cash_outlay = strategy_change - projected_tax_savings  (contribution-like strategies)
```

Mode: `marginal_x_change` · Cash outlay: `contribution`

---

## Form fields

- `deferred_gain` (advisor)
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
assess_like_kind_exchange_applicability
        │
        ├── not applicable → done
        │
        ▼
estimate_like_kind_exchange_savings
        │
        ▼
Show savings / cash outlay
```
