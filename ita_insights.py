"""
ITA (Intuit Tax Advisor) strategy insights.
Uses scenario text + tax calculation result to recommend applicable ITA strategies.
Strategy content is from strategies/ (maintained from ITA product).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from genai_tax_core import _get_genos_env, ask_llm
from strategy_loader import StrategyLoader
from tax_fact_extractor import (
    extract_facts_from_data_model,
    extract_facts_from_text,
    format_data_model_for_insights,
    format_strategy_input_and_output,
    situation_narrative_text,
)

_ROOT = Path(__file__).resolve().parent
_INSIGHTS_STRATEGIES_COMPACT_FILE = _ROOT / "insights_strategies_compact.txt"
_INSIGHTS_STRATEGIES_COMPACT_FILE_10 = _ROOT / "insights_strategies_compact_10.txt"

# TEMP: hardcoded merged scenario text (disabled). Kept below for reference; not executed.
if False:
    _INSIGHTS_USER_BODY_HARDCODED = """\
Taxpayer situation (merged description — 2026, Head of Household)

Taxpayer is age 66 (65+), filing Head of Household for tax year 2026. One dependent: daughter, age 16, qualifying child under 17.

W-2 wages $338,775; federal withholding $12,000.

Sporting Goods LLC (Schedule C): gross receipts $300,000, expenses $200,000; material participation; business treated as qualifying for QBI in the narrative. Schedule C net (as in the modeled inputs/outputs): -$185,800. Depreciable asset: basis $2,000,000, placed in service 2026, 7-year recovery period.

Capital gains/losses: short-term capital gain/loss -$100,000; long-term capital gains $80,000. Narrative also references a short-term disposition of $10,000 and wash sale adjustment $10,000 (reconcile with line items if the engine netted into the short-term total).

Itemized: charitable contributions $25,000; home mortgage interest $18,500; real estate taxes $12,000; state/local taxes (deductible line) $10,000; SALT paid before cap $35,000.

Calculated outputs (summary): AGI $232,975; MAGI $232,975; taxable income $179,475; Schedule C net -$185,800; QBI deduction $0; deduction itemized, amount $53,500; total tax $10,544.28; SE tax $0.

