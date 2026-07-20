"""
Tax calculation CLI and two-step flow. Uses:
  - tax_situations.txt + tax_situations_loader: get scenario by id for regressions/single-shot.
  - genai_tax_core: single-shot get_tax_calculation_response(description) -> LLM blob; ask_llm for two-step.
  - tax_schema_filler: fill_tax_data_model(blob, original_text) -> dict for data model.
See FLOW.md for diagram.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from genai_tax_core import (
    ask_llm,
    genos_available as _genos_available,
    genos_has_credentials as _genos_has_credentials,
    get_resolved_genos_llm_line,
    get_supported_models,
    get_tax_calculation_response,
    use_genos_v3 as _use_genos_v3,
)
from tax_situations_loader import get_scenario_by_id, list_scenario_ids

try:
    from calc_total_tax import (
        get_tax_reference_text,
        get_tax_reference_text_all,
        get_standard_deduction_tool_result,
    )
except ImportError:
    get_tax_reference_text = None  # type: ignore[assignment]
    get_tax_reference_text_all = None  # type: ignore[assignment]
    get_standard_deduction_tool_result = None  # type: ignore[assignment]

_root = Path(__file__).resolve().parent

# --- Two-step flow: first get AGI (drives deduction phase-out, QBI, credits), then full tax ---

AGI_EXTRACTION_PROMPT = """From the tax scenario below, determine the taxpayer's Adjusted Gross Income (AGI).
Include any above-the-line deductions (e.g. 1/2 SE tax, SE health insurance) so the result is true AGI.
If MAGI differs from AGI for this scenario, you may also state MAGI.

Respond with exactly these lines (use the numbers you calculate):
AGI: $<number>
MAGI: $<number>   (optional; if same as AGI you can omit or repeat AGI)

Use only digits and one optional decimal point in the amount (no commas). Example: AGI: $631576"""


def parse_agi_from_response(response: str) -> tuple[float | None, float | None]:
    """
    Parse AGI and optionally MAGI from an LLM response. Looks for lines like "AGI: $631576" or "AGI: 631576".
    Returns (agi, magi). magi defaults to agi if not found.
    """
    agi_val: float | None = None
    magi_val: float | None = None
    # Match "AGI: $123" or "AGI: 123" or "AGI: 123,456" or "AGI: $123456.00"
    for label in ("AGI", "MAGI"):
        pattern = rf"{label}\s*:\s*\$?([\d,]+(?:\.\d+)?)"
        m = re.search(pattern, response, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if label.upper() == "AGI":
                    agi_val = val
                else:
                    magi_val = val
            except ValueError:
                pass
    if magi_val is None and agi_val is not None:
        magi_val = agi_val
    return agi_val, magi_val


def get_agi_from_scenario(
    scenario_text: str,
    *,
    year: int = 2024,
    model: str | None = None,
    print_prompt: bool = False,
) -> tuple[float | None, float | None, str]:
    """
    Step 1 of two-step flow: ask the LLM to compute AGI (and MAGI) from the scenario.
    Returns (agi, magi, raw_response). agi/magi are None if parsing failed.
    """
    prompt = f"""Tax year: {year}.

{AGI_EXTRACTION_PROMPT}

