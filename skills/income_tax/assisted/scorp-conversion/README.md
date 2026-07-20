# Skill: S-Corp conversion (`income_tax.assisted.scorp-conversion`)

**Two parts, two Tools — core path is deterministic (no LLM required).**

| Part | Tool | Needs wage? |
|------|------|-------------|
| 1. Applicability | `assess_scorp_applicability` | No |
| 2. Savings | `estimate_scorp_savings` | Yes (advisor-confirmed) |

| Artifact | Role |
|----------|------|
| [`SKILL.md`](./SKILL.md) | Two-part playbook |
| [`STRATEGY.md`](./STRATEGY.md) | SPE-faithful logic guide (applicability, wage lever, savings) |
| [`INPUTS.md`](./INPUTS.md) | Inputs per part |
| [`tools/scorp_conversion.py`](./tools/scorp_conversion.py) | Both Tools |
| [`tools/schema.json`](./tools/schema.json) | MCP-style schemas |
| [`scripts/run_agent.py`](./scripts/run_agent.py) | Runner |

## Quick start

```bash
# Part 1 only
python3 skills/income_tax/assisted/scorp-conversion/scripts/run_agent.py \
  --tool-only --example --assess-only

# Part 1 + Part 2
python3 skills/income_tax/assisted/scorp-conversion/scripts/run_agent.py \
  --tool-only --example --reasonable-wage 70000
```

## Calculator UI

```bash
python3 web_ui_server.py
# → http://localhost:5000/scorp-conversion
```

Form posts to `/api/scorp-conversion/assess` and `/api/scorp-conversion/estimate`.