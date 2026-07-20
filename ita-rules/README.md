# ITA Rules: Registry, Outlines, and Schema Mapping

This folder is the source of truth for strategy metadata used by the ITA strategies hub.

## Quick start — just run and try it

For someone who only wants to open the hub and click around (no SPE rebuilds required):

1. **Clone / open** this repo (`project-air`).
2. **Install Python deps** (once), from the repo root:

```bash
cd /path/to/project-air
python3 -m pip install -r requirements.txt
```

3. **Start the server** (from the repo root):

```bash
python3 web_ui_server.py
```

4. **Open the hub** in a browser:

- [http://localhost:5000/ita-strategies](http://localhost:5000/ita-strategies)

5. **What to try**

| Area | Where | What to do |
|------|--------|------------|
| Entity Optimization | Left nav accordion | Open **S-Corporation entity selection**, enter SE facts + reasonable wage, click **Estimate savings** |
| Retirement | Left nav accordion | Try **401(k) Employee**, **Solo 401(k)**, or another SPE strategy; run **Assess** then **Estimate** |
| Developers Guide | Right pane | See ITA JSON paths and `TURBO_TAX` mappings; red `NOT_AVAILABLE` = no TurboTax mapping in `tax-model-schema.json` |

No API keys are required for these deterministic strategy tools. If port 5000 is taken:

```bash
PORT=5001 python3 web_ui_server.py
# → http://localhost:5001/ita-strategies
```

## What lives here

- `strategy-registry.json` — strategy catalog used by UI/server routing.
- `strategy-outlines/` — per-strategy extracted inputs (`.json`) and readable summaries (`.md`).
- `tax-model-schema.json` — ITA schema used to map strategy fields to `TURBO_TAX` addresses.
- `build_strategy_registry.py` — one-shot builder for registry + outlines.
- `outline_strategy_inputs.py` / `spe_inputs.py` — SPE field extraction helpers.

## Scorp deep dive

- `../skills/income_tax/assisted/scorp-conversion/STRATEGY.md` — full SPE-faithful S-Corp logic.
- `../skills/income_tax/assisted/scorp-conversion/` — skill/tool implementation.
- `scorp-conversion-strategy.md` — pointer doc to the skill-local strategy guide.

## Build flows

### 1) Rebuild registry + outlines from SPE

```bash
cd ita-rules
python3 build_strategy_registry.py
```

This regenerates:
- `strategy-registry.json`
- `strategy-outlines/*.json`
- `strategy-outlines/*.md`

### 2) Inspect one strategy outline ad hoc

```bash
cd ita-rules
python3 outline_strategy_inputs.py --list
python3 outline_strategy_inputs.py "Scorp" --json
python3 outline_strategy_inputs.py "401k" --user-only --show-includes
```

### 3) Rebuild ITA ↔ TURBO_TAX catalog for UI

```bash
cd ..
python3 scripts/build_ita_tps_catalog.py
```

This regenerates:
- `web_ui/ita-tps-field-catalog.json`

The hub redlines `NOT_AVAILABLE` when no `TURBO_TAX` mapping exists for a row.

## Notes

- `strategy-outlines/*` are runtime docs for the hub; keep them committed.
- `tax-model-schema.json` is intentionally large and committed for deterministic mapping.
- Legacy analysis artifacts like `analyze_1040_feasibility.py` remain available, but are not required for the strategies hub runtime path.
