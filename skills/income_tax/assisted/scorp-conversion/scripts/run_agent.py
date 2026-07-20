#!/usr/bin/env python3
"""
Orchestrate S-Corp Skill loop: Tool ↔ LLM ↔ Tool.

Steps:
  1) (optional LLM) extract activity fields from scenario text
  2) Tool assess_applicability
  3) (optional LLM) wage diligence / confirm
  4) Tool apply_scorp_conversion
  5) (optional LLM) explain results

Examples:
  python3 run_agent.py --tool-only --example
  python3 run_agent.py --net-income 120000 --reasonable-wage 70000 --with-llm
  python3 run_agent.py --scenario-file ../../../../../Tax\\ situations.txt --reasonable-wage 65000 --with-llm
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # project-air
SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))
sys.path.insert(0, str(ROOT))

from tools.scorp_conversion import (  # noqa: E402
    BusinessActivityInput,
    RatesInput,
    apply_scorp_conversion,
    assess_applicability,
    ApplyScorpInput,
)


EXAMPLE_ACTIVITY = BusinessActivityInput(
    activity_id="schc-1",
    source="Schedule C",
    name="Consulting LLC",
    net_income=120_000,
    is_se_biz=True,
    ownership_pct=100,
    prefix=1,
)


def _ask_llm(system: str, user: str) -> str:
    """Call project-air GenOS chat helper when available."""
    try:
        from genai_tax_core import ask_llm_chat  # type: ignore
    except Exception as e:
        return f"[LLM unavailable: {e}]"

    # Prefer a lightweight chat/completions style if responses API is heavy
    try:
        from genai_tax_core import ask_llm  # type: ignore

        return ask_llm(user, system_prompt=system)
    except Exception:
        try:
            return ask_llm_chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
            )
        except TypeError:
            # Signature may differ; last resort
            return ask_llm_chat(user)


def llm_extract_activity(scenario_text: str) -> dict:
    system = (
        "You extract Schedule C / SE business facts for an S-Corp conversion tool. "
        "Return ONLY compact JSON with keys: activity_id, source, name, net_income, "
        "is_se_biz, ownership_pct, prefix, taxpayer_spouse_or_joint. "
        "Use null for unknown numbers. Never invent net_income."
    )
    user = f"Scenario:\n{scenario_text}\n\nJSON:"
    raw = _ask_llm(system, user)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"_raw": raw, "_parse_error": True}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"_raw": raw, "_parse_error": True}


def llm_wage_diligence(activity: BusinessActivityInput, appl: dict) -> str:
    system = (
        "You are a tax advisory assistant. Reasonable S-Corp compensation is "
        "advisor-determined; you must NOT pick a final wage. Ask diligence questions "
        "and optionally give an ILLUSTRATIVE range labeled as non-authoritative."
    )
    user = (
        f"Activity: {activity.name} ({activity.source}), net_income={activity.net_income}, "
        f"net_earnings≈{appl.get('net_earnings')}, ownership={activity.ownership_pct}%.\n"
        "Provide: (1) 3–5 diligence questions, (2) optional illustrative wage range with caveats, "
        "(3) a one-line reminder that the advisor must confirm a number before apply."
    )
    return _ask_llm(system, user)


def llm_explain(result: dict) -> str:
    system = (
        "Explain S-Corp conversion Tool results to a tax advisor. "
        "Use ONLY numbers from the JSON. Do not recalculate or invent savings."
    )
    user = json.dumps(result, indent=2)
    return _ask_llm(system, user)


def build_activity(args: argparse.Namespace, scenario_text: str | None) -> BusinessActivityInput:
    if args.example and not args.net_income:
        return EXAMPLE_ACTIVITY

    extracted = {}
    if scenario_text and args.with_llm:
        extracted = llm_extract_activity(scenario_text)
        print("=== LLM extract ===")
        print(json.dumps(extracted, indent=2))
        print()

    net_income = args.net_income
    if net_income is None and isinstance(extracted.get("net_income"), (int, float)):
        net_income = float(extracted["net_income"])
    if net_income is None:
        raise SystemExit(
            "net_income required (pass --net-income or provide scenario + --with-llm that yields it)."
        )

    if args.is_se_biz is not None:
        is_se = bool(args.is_se_biz)
    elif extracted.get("is_se_biz") is not None:
        is_se = bool(extracted["is_se_biz"])
    else:
        is_se = True

    return BusinessActivityInput(
        activity_id=str(
            args.activity_id
            or extracted.get("activity_id")
            or "schc-1"
        ),
        source=str(args.source or extracted.get("source") or "Schedule C"),
        name=str(args.name or extracted.get("name") or "SE business"),
        net_income=float(net_income),
        is_se_biz=is_se,
        ownership_pct=float(
            args.ownership_pct
            if args.ownership_pct is not None
            else extracted.get("ownership_pct") or 100
        ),
        prefix=int(args.prefix or extracted.get("prefix") or 1),
        taxpayer_spouse_or_joint=str(
            args.tp_sp_jt
            or extracted.get("taxpayer_spouse_or_joint")
            or "taxpayer"
        ),
    )


def main() -> int:
    p = argparse.ArgumentParser(description="S-Corp conversion Skill runner (Tool + optional LLM)")
    p.add_argument("--example", action="store_true", help="Use sample Sch C $120k activity")
    p.add_argument("--tool-only", action="store_true", help="Skip all LLM calls")
    p.add_argument("--with-llm", action="store_true", help="Enable GenOS LLM mid-loop")
    p.add_argument("--scenario-file", type=Path, help="Scenario text to extract from")
    p.add_argument("--net-income", type=float)
    p.add_argument("--reasonable-wage", type=float, help="Confirmed wage (required to apply)")
    p.add_argument("--activity-id", type=str)
    p.add_argument("--source", type=str, default=None)
    p.add_argument("--name", type=str, default=None)
    p.add_argument("--ownership-pct", type=float, default=None)
    p.add_argument("--prefix", type=int, default=None)
    p.add_argument("--tp-sp-jt", type=str, default=None)
    p.add_argument("--is-se-biz", type=lambda x: x.lower() != "false", default=None)
    p.add_argument("--fed-rate", type=float, default=24.0)
    p.add_argument("--state-rate", type=float, default=0.0)
    p.add_argument("--assess-only", action="store_true")
    args = p.parse_args()

    if args.with_llm and args.tool_only:
        print("Pick one of --with-llm or --tool-only", file=sys.stderr)
        return 2

    scenario_text = None
    if args.scenario_file:
        scenario_text = args.scenario_file.read_text(errors="ignore")

    activity = build_activity(args, scenario_text)
    rates = RatesInput(
        federal_marginal_rate_pct=args.fed_rate,
        state_marginal_rate_pct=args.state_rate,
    )

    appl = assess_applicability(activity, rates)
    print("=== Part 1 Tool: assess_scorp_applicability ===")
    print(json.dumps(appl.to_dict(), indent=2))
    print()

    if args.assess_only:
        return 0 if appl.applicable else 1

    if args.with_llm and not args.tool_only:
        print("=== Optional LLM: wage diligence (not required for core path) ===")
        print(llm_wage_diligence(activity, appl.to_dict()))
        print()

    if args.reasonable_wage is None:
        print(
            "Stopped before Part 2: pass --reasonable-wage <confirmed amount>.\n"
            "Core Skill does not use LLM to invent a wage.",
            file=sys.stderr,
        )
        return 3

    result = apply_scorp_conversion(
        ApplyScorpInput(
            activity=activity,
            reasonable_wage=args.reasonable_wage,
            rates=rates,
            tax_year=2026,
        )
    )
    out = result.to_dict()
    print("=== Part 2 Tool: estimate_scorp_savings ===")
    print(json.dumps(out, indent=2))
    print()

    if args.with_llm and not args.tool_only and result.ok:
        print("=== Optional LLM: explain (not required for core path) ===")
        print(llm_explain(out))
        print()

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
