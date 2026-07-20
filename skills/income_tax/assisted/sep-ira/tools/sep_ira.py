#!/usr/bin/env python3
"""Deterministic SEP-IRA tool (SEP-IRA.spe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FILING_MARRIED = {2, 5}
NON_CONFORMING_STATES = {"MA", "NJ", "PA"}


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
    all_se_income: float = 0.0
    wages_paid_by_scorp: int = 0
    solo401k: float = 0.0
    sep_ira_contribution: float = 0.0
    max_sep_ira: float = 0.0


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
    all_se_income: float
    wages_paid_by_scorp: int
    sep_ira_contribution: float
    max_sep_ira: float
    filing_status_code: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _recommend_ok(p: PersonInput, strategy_change_default: float) -> bool:
    solo_sep_ok = (p.solo401k == 0) or (p.solo401k > 0 and p.sep_ira_contribution > 0)
    return bool(
        (strategy_change_default > 0 and solo_sep_ok) or int(p.wages_paid_by_scorp) > 0
    )


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    p = inp.person
    owner = p.taxpayer_spouse_or_joint
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED
    strategy_change_default = max(float(p.max_sep_ira) - float(p.sep_ira_contribution), 0.0)

    # SPE spouse: (marriedMAGI && allSEincome > 0) || wagesPaidByScorp > 0
    # Unmarried spouse with S-Corp wages can still be applicable.
    has_se = float(p.all_se_income) > 0
    has_scorp_wages = int(p.wages_paid_by_scorp) > 0
    if owner == "spouse":
        applicable = bool((married and has_se) or has_scorp_wages)
        if not applicable:
            reasons.append(
                "Spouse SEP applicable needs (married + SE income) OR wages_paid_by_scorp > 0 "
                f"(filingStatus={inp.filing_status_code})."
            )
    else:
        applicable = bool(has_se or has_scorp_wages)
        if not applicable:
            reasons.append(
                "Applicable blocked: all_se_income > 0 OR wages_paid_by_scorp > 0 required."
            )

    recommended = bool(applicable and _recommend_ok(p, strategy_change_default))
    if owner == "spouse" and recommended and not married and not has_scorp_wages:
        recommended = False
    if applicable and not _recommend_ok(p, strategy_change_default):
        reasons.append(
            "Recommend blocked: strategy_change_default <= 0 and no S-Corp wages, "
            "or solo401k/sep gate failed."
        )
    if recommended:
        reasons.append("Meets SEP-IRA recommend gates.")

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        strategy_change_default=strategy_change_default,
        all_se_income=float(p.all_se_income),
        wages_paid_by_scorp=int(p.wages_paid_by_scorp),
        sep_ira_contribution=float(p.sep_ira_contribution),
        max_sep_ira=float(p.max_sep_ira),
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
    baseline = float(inp.person.sep_ira_contribution or 0)

    if inp.strategy_change is None:
        strategy_change = appl.strategy_change_default
    else:
        strategy_change = float(inp.strategy_change)

    if not appl.applicable:
        errors.append("Person is not applicable for SEP-IRA under SPE gates.")

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
        all_se_income=float(d.get("all_se_income") or 0),
        wages_paid_by_scorp=int(d.get("wages_paid_by_scorp") or 0),
        solo401k=float(d.get("solo401k") or 0),
        sep_ira_contribution=float(d.get("sep_ira_contribution") or 0),
        max_sep_ira=float(d.get("max_sep_ira") or 0),
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
