#!/usr/bin/env python3
"""Extract a compact UI seed from an ITA projection JSON (e.g. 2025projection.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _g(obj: Any, *path: str, default: Any = None) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _num(val: Any, default: float | int = 0) -> float | int:
    if val is None or val == "":
        return default
    try:
        n = float(val)
    except (TypeError, ValueError):
        return default
    if n == int(n):
        return int(n)
    return n


def _owner_from_code(code: Any) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "taxpayer"
    if c == 1:
        return "spouse"
    if c == 2:
        return "joint"
    return "taxpayer"


def extract_ui_seed(projection: dict) -> dict:
    """Map projection TaxML-ish JSON → form seeds for the ITA strategies hub."""
    ita = _g(projection, "summary", "usITASummary", "defaultSection", default={}) or {}
    tp = _g(projection, "summary", "usITATaxpayerItems", "defaultSection", default={}) or {}
    indexed = _g(projection, "summary", "usITAIndexedAmount", "defaultSection", default={}) or {}
    only = _g(projection, "summary", "usITAOnlyIncome", default=[]) or []
    only0 = (only[0].get("defaultSection") if only and isinstance(only[0], dict) else {}) or {}

    wages = _g(projection, "income", "usIncSum", "usWageSum", "usWageInp", default=[]) or []
    w0 = wages[0] if wages else {}
    w_gen = w0.get("general") or {}
    w_fed = w0.get("federal") or {}

    buses = _g(projection, "income", "usIncSum", "usBusIncSum", "usBusIncInp", default=[]) or []
    b0 = buses[0] if buses else {}
    b_gen = b0.get("generalInformation") or {}
    b_net = b0.get("netProfitorLoss") or {}

    net_income = _num(b_net.get("itaNetProfitLoss"), _num(ita.get("totalScheduleCIncome")))
    all_se = _num(tp.get("allSEIncome"), net_income)
    se_tax = _num(ita.get("selfEmploymentTax"))
    # Projection sometimes leaves subjsETax=0 even when Sch C + SE tax exist.
    is_se = bool(_num(b_gen.get("subjsETax"))) or (net_income > 0 and (all_se > 0 or se_tax > 0))

    bus_name = (b_gen.get("princpalBus") or "").strip() or "Schedule C business"
    owner = _owner_from_code(b_gen.get("busTpSpJt"))
    filing = _num(ita.get("filingStatus"), 1)
    fed_m = _num(ita.get("marginalRate"), 24)
    state_m = _num(ita.get("stateMarginalRate"), 0)
    ss_base = _num(indexed.get("maxSSwage"), 176100)
    ss_already = _num(tp.get("incomeTaxedBySocSec"), _num(w_fed.get("wgSSwages")))

    reasonable = _num(only0.get("taxpayerReasonableWages"))
    if owner == "spouse":
        reasonable = _num(only0.get("spouseReasonableWages"), reasonable)

    seed = {
        "source": "ita-rules/2025projection.json",
        "label": "2025 projection",
        "meta": {
            "tax_year": _num(ita.get("taxYear"), _num(_g(projection, "summary", "usMain", "defaultSection", "taxYear"), 2025)),
            "filing_status": filing,
            "agi": _num(ita.get("adjustedGrossIncome")),
            "taxable_income": _num(ita.get("taxableIncome")),
            "federal_tax": _num(ita.get("federalTax")),
            "total_wages": _num(ita.get("totalWages")),
            "schedule_c_income": _num(ita.get("totalScheduleCIncome")),
        },
        "rates": {
            "federal_marginal_rate_pct": fed_m,
            "state_marginal_rate_pct": state_m,
            "nyc_marginal_rate_pct": _num(ita.get("marginalNYC"), 0),
            "ss_wage_base": ss_base,
        },
        "scorp": {
            "name": bus_name,
            "source": "Schedule C",
            "owner": owner,
            "net_income": net_income,
            "ownership_pct": 100,
            "is_se_biz": is_se,
            "reasonable_wage": reasonable if reasonable else "",
            "fed_rate": fed_m,
            "state_rate": state_m,
            "ss_wage_base": ss_base,
            "ss_already": ss_already,
            "all_se_income": all_se,
        },
        "solo401k": {
            "owner": owner if owner in ("taxpayer", "spouse") else "taxpayer",
            "filing_status": filing,
            "all_se_income": all_se,
            "earned_income": _num(tp.get("earnedIncome")),
            "sep_ira": _num(tp.get("sepIRA")),
            "solo_elective_deferral": 0,
            "solo401k_contribution": _num(tp.get("solo401kContribution")),
            "solo401k_catchup": _num(tp.get("solo401kCatchUp")),
            "biz_exists_without_wages": True,
            "max_allowed": _num(tp.get("maxSolo401kContributionAllowed")),
            "combined_limit": _num(tp.get("combined401KLimit")),
            "total_401k": _num(tp.get("total401kContribution")),
            "total_roth_401k": _num(tp.get("totalRoth401kContribution")),
            "total_403b": _num(tp.get("total403bContribution")),
            "total_roth_403b": _num(tp.get("totalRoth403bContribution")),
            "baseline_solo401k": _num(tp.get("solo401kContribution")),
            "fed_rate": fed_m,
            "state_rate": state_m,
            "nyc_rate": _num(ita.get("marginalNYC"), 0),
        },
        "ee401k": {
            "owner": str(_num(w_gen.get("wgTpSp"), 0)),
            "filing": filing,
            "nam": (w_gen.get("namEmp") or "").strip() or "Employer",
            "prefix": _num(w0.get("prefix"), 1),
            "wages": _num(w_fed.get("wgFedwages")),
            "401k": _num(w_fed.get("wages401kContribution")),
            "403b": _num(w_fed.get("wages403bContribution")),
            "457b": _num(w_fed.get("wg457b")),
            "max": _num(tp.get("max401kContributionAllowed")),
            "combined": _num(tp.get("combined401KLimit")),
            "total401k": _num(tp.get("total401kContribution")),
            "roth401k": _num(tp.get("totalRoth401kContribution")),
            "403b_base": _num(tp.get("total403bContribution")),
            "roth403b": _num(tp.get("totalRoth403bContribution")),
            "solo": _num(tp.get("solo401kContribution")),
            "abs_ee": _num(tp.get("employee401kcontributionlimitabsorbed")),
            "abs_comb": _num(tp.get("combined401kcontributionlimitabsorbed")),
            "fed": fed_m,
            "state": state_m,
            "nyc": _num(ita.get("marginalNYC"), 0),
        },
        "retirement_common": {
            "wg_tp_sp": str(_num(w_gen.get("wgTpSp"), 0)),
            "is_spouse": str(_num(w_gen.get("wgTpSp"), 0)),
            "filing_status_code": filing,
            "nam_emp": (w_gen.get("namEmp") or "").strip() or "Employer",
            "wg_fed_wages": _num(w_fed.get("wgFedwages")),
            "wages_401k_contribution": _num(w_fed.get("wages401kContribution")),
            "wages_401k": _num(w_fed.get("wages401kContribution")),
            "wages_403b_contribution": _num(w_fed.get("wages403bContribution")),
            "wg_457b": _num(w_fed.get("wg457b")),
            "max_401k_contribution_allowed": _num(tp.get("max401kContributionAllowed")),
            "current_year_max_401k_allowed": _num(tp.get("max401kContributionAllowed")),
            "combined_401k_limit": _num(tp.get("combined401KLimit")),
            "combined_limit_absorbed": _num(tp.get("combined401kcontributionlimitabsorbed")),
            "total_403b": _num(tp.get("total403bContribution")),
            "total_401k": _num(tp.get("total401kContribution")),
            "all_se_income": all_se,
            "earned_income": _num(tp.get("earnedIncome")),
            "sep_ira_contribution": _num(tp.get("sepIRA")),
            "max_sep_ira": _num(tp.get("maxSepIRA")),
            "solo_401k_contribution": _num(tp.get("solo401kContribution")),
            "max_solo_401k_allowed": _num(tp.get("maxSolo401kContributionAllowed")),
            "ira_contribution": _num(tp.get("iraContribution")),
            "max_ira_allowed": _num(tp.get("maxIRAContributionAllowed")),
            "roth_cont": _num(tp.get("nonDeductibleIRA"), 0),  # best available; often 0
            "non_deductible_ira": _num(tp.get("nonDeductibleIRA")),
            "has_plan": "1" if w_gen.get("wgPensPlanYN") else "0",
            "ira_magi": _num(ita.get("iRAMagi"), _num(ita.get("modifiedAgi"))),
            "ira_phase_out_begin": _num(tp.get("iRAPhaseOutBegin")),
            "modified_agi": _num(ita.get("modifiedAgi")),
            "roth_phase_out": _num(ita.get("rothMAGILimit")),
            "federal_marginal_rate_pct": fed_m,
            "state_marginal_rate_pct": state_m,
            "nyc_marginal_rate_pct": _num(ita.get("marginalNYC"), 0),
        },
    }
    return seed


def load_default_seed(path: Path | None = None) -> dict:
    root = Path(__file__).resolve().parent
    path = path or (root / "2025projection.json")
    with open(path, encoding="utf-8") as f:
        return extract_ui_seed(json.load(f))


if __name__ == "__main__":
    print(json.dumps(load_default_seed(), indent=2))
