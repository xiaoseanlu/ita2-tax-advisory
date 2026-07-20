"""
Tax fact extraction and formatting utilities.

Responsible for:
- Extracting structured facts from data_model JSON or free-text scenarios
- Formatting tax situation + calculated outputs into labeled text blocks for LLM prompts
- Generating Schedule C guard lines that prevent false-positive strategy recommendations
"""
from __future__ import annotations

import re
from typing import Any


def normalize_tax_situation(ts: dict[str, Any] | None) -> dict[str, Any]:
    """
    Flatten grouped tax_situation (personal / income / …) to the legacy top-level shape
    used by extractors and prompts. Legacy flat objects are returned unchanged.
    """
    if not isinstance(ts, dict):
        return {}
    personal = ts.get("personal")
    if not isinstance(personal, dict):
        return ts
    out: dict[str, Any] = {}
    for k in ("tax_year", "filing_status", "primary_taxpayer", "spouse", "dependents"):
        if k in personal:
            out[k] = personal[k]
    out["income"] = dict(ts.get("income") or {})
    out["itemized_deductions"] = dict(ts.get("itemized_deductions") or {})
    pay = ts.get("payments") or {}
    if isinstance(pay, dict):
        out["payments"] = pay
        wh, dh = pay.get("wages_withholding"), pay.get("dividend_withholding")
        if wh is not None:
            out["income"]["wages_withholding"] = wh
        if dh is not None:
            out["income"]["dividend_withholding"] = dh
    cred = ts.get("credits")
    if isinstance(cred, list):
        out["credits_mentioned"] = cred
    elif isinstance(ts.get("credits_mentioned"), list):
        out["credits_mentioned"] = ts["credits_mentioned"]
    return out


def extract_facts_from_data_model(data_model: dict[str, Any]) -> dict[str, Any]:
    """Extract structured facts from a data_model dict (compatible with extract_facts_from_text output)."""
    facts: dict[str, Any] = {
        "income": {"w2_income": None, "schedule_c_income": None},
        "business": {"equipment_cost": None, "miles": None, "entity_type": None},
        "personal": {"children": None, "child_ages": [], "spouse_employed": None},
    }
    ts = normalize_tax_situation(data_model.get("tax_situation") or {})
    inc = ts.get("income") or {}
    calc = data_model.get("form_1040_calculated_lines") or {}

    w = inc.get("wages")
    if w is not None:
        facts["income"]["w2_income"] = float(w)

    sc = calc.get("schedule_c_net_profit_or_loss")
    if sc is None:
        gr = inc.get("schedule_c_gross_receipts")
        exp = inc.get("schedule_c_expenses")
        if gr is not None:
            sc = float(gr) - float(exp or 0)
    if sc is not None:
        facts["income"]["schedule_c_income"] = float(sc)

    assets = inc.get("depreciable_assets") or []
    if assets:
        facts["business"]["equipment_cost"] = sum(float(a.get("basis", 0)) for a in assets)

    dep = ts.get("dependents") or []
    if dep:
        facts["personal"]["children"] = len(dep)

    return facts