---
Scenario:
{scenario_text}"""
    raw = ask_llm(prompt, model=model, print_prompt=print_prompt)
    agi, magi = parse_agi_from_response(raw)
    return agi, magi, raw


def get_agi_then_tax_answer(
    scenario_text: str,
    *,
    raw_prompt: str | None = None,
    year: int = 2024,
    filing_status: str = "Married Filing Jointly",
    filer_65: bool = True,
    spouse_65: bool = True,
    reference_filer_blind: bool = False,
    reference_spouse_blind: bool = False,
    include_reference: bool = True,
    model: str | None = None,
    two_step_agi_override: float | None = None,
    print_prompt: bool = False,
) -> tuple[str, float | None, float | None]:
    """
    Two-step flow: (1) get AGI from the scenario via LLM; (2) build reference with that AGI
    and run full tax prompt. AGI drives standard deduction phase-out (2025+ senior bonus), QBI
    phase-out, and most credits.

    If two_step_agi_override is set, skip step 1 and use this value as AGI/MAGI for the reference.

    Returns (full_tax_response, agi_used, magi_used).
    """
    if two_step_agi_override is not None:
        agi = magi = two_step_agi_override
        step1_response = ""
    else:
        agi, magi, step1_response = get_agi_from_scenario(
            scenario_text, year=year, model=model, print_prompt=print_prompt
        )
        if agi is None:
            agi = magi = 0.0  # fallback so reference still builds
    # Build the full tax prompt with universal reference (no parsed year/status)
    prompt_for_step2 = build_tax_prompt(
        raw_prompt=raw_prompt or scenario_text,
        include_reference=include_reference,
    )
    # Optionally inject "Use AGI from step 1" so the model doesn't contradict
    if agi is not None and agi > 0:
        prompt_for_step2 = (
            f"Use AGI = ${agi:,.0f} (and MAGI = ${(magi or agi):,.0f} if relevant) from the prior AGI determination.\n\n"
            + prompt_for_step2
        )
    step2_response = ask_llm(prompt_for_step2, model=model, print_prompt=print_prompt)
    return step2_response, agi, magi


# Default prompt: scenario + short instructions (no second example scenario to avoid confusing the LLM).
DEFAULT_TAX_PROMPT = r"""Calculate the tax liability for this tax situation.

--- Scenario (use only this case) ---

Married Filing Jointly, tax year 2024.
Tax Filer John Anderson, PA, DOB 01/01/1984. 
Spouse: Anne Anderson, DOB 01/01/1984. 
Two dependents - Kellie Anderson (Daughter), Devon Anderson (Sister); both DOB 01/01/2020, type 1, claimed. 
Taxpayer wage Tester Cleaning Equipment, Inc. $200,000 federal wages, $15,000 federal withholding; 
Taxpayer's business: “John Anderson,” $64,000 gross sales, subject to SE tax, QBI qualify yes. 
SALT $4,083, real estate tax $22,000, mortgage interest $32,000; no medical, no contributions. 
No dividends, interest, pensions, or capital gains in this payload.

