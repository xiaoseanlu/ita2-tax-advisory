"""
Strategy savings estimation for project-air.
Uses ita_insights.extract_facts_from_text + strategy_calculators to estimate
approximate savings for strategies that have calculators (from ita-tax-savings-ai).
"""

from __future__ import annotations

import os
import sys
from typing import Any

from tax_fact_extractor import extract_facts_from_data_model, extract_facts_from_text
from strategy_calculators import CALCULATORS, calculate_strategy_savings

DEFAULT_TAX_RATE = 0.24


def _estimate_marginal_rate(taxable_income: float) -> float:
    """Estimate marginal tax rate based on income (2025 brackets, simplified)."""
    if taxable_income <= 11_600:
        return 0.10
    if taxable_income <= 47_150:
        return 0.12
    if taxable_income <= 100_525:
        return 0.22
    if taxable_income <= 191_950:
        return 0.24
    if taxable_income <= 243_725:
        return 0.32
    if taxable_income <= 609_350:
        return 0.35
    return 0.37


def _get_default_inputs(strategy_id: str, facts: dict[str, Any], tax_rate: float) -> dict[str, Any]:
    """Build default calculator inputs from extracted facts."""
    income = facts.get("income", {})
    business = facts.get("business", {})
    personal = facts.get("personal", {})
    schedule_c = income.get("schedule_c_income") or 100000
    equipment = business.get("equipment_cost") or max(schedule_c * 0.10, 10000)
    children = personal.get("children") or 1

    defaults = {
        "ita_002": {"schedule_c_income": schedule_c, "comp_percentage": 40},
        "ita_010": {
            "total_days": 7,
            "business_days": 5,
            "transportation_cost": 1000,
            "daily_lodging_meals": 200,
            "tax_rate": tax_rate,
        },
        "ita_016": {
            "annual_medical_expenses": 10000,
            "include_se_tax": True,
            "tax_rate": tax_rate,
        },
        "ita_018": {"rental_days": 14, "daily_rate": 500, "tax_rate": tax_rate},
        "ita_020": {
            "num_children": max(1, children),
            "wages_per_child": 12000,
            "parent_tax_rate": tax_rate,
        },
        "ita_025": {
            "equipment_cost": int(equipment),
            "bonus_percentage": 100,
            "tax_rate": tax_rate,
            "schedule_c_income": schedule_c,
        },
        "ita_044": {
            "se_income": schedule_c,
            "employee_deferral": min(23500, schedule_c * 0.25),
            "employer_contribution": min(schedule_c * 0.20, 20000),
            "tax_rate": tax_rate,
        },
    }
    base = defaults.get(strategy_id, {})
    return {k: v for k, v in base.items()}


def estimate_savings_for_strategy(
    strategy_id: str,
    scenario_text: str,
    tax_result: str,
    *,
    data_model: dict | None = None,
) -> dict[str, Any] | None:
    """
    Estimate approximate savings for a strategy using extracted facts and its calculator.
    Prefers data_model over tax_result when provided.
    Returns dict with savings, min, max, description, input_defaults; or None if no calculator.
    """
    if strategy_id not in CALCULATORS:
        return None

    if data_model:
        facts = extract_facts_from_data_model(data_model)
    else:
        facts = extract_facts_from_text(scenario_text + "\n" + tax_result)
    income = facts.get("income", {})
    total_income = (income.get("w2_income") or 0) + (income.get("schedule_c_income") or 0)
    tax_rate = _estimate_marginal_rate(total_income) if total_income > 0 else DEFAULT_TAX_RATE

    inputs = _get_default_inputs(strategy_id, facts, tax_rate)
    result = calculate_strategy_savings(strategy_id, inputs)
    if "error" in result or result.get("savings", 0) == 0:
        return None

    savings = result["savings"]
    if isinstance(savings, (int, float)):
        s_min = int(savings * 0.85)
        s_max = int(savings * 1.15)
    else:
        s_min = s_max = 0

    return {
        "savings": int(savings),
        "min": max(0, s_min),
        "max": s_max,
        "description": "Approximate annual savings",
        "input_defaults": inputs,
    }


def _debug_insights() -> bool:
    return (os.environ.get("DEBUG_INSIGHTS", "1") or "1").lower() in ("1", "true", "yes")


def enrich_strategies_with_savings(
    strategies: list[dict[str, Any]],
    scenario_text: str,
    tax_result: str,
    *,
    data_model: dict | None = None,
) -> list[dict[str, Any]]:
    """Add estimated_savings to each strategy that has a calculator."""
    if _debug_insights():
        print(f"[DEBUG INSIGHTS] enrich_strategies_with_savings: {len(strategies)} strategies", file=sys.stderr)
    for st in strategies:
        sid = st.get("strategy_id", "")
        if not sid:
            continue
        est = estimate_savings_for_strategy(
            sid, scenario_text, tax_result, data_model=data_model
        )
        if est:
            st["estimated_savings"] = est
    return strategies