def extract_facts_from_text(text: str) -> dict[str, Any]:
    """Extract structured facts from free-text scenario/calculation (regex heuristics)."""
    facts: dict[str, Any] = {
        "income": {"w2_income": None, "schedule_c_income": None},
        "business": {"equipment_cost": None, "miles": None, "entity_type": None},
        "personal": {"children": None, "child_ages": [], "spouse_employed": None},
    }

    def parse_amount(match_text: str, raw: str) -> float:
        raw = raw.replace(",", "")
        if "K" in match_text.upper():
            return float(raw) * 1000
        return float(raw)

    for pattern in [
        r"Schedule\s+C\s+(?:income|business)[^\$]*\$?([\d,]+)K?",
        r"\$?([\d,]+)K?\s+(?:in|of|from)?\s*Schedule\s+C",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                facts["income"]["schedule_c_income"] = parse_amount(m.group(0), m.group(1))
            except (ValueError, IndexError):
                pass
            break

    for pattern in [
        r"W-?2\s+(?:income|wages)[^\$]*\$?([\d,]+)K?",
        r"\$?([\d,]+)K?\s+(?:in\s+)?(?:W-?2|wage)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                facts["income"]["w2_income"] = parse_amount(m.group(0), m.group(1))
            except (ValueError, IndexError):
                pass
            break

    m = re.search(r"equipment[^\$]*\$?([\d,]+)K?", text, re.IGNORECASE)
    if m:
        try:
            facts["business"]["equipment_cost"] = parse_amount(m.group(0), m.group(1))
        except (ValueError, IndexError):
            pass

    m = re.search(r"(\d+)\s*(?:qualifying\s+)?(?:child|children)", text, re.IGNORECASE)
    if m:
        try:
            facts["personal"]["children"] = int(m.group(1))
        except (ValueError, IndexError):
            pass

    return facts


def situation_narrative_text(scenario_text: str, data_model: dict[str, Any] | None) -> str:
    """
    Resolve free-text taxpayer narrative: prefers scenario_text, falls back to
    string fields on data_model when only JSON is available.
    """
    s = (scenario_text or "").strip()
    if s:
        return s
    if not data_model:
        return ""
    for key in ("taxpayer_situation_description", "scenario_description", "original_tax_situation_text"):
        v = data_model.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    ts = normalize_tax_situation(data_model.get("tax_situation") or {})
    for key in ("description", "narrative", "situation_summary"):
        v = ts.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def schedule_c_loss_guard_line(schedule_c_net: float | None) -> str | None:
    """
    Returns a user-message guard line when Schedule C is zero or a loss.
    Reduces false-positive strategy recommendations driven by narrative text.
    Returns None when Schedule C is a profit (or unknown).
    """
    if schedule_c_net is None or schedule_c_net > 0:
        return None
    return (
        "Schedule C selection note (modeled net is zero or a loss): "
        "Omit strategies that require Schedule C profit, positive QBI from this activity, "
        "or net self-employment earnings from it (ita_002, ita_028, ita_029, ita_043, ita_044, ita_020, ita_021; "
        "ita_004 only if another pass-through shows profit). "
        "ita_025 and ita_026 may still apply when depreciable assets are in play. "
        "If narrative detail conflicts with the Schedule C net line above, follow the Schedule C net line."
    )


def schedule_c_profit_note_line(schedule_c_net: float | None) -> str | None:
    """
    Returns a parallel note line when Schedule C is a profit.
    Keeps the prompt shape consistent with loss runs (aids GenOS output screening).
    Returns None when Schedule C is zero, a loss, or unknown.
    """
    if schedule_c_net is None or schedule_c_net <= 0:
        return None
    return (
        "Schedule C selection note (modeled net is a profit): "
        "Entity, QBI, and self-employment retirement strategies may apply when they match the inputs above. "
        "If narrative detail conflicts with the Schedule C or QBI lines, follow the modeled lines."
    )


def format_strategy_input_and_output(data_model: dict[str, Any]) -> str:
    """
    Flatten tax_situation + form_1040_calculated_lines into labeled text blocks
    for use in insights LLM prompts and debugging.

    Returns two sections: "Tax situation Inputs" and "Tax calculated outputs",
    with a Schedule C guard line appended when applicable.
    """
    input_lines: list[str] = []
    output_lines: list[str] = []
    ts = normalize_tax_situation(data_model.get("tax_situation") or {})
    calc = data_model.get("form_1040_calculated_lines") or {}

    def add(lines_list: list[str], label: str, val: Any) -> None:
        if val is not None and val != "" and val != []:
            lines_list.append(f"{label}: {val}")

    add(input_lines, "Tax year", ts.get("tax_year"))
    add(input_lines, "Filing status", ts.get("filing_status"))

    prim = ts.get("primary_taxpayer") or {}
    sp = ts.get("spouse")
    if prim.get("age_65_or_older"):
        input_lines.append("Taxpayer: age 65+")
    if prim.get("age_70_5_or_older"):
        input_lines.append("Taxpayer: age 70.5+")
    if sp and sp.get("age_65_or_older"):
        input_lines.append("Spouse: age 65+")
    if sp and sp.get("age_70_5_or_older"):
        input_lines.append("Spouse: age 70.5+")

    dep = ts.get("dependents") or []
    if dep:
        n_under_17 = sum(1 for d in dep if d.get("qualifying_child_under_17"))
        input_lines.append(
            f"Dependents: {len(dep)}"
            + (f" (qualifying child under 17: {n_under_17})" if n_under_17 else "")
        )

    inc = ts.get("income") or {}
    w = inc.get("wages")
    if w is not None and w != 0:
        input_lines.append(f"Wages: {w}")

    # Schedule C net: prefer calculated line, derive from gross receipts − expenses as fallback
    schedule_c_net: float | None = None
    sc = calc.get("schedule_c_net_profit_or_loss")
    if sc is None:
        gr = inc.get("schedule_c_gross_receipts")
        exp = inc.get("schedule_c_expenses")
        if gr is not None:
            sc = float(gr) - float(exp or 0)
    if sc is not None:
        schedule_c_net = float(sc)
    if sc is not None and sc != 0:
        input_lines.append(f"Schedule C net: {sc}")

    if inc.get("rental_income") is not None and inc.get("rental_income") != 0:
        input_lines.append(f"Schedule E rental: {inc.get('rental_income')}")

    for k in [
        "ordinary_dividends", "qualified_dividends", "taxable_interest",
        "taxable_pensions", "short_term_capital_gain_loss", "long_term_capital_gains",
        "other_income",
    ]:
        v = inc.get(k)
        if v is not None and v != 0:
            input_lines.append(f"{k}: {v}")

    assets = inc.get("depreciable_assets") or []
    for i, a in enumerate(assets):
        input_lines.append(f"Asset {i+1}: basis={a.get('basis')}, recovery={a.get('recovery_period_years')}yr")

    item = ts.get("itemized_deductions") or {}
    for k, v in item.items():
        if isinstance(v, (int, float)) and v != 0:
            input_lines.append(f"Itemized.{k}: {v}")

    add(output_lines, "AGI", calc.get("adjusted_gross_income"))
    add(output_lines, "MAGI", calc.get("magi"))
    add(output_lines, "Taxable income", calc.get("taxable_income"))
    add(output_lines, "Schedule C net", calc.get("schedule_c_net_profit_or_loss"))
    add(output_lines, "QBI deduction", calc.get("qbi_deduction"))
    add(output_lines, "Deduction", calc.get("standard_or_itemized_deduction_used"))
    add(output_lines, "Deduction amount", calc.get("deduction_amount"))
    add(output_lines, "Total tax", calc.get("total_tax_liability"))
    add(output_lines, "SE tax", calc.get("self_employment_tax"))

    parts: list[str] = []
    if input_lines:
        parts.append("Tax situation Inputs:\n" + "\n".join(input_lines))
    if output_lines:
        parts.append("Tax calculated outputs:\n" + "\n".join(output_lines))
    body = "\n\n".join(parts) if parts else ""

    guard = schedule_c_loss_guard_line(schedule_c_net) or schedule_c_profit_note_line(schedule_c_net)
    if guard and body:
        body = body + "\n\n" + guard

    return body


def format_data_model_for_insights(data_model: dict[str, Any]) -> str:
    """Alias for format_strategy_input_and_output (kept for backward compatibility)."""
    return format_strategy_input_and_output(data_model)