"""


def build_tax_prompt(
    raw_prompt: str | None = None,
    year: int = 2024,
    filing_status: str = "Married Filing Jointly",
    wages: float = 0,
    ordinary_dividends: float = 0,
    qualified_dividends: float = 0,
    taxable_interest: float = 0,
    taxable_pensions: float = 0,
    st_capital_gain: float = 0,
    lt_capital_gains: float = 0,
    rental_income: float = 0,
    standard_deduction: float | None = None,
    filer_65: bool = False,
    spouse_65: bool = False,
    nonrefundable_credits: float = 0,
    withholding: float = 0,
    extra_instructions: str = "",
    include_reference: bool = True,
    reference_year: int = 2024,
    reference_filing_status: str = "Married Filing Jointly",
    reference_magi: float = 0,
    reference_filer_65: bool = True,
    reference_filer_blind: bool = False,
    reference_spouse_65: bool = True,
    reference_spouse_blind: bool = False,
    **kwargs: Any,
) -> str:
    """Build a tax prompt. If raw_prompt is provided, return it as-is (optionally + extra_instructions).

    Reference injection: When include_reference is True and raw_prompt is provided, we prepend
    get_tax_reference_text_all() so the LLM sees thresholds for all years and filing statuses
    and is told to use the tax year and filing status from the scenario (no parsing)."""
    if raw_prompt is not None:
        out = raw_prompt
        if include_reference and get_tax_reference_text_all is not None:
            ref = get_tax_reference_text_all()
            out = ref + "\n\n---\n\n" + out
        if extra_instructions:
            out = out.rstrip() + "\n\n" + extra_instructions
        return out
    # Structured path: we have income fields, so we can compute AGI for the deduction tool (2025+ senior bonus).
    ref_magi = reference_magi
    if include_reference and get_tax_reference_text is not None:
        if ref_magi == 0 and year >= 2025:
            ref_magi = (
                wages + ordinary_dividends + taxable_interest + taxable_pensions
                + st_capital_gain + lt_capital_gains + rental_income
                + float(kwargs.get("other_ordinary_income", 0))
            )
        ref = get_tax_reference_text(
            year,
            filing_status,
            magi=ref_magi,
            filer_65=filer_65,
            filer_blind=kwargs.get("filer_blind", False),
            spouse_65=spouse_65,
            spouse_blind=kwargs.get("spouse_blind", False),
        )
        ref_block = ref + "\n\n---\n\n"
    else:
        ref_block = ""
    lines = [
        f"Calculate federal income tax for the following scenario. Use {year} IRS rules.",
        f"Filing status: {filing_status}.",
        "",
        "Income:",
        f"  Wages: ${wages:,.0f}" if wages else None,
        f"  Ordinary dividends: ${ordinary_dividends:,.0f} (qualified: ${qualified_dividends:,.0f})" if ordinary_dividends else None,
        f"  Taxable interest: ${taxable_interest:,.0f}" if taxable_interest else None,
        f"  Taxable pensions: ${taxable_pensions:,.0f}" if taxable_pensions else None,
        f"  Short-term capital gain: ${st_capital_gain:,.0f}" if st_capital_gain else None,
        f"  Long-term capital gains: ${lt_capital_gains:,.0f}" if lt_capital_gains else None,
        f"  Rental income: ${rental_income:,.0f}" if rental_income else None,
        "",
        "Other:",
        f"  Use standard deduction (filer 65+: {filer_65}, spouse 65+: {spouse_65})." if standard_deduction is None else f"  Standard deduction: ${standard_deduction:,.0f}.",
        f"  Nonrefundable credits: ${nonrefundable_credits:,.0f}" if nonrefundable_credits else None,
        f"  Withholding: ${withholding:,.0f}" if withholding else None,
        "",
        "Instructions:",
        "Use the correct ordinary income brackets and capital gains rates for the year and filing status. "
        "Include NIIT if MAGI exceeds the threshold. "
        "Show: AGI, taxable income, tax on ordinary income, tax on preferential income (LTCG/qualified dividends), regular tax, NIIT, total before credits, credits, total after credits, and amount owed/refund.",
        "",
    ]
    if extra_instructions:
        lines.append(extra_instructions)
        lines.append("")
    body = "\n".join(l for l in lines if l is not None)
    return ref_block + body


def get_tax_llm_answer(
    prompt: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Get a tax answer from GenOS (requires GenOS + Intuit credentials in `.env`).

    Pass either:
      - prompt: a raw string prompt, or
      - keyword arguments for build_tax_prompt() to build the prompt for you.

    Returns the model's full text response.
    """
    if prompt is None:
        prompt = build_tax_prompt(**kwargs)
    return ask_llm(prompt)