Other credits mentioned in narrative: General Business Credit $12,542; foreign tax credit $5,000; energy efficient home improvement credit (Form 5695) $850."""

_strategy_loader: StrategyLoader | None = None


def _get_loader() -> StrategyLoader:
    global _strategy_loader
    if _strategy_loader is None:
        _strategy_loader = StrategyLoader()
    return _strategy_loader


def _insights_max_strategy_lines() -> int:
    """
    Cap on compact strategy lines when truncating. 0 = no cap (full list from file).
    Override: INSIGHTS_MAX_STRATEGY_LINES (positive integer limits lines).
    """
    try:
        v = int(os.environ.get("INSIGHTS_MAX_STRATEGY_LINES", "0").strip())
    except ValueError:
        v = 0
    if v <= 0:
        return 99999
    return max(1, v)


def _insights_max_strategies() -> int | None:
    """For bulky format: max number of strategy JSONs to include. 0 or unset = all. Override: INSIGHTS_MAX_STRATEGIES."""
    raw = os.environ.get("INSIGHTS_MAX_STRATEGIES", "0").strip()
    if not raw or raw == "0":
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    return max(1, v)


def _insights_use_bulky_strategies() -> bool:
    """INSIGHTS_STRATEGY_FORMAT=bulky uses full JSON from strategies/*. Default is compact list from insights_strategies_compact.txt."""
    return os.environ.get("INSIGHTS_STRATEGY_FORMAT", "compact").strip().lower() == "bulky"


def _insights_genos_model_chain() -> list[str]:
    """
    Models to try for insights matching (comma-separated IDs only).

    GenOS may return 422 on *output* risk screening for some models while gpt-5.1 passes.
    Default: use GENOS_MODEL_ID first, then fall back to gpt-5.1-2025-11-13 if different.

    Override: INSIGHTS_MODEL_ID=single_model (no automatic fallback).
    """
    override = os.environ.get("INSIGHTS_MODEL_ID", "").strip()
    if override:
        return [override]
    primary = _get_genos_env()["model_id"]
    fallback = "gpt-5.1-2025-11-13"
    if primary == fallback:
        return [primary]
    return [primary, fallback]


def _insights_compact_strategy_file_path() -> Path:
    """
    Which compact list file to load. Default: full list (insights_strategies_compact.txt).
    Short list (10): set INSIGHTS_STRATEGY_COMPACT_VARIANT=10 (or minimal, small).
    """
    raw = os.environ.get("INSIGHTS_STRATEGY_COMPACT_VARIANT")
    if raw is None:
        return _INSIGHTS_STRATEGIES_COMPACT_FILE
    v = raw.strip().lower()
    if not v:
        return _INSIGHTS_STRATEGIES_COMPACT_FILE
    if v in ("full", "51", "all"):
        return _INSIGHTS_STRATEGIES_COMPACT_FILE
    if v in ("10", "minimal", "small"):
        return _INSIGHTS_STRATEGIES_COMPACT_FILE_10
    return _INSIGHTS_STRATEGIES_COMPACT_FILE


def _load_insights_strategies_compact() -> str:
    """
    Canonical one-line-per-strategy list for insights (matches previous iterations.txt style).
    """
    path = _insights_compact_strategy_file_path()
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    loader = _get_loader()
    lines = loader.get_compact_strategy_list_for_insights()
    return "STRATEGIES (id: title — key signals):\n" + lines


def _truncate_strategy_block(full: str, max_lines: int) -> str:
    lines = [ln for ln in full.splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return full.strip()
    kept = lines[:max_lines]
    return "\n".join(kept) + f"\n... ({len(lines) - max_lines} more omitted)"


def _build_ita_system_prompt(strategies_list: str, *, bulky: bool) -> str:
    """System prompt: role, strategy catalog, analysis steps, response format. Tax numbers stay in user message."""
    if bulky:
        strategies_body = (
            "STRATEGIES (full descriptions from ITA JSON: summary, criteria, restrictions):\n"
            + strategies_list.strip()
        )
    else:
        # Compact: file usually includes "STRATEGIES (id: title — key signals):" header
        strategies_body = strategies_list.strip()
    return f"""You are a tax strategy advisor. Match the taxpayer's inputs and tax calculation output to applicable strategies.

{strategies_body}

ANALYSIS PROCESS:
1. Extract key facts from the situation and tax calculation (income types, amounts, business activities, family, retirement).
2. Match facts to strategy signals. Use specific thresholds (e.g., Schedule C $60K+ **profit** for S-Corp, equipment purchase for Section 179). **If modeled Schedule C net profit/loss is zero or negative, omit strategies that require Schedule C profit, positive QBI from that activity, or net self-employment earnings from it** (e.g. ita_002, ita_028, ita_029, ita_043, ita_044, ita_020, ita_021; ita_004 only when pass-through profit exists to compare). **When free-text and the Schedule C net line disagree, use the modeled Schedule C net line.** Depreciation (ita_025, ita_026) can still apply when assets are placed in service even if Schedule C shows a loss—treat that separately from S-Corp or QBI. Use only information in the inputs and outputs; avoid unstated assumptions.
3. Build a comprehensive list. Check: Entity (ita_002, ita_003), Business (ita_025, ita_026, ita_028), Retirement (ita_034, ita_035, ita_043, ita_044), Credits (ita_047), etc.

RESPONSE FORMAT:
Return ONLY a comma-separated list of strategy IDs (e.g., "ita_026,ita_002,ita_028,ita_047").
- Include ALL strategies with medium to high relevance
- Use full IDs with ita_ prefix
- No explanations, just the strategy IDs"""




def _debug_insights() -> bool:
    return (os.environ.get("DEBUG_INSIGHTS", "1") or "1").lower() in ("1", "true", "yes")


def _insights_max_completion_tokens() -> int:
    """Tight cap for GenOS v3 on insights — long completions are more likely to fail output risk screening."""
    try:
        v = int(os.environ.get("INSIGHTS_MAX_COMPLETION_TOKENS", "512").strip())
    except ValueError:
        v = 512
    return max(64, min(v, 8192))


def get_ita_strategy_insights(
    scenario_text: str,
    tax_calculation_result: str | None = None,
    *,
    data_model: dict[str, Any] | None = None,
    extracted_facts: dict[str, Any] | None = None,
    print_prompt: bool = False,
) -> list[str]:
    """
    Get ITA strategy IDs recommended for this scenario + tax data.

    With data_model: Tax situation Inputs / Tax calculated outputs from format_strategy_input_and_output
    (no duplicate free-text narrative — structured block is sufficient). Without data_model: narrative + tax calculation blob + optional Extracted facts.

    Returns a list of strategy IDs (e.g. ["ita_026", "ita_002", "ita_028"]).
    """
    loader = _get_loader()
    bulky = _insights_use_bulky_strategies()
    if bulky:
        strategies_list = loader.get_bulky_strategy_descriptions_for_insights(
            max_strategies=_insights_max_strategies(),
        )
        if not strategies_list.strip():
            strategies_list = _load_insights_strategies_compact()
            bulky = False
    else:
        strategies_list = _load_insights_strategies_compact()
        max_lines = _insights_max_strategy_lines()
        strategies_list = _truncate_strategy_block(strategies_list, max_lines)
    system_prompt = _build_ita_system_prompt(strategies_list, bulky=bulky)

    # # TEMP: hardcoded merged scenario (disabled — see `if False` block near top of this file)
    # user_prompt = (
    #     _INSIGHTS_USER_BODY_HARDCODED
    #     + "\n\nReturn applicable strategy IDs as comma-separated list (ita_ prefix)."
    # )

    tax_context = tax_calculation_result or ""

    facts_context = ""
    if not data_model and (scenario_text or tax_context):
        ext = extracted_facts or extract_facts_from_text(scenario_text + "\n" + tax_context)
        if ext:
            facts_context = f"\nExtracted: {json.dumps(ext, default=str)}"

    if data_model:
        blocks_dm: list[str] = []
        body = format_strategy_input_and_output(data_model)
        if body:
            blocks_dm.append(body)
        tax_context = "\n\n".join(blocks_dm) if blocks_dm else ""

    if data_model:
        user_prompt = f"""{tax_context}

Return applicable strategy IDs as comma-separated list (ita_ prefix)."""
    else:
        narrative_only = situation_narrative_text(scenario_text, None)
        blocks_else: list[str] = []
        if narrative_only:
            blocks_else.append(f"Taxpayer situation (description):\n{narrative_only}")
        blocks_else.append(f"Tax calculation result:\n{tax_context}")
        if facts_context.strip():
            blocks_else.append(facts_context.strip())
        user_prompt = "\n\n".join(blocks_else) + """

Return applicable strategy IDs as comma-separated list (ita_ prefix)."""

    debug = _debug_insights() or print_prompt
    if debug:
        print("\n" + "=" * 60 + " INSIGHTS PROMPT (system) " + "=" * 60, file=sys.stderr)
        print(system_prompt, file=sys.stderr)
        print("=" * 60 + " INSIGHTS PROMPT (user) " + "=" * 60, file=sys.stderr)
        print(user_prompt, file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    try:
        if debug:
            print("[DEBUG INSIGHTS] Calling ask_llm (GenOS/LLM)...", file=sys.stderr)
        # Temperature retries + optional second model when GenOS output screening fails on the primary model.
        cap = _insights_max_completion_tokens()
        response = None
        temps = (0.1, 0.2, 1.0)
        models = _insights_genos_model_chain()
        for mi, model_id in enumerate(models):
            if debug and mi == 0:
                print(
                    f"[DEBUG INSIGHTS] Models to try: {models}; current={model_id!r}",
                    file=sys.stderr,
                )
            for attempt, temp in enumerate(temps):
                try:
                    response = ask_llm(
                        user_prompt,
                        model=model_id,
                        system_prompt=system_prompt,
                        print_prompt=print_prompt,
                        temperature=temp,
                        max_completion_tokens=cap,
                    )
                    break
                except ValueError as e:
                    err_str = str(e).lower()
                    if ("422" in err_str or "suspicious" in err_str) and attempt < len(temps) - 1:
                        if debug:
                            print(
                                f"[DEBUG INSIGHTS] GenOS 422 (output screening); retrying temperature={temps[attempt + 1]} ...",
                                file=sys.stderr,
                            )
                        continue
                    if ("422" in err_str or "suspicious" in err_str) and mi < len(models) - 1:
                        if debug:
                            print(
                                f"[DEBUG INSIGHTS] GenOS 422 on model {model_id!r}; trying model {models[mi + 1]!r} ...",
                                file=sys.stderr,
                            )
                        break
                    raise
            if response is not None:
                break
        if response is None:
            raise ValueError("ITA insights: LLM returned no response")
        if debug:
            print("[DEBUG INSIGHTS] LLM response (len=%d):" % len(response), file=sys.stderr)
            print(repr(response[:500]) + ("..." if len(response) > 500 else ""), file=sys.stderr)
    except Exception as e:
        if debug:
            print(f"[DEBUG INSIGHTS] ask_llm EXCEPTION: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        return []

    parsed: list[str] = []
    for id_str in response.strip().split(","):
        id_str = id_str.strip()
        if not id_str:
            continue
        if id_str.isdigit():
            parsed.append(f"ita_{id_str.zfill(3)}")
        elif id_str.lower().startswith("ita_"):
            parsed.append(id_str)
        else:
            parsed.append(id_str)
    if debug:
        print(f"[DEBUG INSIGHTS] Parsed strategy IDs: {parsed}", file=sys.stderr)
        if not parsed and response.strip():
            print(f"[DEBUG INSIGHTS] WARNING: LLM returned non-empty response but parsed 0 IDs. Raw response (first 300 chars): {repr(response[:300])}", file=sys.stderr)
    return parsed


def get_ita_insights_with_strategies(
    scenario_text: str,
    tax_calculation_result: str | None = None,
    *,
    data_model: dict[str, Any] | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Get ITA insights as full strategy objects.
    Prefers data_model over tax_calculation_result when provided.
    Returns list of dicts with strategy_id, title, category, summary, etc.
    """
    ids = get_ita_strategy_insights(
        scenario_text,
        tax_calculation_result,
        data_model=data_model,
        **kwargs,
    )
    loader = _get_loader()
    result: list[dict[str, Any]] = []
    for sid in ids:
        s = loader.get_strategy(sid)
        if s:
            result.append(s)
    return result
