#!/usr/bin/env python3
"""Deterministic Backdoor Roth IRA tool (backdoorRothIRA.spe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


FILING_MARRIED = {2, 5}


@dataclass
class PersonInput:
    taxpayer_spouse_or_joint: str = "taxpayer"
    earned_income: float = 0.0
    non_deductible_ira: float = 0.0


@dataclass
class AssessInput:
    person: PersonInput
    filing_status_code: int = 1


@dataclass
class EstimateInput:
    person: PersonInput
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
    earned_income: float
    non_deductible_ira: float
    filing_status_code: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    p = inp.person
    owner = p.taxpayer_spouse_or_joint
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED

    # SPE: applicableIRA = earnedIncome > 0 for both TP and spouse (no married gate).
    # Recommend spouse requires marriedStatus && spsNonDeductible > 0.
    applicable = bool(p.earned_income > 0)
    if not applicable:
        reasons.append("Applicable blocked: earnedIncome must be > 0.")

    recommended = bool(applicable and float(p.non_deductible_ira) > 0)
    if owner == "spouse":
        if not married:
            recommended = False
            reasons.append(
                f"Spouse backdoor Roth recommend requires married filing (2 or 5); "
                f"got {inp.filing_status_code}."
            )
    if applicable and float(p.non_deductible_ira) <= 0:
        reasons.append("Recommend blocked: non_deductible_ira is not > 0.")
    if recommended:
        reasons.append("Meets backdoor Roth recommend gates.")

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        strategy_change_default=0.0,
        earned_income=float(p.earned_income),
        non_deductible_ira=float(p.non_deductible_ira),
        filing_status_code=int(inp.filing_status_code),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    warnings: list[str] = [
        "Backdoor Roth: PROJECTED_TAX_SAVINGS is always 0 in SPE.",
        "CASH_OUTLAY equals STRATEGY_CHANGE (advisor-entered conversion amount).",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(person=inp.person, filing_status_code=inp.filing_status_code)
    )

    if inp.strategy_change is None:
        strategy_change = appl.strategy_change_default
    else:
        strategy_change = float(inp.strategy_change)

    if not appl.applicable:
        errors.append("Person is not applicable for backdoor Roth under SPE gates.")

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
            "taxpayer_spouse_or_joint": appl.taxpayer_spouse_or_joint,
        },
        "strategy_change": strategy_change,
        "baseline_amount": 0.0,
        "projected_amount": strategy_change,
        "cash_outlay": cash_outlay,
        "mutations": [],
    }


def person_from_dict(d: dict[str, Any]) -> PersonInput:
    return PersonInput(
        taxpayer_spouse_or_joint=str(d.get("taxpayer_spouse_or_joint") or "taxpayer"),
        earned_income=float(d.get("earned_income") or 0),
        non_deductible_ira=float(d.get("non_deductible_ira") or 0),
    )


def assess_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("person"), dict):
        raise ValueError("Missing 'person' object.")
    return assess_applicability(
        AssessInput(
            person=person_from_dict(payload["person"]),
            filing_status_code=int(payload.get("filing_status_code") or 1),
        )
    ).to_dict()


def savings_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("person"), dict):
        raise ValueError("Missing 'person' object.")
    sc = payload.get("strategy_change")
    return estimate_savings(
        EstimateInput(
            person=person_from_dict(payload["person"]),
            filing_status_code=int(payload.get("filing_status_code") or 1),
            strategy_change=None if sc is None else float(sc),
            total_cash_outlay_adjustments=float(
                payload.get("total_cash_outlay_adjustments") or 0
            ),
        )
    )
