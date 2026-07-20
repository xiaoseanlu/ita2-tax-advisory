#!/usr/bin/env python3
"""Deterministic Traditional IRA tool (contribution-Traditional-IRA.spe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FILING_MARRIED = {2, 5}
NON_CONFORMING_STATES = {"MA", "NH", "NJ", "PA"}


def _spe_round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class RatesInput:
    federal_marginal_rate_pct: float = 24.0
    state_marginal_rate_pct: float = 0.0
    nyc_marginal_rate_pct: float = 0.0
    resident_state: str = ""
    apply_nonconforming: bool = True

    @property
    def non_conforming_state(self) -> bool:
        return self.apply_nonconforming and (
            (self.resident_state or "").upper() in NON_CONFORMING_STATES
        )

    @property
    def total_marginal_rate_pct(self) -> float:
        if self.non_conforming_state:
            return self.federal_marginal_rate_pct
        return (
            self.federal_marginal_rate_pct
            + self.state_marginal_rate_pct
            + self.nyc_marginal_rate_pct
        )


@dataclass
class PersonInput:
    taxpayer_spouse_or_joint: str = "taxpayer"
    earned_income: float = 0.0
    ira_contribution: float = 0.0
    max_ira_allowed: float = 0.0
    roth_cont: float = 0.0
    has_plan: int = 0
    ira_magi: float = 0.0
    ira_phase_out_begin: float = 0.0


@dataclass
class AssessInput:
    person: PersonInput
    filing_status_code: int = 1


@dataclass
class EstimateInput:
    person: PersonInput
    filing_status_code: int = 1
    rates: RatesInput = field(default_factory=RatesInput)
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
    ira_contribution: float
    max_ira_allowed: float
    filing_status_code: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    p = inp.person
    owner = p.taxpayer_spouse_or_joint
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED

    if owner == "spouse" and not married:
        reasons.append(
            f"Spouse Traditional IRA requires married filing (2 or 5); "
            f"got {inp.filing_status_code}."
        )

    applicable = bool(p.earned_income > 0 and (owner != "spouse" or married))
    if not (p.earned_income > 0):
        reasons.append("Applicable blocked: earnedIncome must be > 0.")

    below_max = p.ira_contribution < p.max_ira_allowed
    no_roth = float(p.roth_cont or 0) == 0
    plan_ok = int(p.has_plan) == 0 or (
        int(p.has_plan) == 1 and float(p.ira_magi) < float(p.ira_phase_out_begin)
    )
    recommended = bool(
        applicable
        and below_max
        and no_roth
        and plan_ok
        and (owner != "spouse" or married)
    )
    if applicable and not below_max:
        reasons.append("Recommend blocked: ira_contribution >= max_ira_allowed.")
    if applicable and not no_roth:
        reasons.append("Recommend blocked: roth_cont != 0.")
    if applicable and not plan_ok:
        reasons.append(
            "Recommend blocked: has_plan and ira_magi >= phase_out_begin."
        )
    if recommended:
        reasons.append("Meets Traditional IRA recommend gates.")

    strategy_change_default = max(float(p.max_ira_allowed) - float(p.ira_contribution), 0.0)

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        strategy_change_default=strategy_change_default,
        earned_income=float(p.earned_income),
        ira_contribution=float(p.ira_contribution),
        max_ira_allowed=float(p.max_ira_allowed),
        filing_status_code=int(inp.filing_status_code),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    warnings: list[str] = [
        "Static SPE-faithful estimate — not a live ITA engine recalculation.",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(person=inp.person, filing_status_code=inp.filing_status_code)
    )
    baseline = float(inp.person.ira_contribution or 0)

    if inp.strategy_change is None:
        strategy_change = appl.strategy_change_default
    else:
        strategy_change = float(inp.strategy_change)

    if not appl.applicable:
        errors.append("Person is not applicable for Traditional IRA under SPE gates.")

    rates = inp.rates
    if rates.non_conforming_state:
        warnings.append(
            f"Resident state {rates.resident_state.upper()} — nonconforming; "
            "state/NYC zeroed for savings."
        )

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "applicability": appl.to_dict(),
            "savings": None,
            "strategy_change": strategy_change,
            "baseline_amount": baseline,
            "projected_amount": strategy_change + baseline,
            "mutations": [],
        }

    total = rates.total_marginal_rate_pct
    tax_savings = float(_spe_round(strategy_change * total / 100.0))
    cash_outlay = float(
        strategy_change
        - tax_savings
        + float(inp.total_cash_outlay_adjustments or 0)
    )

    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "applicability": appl.to_dict(),
        "savings": {
            "projected_tax_savings": tax_savings,
            "cash_outlay": cash_outlay,
            "marginal_rate_fed": rates.federal_marginal_rate_pct,
            "marginal_rate_state": (
                0.0 if rates.non_conforming_state else rates.state_marginal_rate_pct
            ),
            "marginal_rate_nyc": (
                0.0 if rates.non_conforming_state else rates.nyc_marginal_rate_pct
            ),
            "marginal_rate_total": total,
            "strategy_change": strategy_change,
            "baseline_amount": baseline,
            "projected_amount": strategy_change + baseline,
            "taxpayer_spouse_or_joint": appl.taxpayer_spouse_or_joint,
        },
        "strategy_change": strategy_change,
        "baseline_amount": baseline,
        "projected_amount": strategy_change + baseline,
        "cash_outlay": cash_outlay,
        "mutations": [],
    }


def person_from_dict(d: dict[str, Any]) -> PersonInput:
    return PersonInput(
        taxpayer_spouse_or_joint=str(d.get("taxpayer_spouse_or_joint") or "taxpayer"),
        earned_income=float(d.get("earned_income") or 0),
        ira_contribution=float(d.get("ira_contribution") or 0),
        max_ira_allowed=float(d.get("max_ira_allowed") or 0),
        roth_cont=float(d.get("roth_cont") or 0),
        has_plan=int(d.get("has_plan") or 0),
        ira_magi=float(d.get("ira_magi") or 0),
        ira_phase_out_begin=float(d.get("ira_phase_out_begin") or 0),
    )


def rates_from_dict(d: dict[str, Any] | None) -> RatesInput:
    d = d or {}
    return RatesInput(
        federal_marginal_rate_pct=float(d.get("federal_marginal_rate_pct") or 24),
        state_marginal_rate_pct=float(d.get("state_marginal_rate_pct") or 0),
        nyc_marginal_rate_pct=float(d.get("nyc_marginal_rate_pct") or 0),
        resident_state=str(d.get("resident_state") or ""),
        apply_nonconforming=bool(d.get("apply_nonconforming", True)),
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
            rates=rates_from_dict(payload.get("rates")),
            strategy_change=None if sc is None else float(sc),
            total_cash_outlay_adjustments=float(
                payload.get("total_cash_outlay_adjustments") or 0
            ),
        )
    )
