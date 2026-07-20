#!/usr/bin/env python3
"""Deterministic Roth IRA Conversion tool (Roth_IRA_Conversion.spe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal


EstimateMode = Literal["tax_cost", "growth"]


def _spe_round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class RatesInput:
    federal_marginal_rate_pct: float = 24.0
    state_marginal_rate_pct: float = 0.0
    nyc_marginal_rate_pct: float = 0.0
    resident_state: str = ""
    nj_pension_exclusion_factor: float = 0.0
    apply_pa_nonconforming: bool = True

    @property
    def pa_non_conforming(self) -> bool:
        return self.apply_pa_nonconforming and (self.resident_state or "").upper() == "PA"

    @property
    def nj_non_conforming(self) -> bool:
        return (self.resident_state or "").upper() == "NJ"

    @property
    def total_marginal_rate_pct(self) -> float:
        if self.pa_non_conforming:
            return self.federal_marginal_rate_pct
        return (
            self.federal_marginal_rate_pct
            + self.state_marginal_rate_pct
            + self.nyc_marginal_rate_pct
        )


@dataclass
class PersonInput:
    taxpayer_spouse_or_joint: str = "taxpayer"
    ira_contribution: float = 0.0
    total_401k_contribution: float = 0.0
    total_403b_contribution: float = 0.0
    total_457b_contribution: float = 0.0


@dataclass
class GrowthInput:
    amount: float = 0.0
    growth_rate_pct: float = 0.0
    years: float = 0.0
    retirement_rate_pct: float = 0.0


@dataclass
class AssessInput:
    person: PersonInput
    filing_status_code: int = 1


@dataclass
class EstimateInput:
    person: PersonInput
    filing_status_code: int = 1
    rates: RatesInput = field(default_factory=RatesInput)
    estimate_mode: EstimateMode = "tax_cost"
    strategy_change: float | None = None
    growth: GrowthInput = field(default_factory=GrowthInput)
    total_cash_outlay_adjustments: float = 0.0


@dataclass
class ApplicabilityResult:
    applicable: bool
    recommended: bool
    reasons: list[str]
    taxpayer_spouse_or_joint: str
    filing_status_code: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    p = inp.person
    owner = p.taxpayer_spouse_or_joint
    reasons: list[str] = []
    fs = int(inp.filing_status_code)

    if owner == "taxpayer":
        applicable = True
    elif owner == "spouse":
        applicable = fs == 2
        if not applicable:
            reasons.append("Spouse Roth conversion applicable only when filingStatus == 2.")
    else:
        applicable = False
        reasons.append(f"Unknown owner '{owner}'.")

    has_assets = (
        float(p.ira_contribution) > 0
        or float(p.total_401k_contribution) > 0
        or float(p.total_403b_contribution) > 0
        or float(p.total_457b_contribution) > 0
    )
    recommended = bool(applicable and has_assets)
    if applicable and not has_assets:
        reasons.append(
            "Recommend blocked: no ira/401k/403b/457b contributions > 0 on record."
        )
    if recommended:
        reasons.append("Meets Roth conversion recommend gates.")

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        filing_status_code=fs,
    )


def _tax_cost_savings(strategy_change: float, rates: RatesInput) -> float:
    if rates.nj_non_conforming and rates.nj_pension_exclusion_factor:
        fed = _spe_round(
            rates.federal_marginal_rate_pct * strategy_change / 100.0
        )
        state_taxable = _spe_round(strategy_change * float(rates.nj_pension_exclusion_factor))
        state = _spe_round(rates.state_marginal_rate_pct * state_taxable / 100.0)
        return float(-(fed + state))
    total = rates.total_marginal_rate_pct
    return float(-_spe_round(strategy_change * total / 100.0))


def _growth_savings(growth: GrowthInput) -> tuple[float, float]:
    amount = float(growth.amount)
    r = float(growth.growth_rate_pct)
    years = float(growth.years)
    retirement_rate = float(growth.retirement_rate_pct)
    fv = amount * ((1.0 + r / 100.0) ** years)
    savings = float(_spe_round(fv * retirement_rate / 100.0))
    return fv, savings


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    warnings: list[str] = [
        "Static SPE-faithful estimate — not a live ITA engine recalculation.",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(person=inp.person, filing_status_code=inp.filing_status_code)
    )

    if inp.estimate_mode == "growth":
        fv, tax_savings = _growth_savings(inp.growth)
        strategy_change = fv
        cash_outlay = 0.0
    else:
        if inp.strategy_change is None:
            strategy_change = 0.0
        else:
            strategy_change = float(inp.strategy_change)
        rates = inp.rates
        if rates.pa_non_conforming:
            warnings.append("PA resident — state/NYC zeroed for tax_cost savings.")
        tax_savings = _tax_cost_savings(strategy_change, rates)
        cash_outlay = float(tax_savings + float(inp.total_cash_outlay_adjustments or 0))

    if not appl.applicable:
        errors.append("Person is not applicable for Roth conversion under SPE gates.")

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "applicability": appl.to_dict(),
            "savings": None,
            "strategy_change": strategy_change,
            "estimate_mode": inp.estimate_mode,
            "mutations": [],
        }

    result: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "applicability": appl.to_dict(),
        "savings": {
            "projected_tax_savings": tax_savings,
            "cash_outlay": cash_outlay,
            "strategy_change": strategy_change,
            "estimate_mode": inp.estimate_mode,
            "taxpayer_spouse_or_joint": appl.taxpayer_spouse_or_joint,
        },
        "strategy_change": strategy_change,
        "cash_outlay": cash_outlay,
        "estimate_mode": inp.estimate_mode,
        "mutations": [],
    }
    if inp.estimate_mode == "tax_cost" and strategy_change > 0:
        # SPE ConvertedAmount added: create usPensInp with pensTxblAmt = STRATEGY_CHANGE
        owner = appl.taxpayer_spouse_or_joint
        pension_tp_sp = 1 if owner == "spouse" else 0
        result["mutations"] = [
            {
                "path": (
                    "$.projection.return.income.usIncSum.usRetPlnDistrSum.usPensInp"
                    "[?(@.prefix == NEW)]"
                ),
                "action": "new",
                "fields": {
                    "prefix": "max(existing)+1",
                    "general.pensionTpSp": pension_tp_sp,
                    "general.nameOfPensPayer": "New pension payer (Roth conversion)",
                    "other.deleteNextYear": 0,
                    "general.distCode1": 2,
                    "taxable.pensTxblAmt": strategy_change,
                },
                "secondary_id": "ConvertedAmount",
                "step": "Create taxable IRA/pension distribution for conversion amount",
            }
        ]
    if inp.estimate_mode == "growth":
        result["savings"]["future_value"] = strategy_change
        result["future_value"] = strategy_change
    return result


def person_from_dict(d: dict[str, Any]) -> PersonInput:
    return PersonInput(
        taxpayer_spouse_or_joint=str(d.get("taxpayer_spouse_or_joint") or "taxpayer"),
        ira_contribution=float(d.get("ira_contribution") or 0),
        total_401k_contribution=float(d.get("total_401k_contribution") or 0),
        total_403b_contribution=float(d.get("total_403b_contribution") or 0),
        total_457b_contribution=float(d.get("total_457b_contribution") or 0),
    )


def growth_from_dict(d: dict[str, Any] | None) -> GrowthInput:
    d = d or {}
    return GrowthInput(
        amount=float(d.get("amount") or 0),
        growth_rate_pct=float(d.get("growth_rate_pct") or 0),
        years=float(d.get("years") or 0),
        retirement_rate_pct=float(d.get("retirement_rate_pct") or 0),
    )


def rates_from_dict(d: dict[str, Any] | None) -> RatesInput:
    d = d or {}
    return RatesInput(
        federal_marginal_rate_pct=float(d.get("federal_marginal_rate_pct") or 24),
        state_marginal_rate_pct=float(d.get("state_marginal_rate_pct") or 0),
        nyc_marginal_rate_pct=float(d.get("nyc_marginal_rate_pct") or 0),
        resident_state=str(d.get("resident_state") or ""),
        nj_pension_exclusion_factor=float(d.get("nj_pension_exclusion_factor") or 0),
        apply_pa_nonconforming=bool(d.get("apply_pa_nonconforming", True)),
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
    mode = str(payload.get("estimate_mode") or "tax_cost")
    if mode not in ("tax_cost", "growth"):
        raise ValueError("estimate_mode must be 'tax_cost' or 'growth'.")
    return estimate_savings(
        EstimateInput(
            person=person_from_dict(payload["person"]),
            filing_status_code=int(payload.get("filing_status_code") or 1),
            rates=rates_from_dict(payload.get("rates")),
            estimate_mode=mode,  # type: ignore[arg-type]
            strategy_change=None if sc is None else float(sc),
            growth=growth_from_dict(payload.get("growth")),
            total_cash_outlay_adjustments=float(
                payload.get("total_cash_outlay_adjustments") or 0
            ),
        )
    )
