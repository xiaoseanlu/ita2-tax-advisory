#!/usr/bin/env python3
"""SPE anchor tests for retirement strategy tools."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path: str, name: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _check(label: str, got: Any, expected: Any) -> bool:
    ok = got == expected
    status = "PASS" if ok else "FAIL"
    print(f"{status}  {label}: got={got!r} expected={expected!r}")
    return ok


def _run_savings(mod, payload: dict[str, Any], checks: list[tuple[str, Any]]) -> bool:
    result = mod.savings_from_dict(payload)
    if not result.get("ok"):
        print(f"FAIL  {payload.get('_label', mod.__name__)}: {result.get('errors')}")
        return False
    savings = result["savings"]
    all_ok = True
    for key, expected in checks:
        all_ok &= _check(key, savings.get(key), expected)
    return all_ok


def main() -> int:
    passed = 0
    total = 0

    er401k = _load_module(
        "skills/income_tax/assisted/401k-employer/tools/er_401k.py", "er_401k"
    )
    total += 1
    if _run_savings(
        er401k,
        {
            "_label": "401k-employer",
            "w2": {
                "wg_tp_sp": 0,
                "prefix": 1,
                "wg_fed_wages": 150_000,
                "wages_401k_contribution": 0,
                "wages_403b_contribution": 0,
                "wg_457b": 0,
            },
            "retirement": {
                "max_401k_contribution_allowed": 22_500,
                "combined_401k_limit": 69_000,
                "combined_limit_absorbed": 0,
            },
            "rates": {
                "federal_marginal_rate_pct": 24,
                "state_marginal_rate_pct": 9,
                "nyc_marginal_rate_pct": 0,
            },
            "filing_status_code": 1,
        },
        [("projected_tax_savings", 2475), ("cash_outlay", 0), ("strategy_change", 7500)],
    ):
        passed += 1

    ee403b = _load_module(
        "skills/income_tax/assisted/403b-employee/tools/ee_403b.py", "ee_403b"
    )
    total += 1
    if _run_savings(
        ee403b,
        {
            "_label": "403b-employee",
            "w2": {
                "wg_tp_sp": 0,
                "prefix": 1,
                "wg_fed_wages": 200_000,
                "wages_403b_contribution": 10_000,
            },
            "retirement": {
                "max_401k_contribution_allowed": 27_000,
                "combined_401k_limit": 69_000,
                "total_403b": 10_000,
            },
            "rates": {
                "federal_marginal_rate_pct": 12,
                "state_marginal_rate_pct": 8,
            },
            "filing_status_code": 1,
            "strategy_change": 17_000,
        },
        [("projected_tax_savings", 3400), ("cash_outlay", 13600)],
    ):
        passed += 1

    er403b = _load_module(
        "skills/income_tax/assisted/403b-employer/tools/er_403b.py", "er_403b"
    )
    total += 1
    if _run_savings(
        er403b,
        {
            "_label": "403b-employer",
            "w2": {
                "wg_tp_sp": 0,
                "prefix": 1,
                "wg_fed_wages": 45_000,
                "wages_403b_contribution": 5_000,
            },
            "retirement": {
                "max_401k_contribution_allowed": 27_000,
                "combined_401k_limit": 69_000,
            },
            "rates": {
                "federal_marginal_rate_pct": 12,
                "state_marginal_rate_pct": 8,
            },
            "filing_status_code": 1,
        },
        [("projected_tax_savings", 450), ("cash_outlay", 0), ("strategy_change", 2250)],
    ):
        passed += 1

    trad = _load_module(
        "skills/income_tax/assisted/traditional-ira/tools/traditional_ira.py",
        "traditional_ira",
    )
    total += 1
    if _run_savings(
        trad,
        {
            "_label": "traditional-ira",
            "person": {
                "earned_income": 100_000,
                "ira_contribution": 4000,
                "max_ira_allowed": 6000,
                "roth_cont": 0,
                "has_plan": 0,
            },
            "rates": {"federal_marginal_rate_pct": 37},
            "filing_status_code": 1,
        },
        [("projected_tax_savings", 740), ("cash_outlay", 1260), ("strategy_change", 2000)],
    ):
        passed += 1

    sep = _load_module(
        "skills/income_tax/assisted/sep-ira/tools/sep_ira.py", "sep_ira"
    )
    total += 1
    if _run_savings(
        sep,
        {
            "_label": "sep-ira",
            "person": {
                "all_se_income": 50_000,
                "sep_ira_contribution": 500,
                "max_sep_ira": 11_182,
                "solo401k": 0,
            },
            "rates": {"federal_marginal_rate_pct": 12},
            "filing_status_code": 1,
        },
        [
            ("projected_tax_savings", 1282),
            ("cash_outlay", 9400),
            ("strategy_change", 10682),
        ],
    ):
        passed += 1

    bd = _load_module(
        "skills/income_tax/assisted/backdoor-roth-ira/tools/backdoor_roth.py",
        "backdoor_roth",
    )
    total += 1
    if _run_savings(
        bd,
        {
            "_label": "backdoor-roth",
            "person": {"earned_income": 200_000, "non_deductible_ira": 6500},
            "filing_status_code": 1,
            "strategy_change": 6500,
        },
        [("projected_tax_savings", 0), ("cash_outlay", 6500)],
    ):
        passed += 1

    mega = _load_module(
        "skills/income_tax/assisted/mega-backdoor-roth/tools/mega_backdoor.py",
        "mega_backdoor",
    )
    total += 1
    if _run_savings(
        mega,
        {
            "_label": "mega-backdoor",
            "w2": {
                "wg_tp_sp": 0,
                "prefix": 1,
                "wg_fed_wages": 250_000,
                "wages_401k_contribution": 23_000,
            },
            "retirement": {
                "max_solo_401k_allowed": 69_000,
                "current_year_max_401k_allowed": 23_000,
                "prior_year_max_401k": 23_000,
                "modified_agi": 300_000,
                "roth_phase_out": 161_000,
            },
            "filing_status_code": 1,
        },
        [("projected_tax_savings", 0), ("cash_outlay", 46_000), ("strategy_change", 46_000)],
    ):
        passed += 1

    roth = _load_module(
        "skills/income_tax/assisted/roth-ira-conversion/tools/roth_conversion.py",
        "roth_conversion",
    )
    total += 1
    if _run_savings(
        roth,
        {
            "_label": "roth-conversion-tax_cost",
            "person": {"ira_contribution": 50_000},
            "rates": {"federal_marginal_rate_pct": 37},
            "filing_status_code": 1,
            "estimate_mode": "tax_cost",
            "strategy_change": 2000,
        },
        [("projected_tax_savings", -740), ("cash_outlay", -740)],
    ):
        passed += 1

    total += 1
    growth_result = roth.savings_from_dict(
        {
            "person": {"ira_contribution": 50_000},
            "filing_status_code": 1,
            "estimate_mode": "growth",
            "growth": {
                "amount": 10_000,
                "growth_rate_pct": 7,
                "years": 20,
                "retirement_rate_pct": 25,
            },
        }
    )
    fv = 10_000 * (1.07 ** 20)
    expected_savings = int(__import__("decimal").Decimal(str(fv * 0.25)).quantize(
        __import__("decimal").Decimal("1"),
        rounding=__import__("decimal").ROUND_HALF_UP,
    ))
    growth_ok = growth_result.get("ok") and _check(
        "roth-conversion-growth savings",
        growth_result["savings"]["projected_tax_savings"],
        expected_savings,
    ) and _check(
        "roth-conversion-growth cash",
        growth_result["savings"]["cash_outlay"],
        0,
    )
    if growth_ok:
        passed += 1

    print(f"\n{passed}/{total} anchor checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
