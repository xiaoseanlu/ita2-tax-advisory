# Skill: Solo 401(k) (`income_tax.assisted.solo-401k`)

| Part | Tool | Needs strategy_change? |
|------|------|------------------------|
| 1. Applicability | `assess_solo401k_applicability` | No |
| 2. Savings | `estimate_solo401k_savings` | Optional (defaults to headroom) |

## Calculator UI

```bash
python3 web_ui_server.py
# → http://localhost:5000/ita-strategies
```
