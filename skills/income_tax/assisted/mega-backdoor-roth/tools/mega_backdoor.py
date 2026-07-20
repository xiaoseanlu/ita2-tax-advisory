#!/usr/bin/env python3
"""Deterministic Mega Backdoor Roth tool (megaBackdoor.spe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


FILING_MARRIED = {2, 5}


@dataclass
class W2Input:
    delete_next_year: int = 0
    wg_tp_sp: int = 0
    nam_emp: str = ""
    prefix: int = 1
    wg_fed_wages: float = 0.0
    wages_401k_contribution: float = 0.0
    wages_403b_contribution: float = 0.0
    wg_457b: float = 0.0

    @property
    def owner(self) -> str:
        return "spouse" if int(self.wg_tp_sp) == 1 else "taxpayer"


@dataclass
class MegaRetirement:
    max_solo_401k_allowed: float = 0.0
    current_year_max_401k_allowed: float = 0.0
    prior_year_max_401k: float = 0.0
    modified_agi: float = 0.0
    roth_phase_out: float = 0.0


@dataclass
class AssessInput:
    w2: W2Input
    retirement: MegaRetirement = field(default_factory=MegaRetirement)
    filing_status_code: int = 1


@dataclass
class EstimateInput:
    w2: W2Input
    retirement: MegaRetirement = field(default_factory=MegaRetirement)
    filing_status_code: int = 1
    strategy_change: float | None = None
    total_cash_outlay_adjustments: float = 0.0


@dataclass
class ApplicabilityResult:
    applicable: bool
    recommended: bool
    reasons: list[str]
    taxpayer_spouse_or_joint: str
    strategy_change_default: float
    mega_max_allowed: float
    modified_agi: float
    roth_phase_out: float
    filing_status_code: int
    wg_fed_wages: float
    nam_emp: str
    prefix: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _maxed_deferral(w2: W2Input, prior_year_max: float) -> bool:
    return (
        float(w2.wages_401k_contribution) >= prior_year_max
        or float(w2.wages_403b_contribution) >= prior_year_max
        or float(w2.wg_457b) >= prior_year_max
    )


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    w2 = inp.w2
    r = inp.retirement
    owner = w2.owner
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED
    mega_max = max(float(r.max_solo_401k_allowed) - float(r.current_year_max_401k_allowed), 0.0)

    pool_ok = int(w2.delete_next_year) == 0 and float(w2.wg_fed_wages) > 0
    if not pool_ok:
        reasons.append(
            "W-2 must have deleteNextYear == 0 and wgFedwages > 0 (SPE applicableW2s)."
        )

    # SPE: spouse applicable has no married gate; recommend does.
    applicable = bool(pool_ok)

    phased_out = float(r.modified_agi) > float(r.roth_phase_out)
    maxed = _maxed_deferral(w2, float(r.prior_year_max_401k))
    recommended = bool(
        applicable
        and phased_out
        and float(w2.wg_fed_wages) > 0
        and maxed
        and (owner != "spouse" or married)
    )
    if owner == "spouse" and not married:
        reasons.append(
            f"Spouse mega backdoor recommend requires married filing (2 or 5); "
            f"got {inp.filing_status_code}."
        )
    if applicable and not phased_out:
        reasons.append("Recommend blocked: modified_agi is not above roth_phase_out.")
    if applicable and not maxed:
        reasons.append(
            "Recommend blocked: 401k/403b/457b deferral has not reached prior_year_max_401k."
        )
    if recommended:
        reasons.append(f"Meets mega backdoor recommend gates (mega_max={mega_max:.2f}).")

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        strategy_change_default=mega_max,
        mega_max_allowed=mega_max,
        modified_agi=float(r.modified_agi),
        roth_phase_out=float(r.roth_phase_out),
        filing_status_code=int(inp.filing_status_code),
        wg_fed_wages=float(w2.wg_fed_wages),
        nam_emp=str(w2.nam_emp or ""),
        prefix=int(w2.prefix),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    warnings: list[str] = [
        "Mega backdoor: PROJECTED_TAX_SAVINGS is always 0 in SPE.",
        "CASH_OUTLAY equals STRATEGY_CHANGE (after-tax mega contribution).",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(
            w2=inp.w2,
            retirement=inp.retirement,
            filing_status_code=inp.filing_status_code,
        )
    )

    if inp.strategy_change is None:
        strategy_change = appl.strategy_change_default
    else:
        strategy_change = float(inp.strategy_change)

    if not appl.applicable:
        errors.append("W-2 is not applicable for mega backdoor under SPE gates.")

    tax_savings = 0.0
    cash_outlay = float(strategy_change + float(inp.total_cash_outlay_adjustments or 0))

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "applicability": appl.to_dict(),
            "savings": None,
            "strategy_change": strategy_change,
            "baseline_amount": 0.0,
            "projected_amount": strategy_change,
            "cash_outlay": cash_outlay,
            "mutations": [],
        }

    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "applicability": appl.to_dict(),
        "savings": {
            "projected_tax_savings": tax_savings,
            "cash_outlay": cash_outlay,
            "strategy_change": strategy_change,
            "baseline_amount": 0.0,
            "projected_amount": strategy_change,
            "mega_max_allowed": appl.mega_max_allowed,
            "taxpayer_spouse_or_joint": appl.taxpayer_spouse_or_joint,
        },
        "strategy_change": strategy_change,
        "baseline_amount": 0.0,
        "projected_amount": strategy_change,
        "cash_outlay": cash_outlay,
        "mutations": [],
    }


def w2_from_dict(d: dict[str, Any]) -> W2Input:
    return W2Input(
        delete_next_year=int(d.get("delete_next_year") or 0),
        wg_tp_sp=int(d.get("wg_tp_sp") or 0),
        nam_emp=str(d.get("nam_emp") or ""),
        prefix=int(d.get("prefix") or 1),
        wg_fed_wages=float(d.get("wg_fed_wages") or 0),
        wages_401k_contribution=float(d.get("wages_401k_contribution") or 0),
        wages_403b_contribution=float(d.get("wages_403b_contribution") or 0),
        wg_457b=float(d.get("wg_457b") or 0),
    )


def retirement_from_dict(d: dict[str, Any] | None) -> MegaRetirement:
    d = d or {}
    return MegaRetirement(
        max_solo_401k_allowed=float(d.get("max_solo_401k_allowed") or 0),
        current_year_max_401k_allowed=float(
            d.get("current_year_max_401k_allowed") or 0
        ),
        prior_year_max_401k=float(d.get("prior_year_max_401k") or 0),
        modified_agi=float(d.get("modified_agi") or 0),
        roth_phase_out=float(d.get("roth_phase_out") or 0),
    )


def assess_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("w2"), dict):
        raise ValueError("Missing 'w2' object.")
    return assess_applicability(
        AssessInput(
            w2=w2_from_dict(payload["w2"]),
            retirement=retirement_from_dict(payload.get("retirement")),
            filing_status_code=int(payload.get("filing_status_code") or 1),
        )
    ).to_dict()


def savings_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("w2"), dict):
        raise ValueError("Missing 'w2' object.")
    sc = payload.get("strategy_change")
    return estimate_savings(
        EstimateInput(
            w2=w2_from_dict(payload["w2"]),
            retirement=retirement_from_dict(payload.get("retirement")),
            filing_status_code=int(payload.get("filing_status_code") or 1),
            strategy_change=None if sc is None else float(sc),
            total_cash_outlay_adjustments=float(
                payload.get("total_cash_outlay_adjustments") or 0
            ),
        )
    )