if __name__ == "__main__":
    _extract_env = _root.parent / "tax-advisory-toolkit" / "tools" / "1040Extract" / "tests" / ".env"
    if len(sys.argv) > 1 and sys.argv[1] == "--check-env":
        print("LLM config check:")
        print(" ", get_resolved_genos_llm_line())
        print("  GenOS (genosclient + GENOS_EXPERIENCE_ID):", _genos_available())
        print("  GenOS v3 (GENOS_USE_V3=1):", _use_genos_v3())
        print("  GenOS credentials (INTUIT_APP_ID, INTUIT_APP_SECRET, etc.):", "set" if _genos_has_credentials() else "not set")
        print("  .env loaded from (script dir):", _root / ".env", "exists:", (_root / ".env").exists())
        print("  1040Extract .env path:", _extract_env, "exists:", _extract_env.exists())
        if not _genos_has_credentials():
            print("  → Add INTUIT_APP_ID and INTUIT_APP_SECRET to .env for GenOS to work.")
        if _use_genos_v3():
            print("  → Using v3 API; GENOS_MODEL_ID (e.g. gpt-5.4-2026-03-05) is used as-is.")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--list-models":
        models = get_supported_models()
        if not models:
            print("No models returned. Set GENOS_* and Intuit credentials in .env (see .env.example).")
            sys.exit(1)
        print("Available models (from GenOS; GENOS_MODEL_ID in .env selects the default):")
        for m in sorted(models):
            print(f"  {m}")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--list-scenarios":
        ids = list_scenario_ids()
        print("Scenario ids in tax_situations.txt:", ids if ids else "(none or file missing)")
        sys.exit(0)

    two_step = "--two-step" in sys.argv
    print_prompt = "--print-prompt" in sys.argv
    fill_schema = "--fill-schema" in sys.argv
    ita_insights = "--ita-insights" in sys.argv
    prompt_only = "--prompt-only" in sys.argv
    argv = [a for a in sys.argv[1:] if a not in ("--two-step", "--print-prompt", "--fill-schema", "--ita-insights", "--prompt-only")]
    scenario_id = argv[0] if argv else "default"
    scenario_text = get_scenario_by_id(scenario_id)
    if scenario_text is None:
        scenario_text = DEFAULT_TAX_PROMPT
        if argv and argv[0] != "default":
            print(f"Scenario id {scenario_id!r} not found; using default.\n", file=sys.stderr)

    if not prompt_only:
        print(get_resolved_genos_llm_line(), file=sys.stderr)

    if prompt_only:
        prompt = build_tax_prompt(raw_prompt=scenario_text, include_reference=True)
        print(prompt)
        sys.exit(0)

    if two_step and _genos_available():
        try:
            print("Mode: two-step (2 LLM calls: AGI first, then full tax)\n")
            print("=== Step 1: AGI (drives deduction phase-out, QBI, credits) ===\n")
            step2_answer, agi_used, magi_used = get_agi_then_tax_answer(
                scenario_text,
                raw_prompt=scenario_text,
                print_prompt=print_prompt,
            )
            if agi_used is not None:
                print(f"AGI (used for reference deduction): ${agi_used:,.0f}")
            if magi_used is not None and magi_used != agi_used:
                print(f"MAGI: ${magi_used:,.0f}")
            print("\n=== Step 2: Full tax calculation (using AGI above) ===\n")
            print(step2_answer)
            if ita_insights:
                try:
                    from ita_insights import get_ita_insights_with_strategies
                    strategies = get_ita_insights_with_strategies(
                        scenario_text, step2_answer, print_prompt=print_prompt
                    )
                    print("\n" + "=" * 60 + " ITA STRATEGY INSIGHTS " + "=" * 60, file=sys.stderr)
                    print(f"Recommended strategies: {[s['strategy_id'] for s in strategies]}", file=sys.stderr)
                    for s in strategies:
                        print(f"  • {s['strategy_id']}: {s.get('title', '')}", file=sys.stderr)
                except Exception as e:
                    print(f"ITA insights failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Single-shot: core library returns full LLM blob
    if _genos_available():
        try:
            print("Mode: single prompt (1 LLM call). Scenario id:", scenario_id, file=sys.stderr)
            if fill_schema:
                print("Will fill tax data model schema after response.\n", file=sys.stderr)
            answer = get_tax_calculation_response(
                scenario_text,
                include_reference=True,
                print_prompt=print_prompt,
            )
            print(answer)
            if ita_insights:
                try:
                    from ita_insights import get_ita_insights_with_strategies
                    strategies = get_ita_insights_with_strategies(
                        scenario_text, answer, print_prompt=print_prompt
                    )
                    print("\n" + "=" * 60 + " ITA STRATEGY INSIGHTS " + "=" * 60, file=sys.stderr)
                    print(f"Recommended strategies: {[s['strategy_id'] for s in strategies]}", file=sys.stderr)
                    for s in strategies:
                        print(f"  • {s['strategy_id']}: {s.get('title', '')}", file=sys.stderr)
                except Exception as e:
                    print(f"ITA insights failed: {e}", file=sys.stderr)
            if fill_schema:
                from tax_schema_filler import fill_tax_data_model
                filled = fill_tax_data_model(answer, scenario_text, print_prompt=print_prompt)
                print("\n" + "=" * 60 + " FILLED TAX DATA MODEL " + "=" * 60, file=sys.stderr)
                print(json.dumps(filled, indent=2))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        prompt = build_tax_prompt(raw_prompt=scenario_text, include_reference=True)
        print(prompt)
        print()
        print("Set INTUIT_APP_ID and INTUIT_APP_SECRET in .env (with GENOS_EXPERIENCE_ID) to get a response.")
