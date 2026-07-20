#!/usr/bin/env python3
"""
Deterministic 401(k) Employer Contribution tool (employer-401k-contribution.spe).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FILING_MARRIED = {2, 5}


def _spe_round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Combined §415(c) limit by tax year, with age-50 catch-up.
#
# SPE source: shared401KLimit_GlobalScope.spe lines 39-83. The SPE only
# recomputes combined401KLimit inside `if actualyear < 2023` and adds the
# age-50 catch-up; otherwise it trusts the engine-provided combined limit.
# The employer strategy includes this file verbatim, so the same table applies
# to combined401KLimitTxp / combined401KLimitSps used by the employer headroom
# (shared401KLimit_GlobalScope_strategyLimit.spe line 12) and by the validation
# range (employer-401k-contribution.spe lines 148-150).
#
# We surface the same table here so a caller that does NOT pass an engine
# `combined_401k_limit` gets the SPE-faithful value for the given tax year and
# age instead of a silent hardcode of 69_000. Extend the table each year the
# IRS updates §415(c); keep prior years so multiple tax years stay supported.
# ---------------------------------------------------------------------------
COMBINED_401K_BASE_LIMIT_BY_YEAR: dict[int, int] = {
    2022: 61_000,
    2023: 66_000,
    2024: 69_000,
}
# SPE catch-up amounts (lines 42-81): 6,500 for 2022, 7,500 for 2023/2024.
COMBINED_401K_CATCHUP_BY_YEAR: dict[int, int] = {
    2022: 6_500,
    2023: 7_500,
    2024: 7_500,
}
# Fallback base limit when tax_year is unknown / beyond the table (latest known).
_COMBINED_401K_DEFAULT_BASE = 69_000
_CATCHUP_AGE = 50


def resolve_combined_401k_limit(
    tax_year: int | None,
    age: int | None,
    *,
    engine_value: float | None = None,
) -> float:
    """
    Resolve the per-person combined 401(k) limit.

    Precedence (mirrors SPE): an explicit engine value wins; otherwise use the
    year table + age-50 catch-up (shared401KLimit_GlobalScope.spe lines 39-83).
    """
    if engine_value:
        return float(engine_value)
    base = COMBINED_401K_BASE_LIMIT_BY_YEAR.get(
        int(tax_year) if tax_year is not None else -1,
        _COMBINED_401K_DEFAULT_BASE,
    )
    if age is not None and int(age) >= _CATCHUP_AGE:
        base += COMBINED_401K_CATCHUP_BY_YEAR.get(
            int(tax_year) if tax_year is not None else -1, 7_500
        )
    return float(base)


@dataclass
class RatesInput:
    federal_marginal_rate_pct: float = 24.0
    state_marginal_rate_pct: float = 0.0
    nyc_marginal_rate_pct: float = 0.0
    resident_state: str = ""

    @property
    def total_marginal_rate_pct(self) -> float:
        return (
            self.federal_marginal_rate_pct
            + self.state_marginal_rate_pct
            + self.nyc_marginal_rate_pct
        )


@dataclass
class RetirementBaseline:
    max_401k_contribution_allowed: float = 0.0
    # Engine-provided combined §415(c) limit. When 0/None, it is resolved from
    # tax_year + age via resolve_combined_401k_limit (SPE year table) instead of
    # a silent hardcode. An explicit engine value always wins.
    combined_401k_limit: float = 0.0
    combined_limit_absorbed: float = 0.0
    # SPE combined-limit inputs (shared401KLimit_GlobalScope.spe lines 35-38).
    tax_year: int | None = None
    age: int | None = None

    @property
    def effective_combined_401k_limit(self) -> float:
        """Engine value if given, else SPE year/age table."""
        return resolve_combined_401k_limit(
            self.tax_year, self.age, engine_value=self.combined_401k_limit or None
        )


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
class AssessInput:
    w2: W2Input
    retirement: RetirementBaseline = field(default_factory=RetirementBaseline)
    filing_status_code: int = 1


@dataclass
class EstimateInput:
    w2: W2Input
    retirement: RetirementBaseline = field(default_factory=RetirementBaseline)
    filing_status_code: int = 1
    rates: RatesInput = field(default_factory=RatesInput)
    strategy_change: float | None = None
    tax_year: int | None = None


@dataclass
class ApplicabilityResult:
    applicable: bool
    recommended: bool
    reasons: list[str]
    taxpayer_spouse_or_joint: str
    employer_headroom: float
    employer_match: float
    strategy_change_default: float
    max_401k_contribution_allowed: float
    validation_max: float
    filing_status_code: int
    wg_fed_wages: float
    wages_401k_contribution: float
    nam_emp: str
    prefix: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SavingsBreakdown:
    projected_tax_savings: float
    cash_outlay: float
    marginal_rate_fed: float
    marginal_rate_state: float
    marginal_rate_nyc: float
    marginal_rate_total: float
    strategy_change: float
    baseline_amount: float
    projected_amount: float
    employer_headroom: float
    employer_match: float
    taxpayer_spouse_or_joint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_employer_headroom(retirement: RetirementBaseline) -> float:
    # shared401KLimit_GlobalScope_strategyLimit.spe line 12:
    #   taxPayerMaxAllowedContributionEmployer =
    #       max(combined401KLimitTxp - taxpayerCombined401kContributionLimitAbsorbed, 0)
    # NOTE: NO baseline subtraction (unlike the employee formula on line 9).
    return max(
        retirement.effective_combined_401k_limit - retirement.combined_limit_absorbed,
        0.0,
    )


def compute_match(wg_fed_wages: float, employer_headroom: float) -> float:
    return float(min(wg_fed_wages * 0.05, employer_headroom))


def compute_strategy_change_default(
    max_401k_allowed: float,
    match: float,
    employer_headroom: float,
) -> float:
    return float(_spe_round(min(max_401k_allowed, min(match, employer_headroom))))


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    w2 = inp.w2
    owner = w2.owner
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED
    employer_headroom = compute_employer_headroom(inp.retirement)
    max_401k = float(inp.retirement.max_401k_contribution_allowed or 0)
    match = compute_match(float(w2.wg_fed_wages), employer_headroom)
    wages401k = float(w2.wages_401k_contribution or 0)

    pool_ok = int(w2.delete_next_year) == 0 and float(w2.wg_fed_wages) > 0
    if not pool_ok:
        reasons.append(
            "W-2 must have deleteNextYear == 0 and wgFedwages > 0 (SPE applicableW2s)."
        )

    if owner == "spouse" and not married:
        reasons.append(
            f"Spouse 401(k) ER requires married filing (filingStatus 2 or 5); "
            f"got {inp.filing_status_code}."
        )

    applicable = bool(
        pool_ok
        and wages401k <= employer_headroom + 1e-9
        and (owner != "spouse" or married)
    )
    if pool_ok and wages401k > employer_headroom + 1e-9:
        reasons.append(
            f"wages401kContribution ({wages401k:.2f}) exceeds employer headroom "
            f"({employer_headroom:.2f})."
        )

    no_403b = float(w2.wages_403b_contribution or 0) == 0
    no_457b = float(w2.wg_457b or 0) == 0
    recommended = bool(
        applicable
        and no_403b
        and no_457b
        and match > 0
        and (owner != "spouse" or married)
    )
    if applicable and not no_403b:
        reasons.append("Recommend blocked: wages403bContribution != 0 on this W-2.")
    if applicable and not no_457b:
        reasons.append("Recommend blocked: wg457b != 0 on this W-2.")
    if applicable and match <= 0:
        reasons.append("Recommend blocked: employer match is not > 0.")
    if recommended:
        reasons.append(
            f"Meets 401(k) ER recommend gates (owner={owner}, match={match:.2f})."
        )

    strategy_change_default = compute_strategy_change_default(
        max_401k, match, employer_headroom
    )
    # SPE validation (employer-401k-contribution.spe lines 148-150):
    #   validationMaxContribution = combined401KLimit  (NOT the absorbed Employer value)
    #   validationMax = validationMaxContribution − BASELINE_AMOUNT ; baseline default 0
    validation_max = float(
        max(inp.retirement.effective_combined_401k_limit - 0.0, 0.0)
    )

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        employer_headroom=employer_headroom,
        employer_match=match,
        strategy_change_default=strategy_change_default,
        max_401k_contribution_allowed=max_401k,
        validation_max=validation_max,
        filing_status_code=int(inp.filing_status_code),
        wg_fed_wages=float(w2.wg_fed_wages),
        wages_401k_contribution=wages401k,
        nam_emp=str(w2.nam_emp or ""),
        prefix=int(w2.prefix),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    warnings: list[str] = [
        "Static SPE-faithful estimate — not a live ITA engine recalculation.",
        "Employer 401(k): CASH_OUTLAY is always 0 (employer-funded match).",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(
            w2=inp.w2,
            retirement=inp.retirement,
            filing_status_code=inp.filing_status_code,
        )
    )
    validation_max = float(appl.validation_max or 0)
    validation_exceeded = False
    requested_strategy_change: float | None = None

    if inp.strategy_change is None:
        strategy_change = appl.strategy_change_default
    else:
        requested_strategy_change = float(inp.strategy_change)
        strategy_change = requested_strategy_change
        if strategy_change < 0:
            errors.append("strategy_change must be >= 0.")
        if strategy_change > validation_max + 1e-9:
            validation_exceeded = True
            errors.append(f"Exceeds ${validation_max:,.0f}")
            strategy_change = max(0.0, validation_max)

    if not appl.applicable and not appl.recommended:
        errors.append("W-2 is not applicable or recommended for 401(k) ER under SPE gates.")

    rates = inp.rates
    total = rates.total_marginal_rate_pct
    tax_savings = float(_spe_round(strategy_change * total / 100.0))
    cash_outlay = 0.0

    savings = SavingsBreakdown(
        projected_tax_savings=tax_savings,
        cash_outlay=cash_outlay,
        marginal_rate_fed=rates.federal_marginal_rate_pct,
        marginal_rate_state=rates.state_marginal_rate_pct,
        marginal_rate_nyc=rates.nyc_marginal_rate_pct,
        marginal_rate_total=total,
        strategy_change=strategy_change,
        baseline_amount=0.0,
        projected_amount=strategy_change,
        employer_headroom=appl.employer_headroom,
        employer_match=appl.employer_match,
        taxpayer_spouse_or_joint=appl.taxpayer_spouse_or_joint,
    )

    # SPE employer match: combined absorption only — does NOT write wages401kContribution.
    mutations = [
        {
            "path": (
                "$.projection.return.income.usIncSum.usWageSum.usWageInp"
                f"[?(@.prefix == {inp.w2.prefix})]"
            ),
            "action": "update",
            "fields": {},
            "absorption": {
                "combined401kcontributionlimitabsorbed_delta": strategy_change,
            },
            "secondary_id": "primary",
            "step": "Increase employer 401(k) match absorption (combined only)",
        }
    ]

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "validation_exceeded": validation_exceeded,
            "validation_max": validation_max,
            "strategy_change_requested": requested_strategy_change,
            "applicability": appl.to_dict(),
            "savings": savings.to_dict() if validation_exceeded else None,
            "strategy_change": strategy_change,
            "baseline_amount": 0.0,
            "projected_amount": strategy_change,
            "cash_outlay": cash_outlay if validation_exceeded else 0.0,
            "mutations": [],
        }

    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "validation_exceeded": False,
        "validation_max": validation_max,
        "strategy_change_requested": requested_strategy_change,
        "applicability": appl.to_dict(),
        "savings": savings.to_dict(),
        "strategy_change": strategy_change,
        "baseline_amount": 0.0,
        "projected_amount": strategy_change,
        "cash_outlay": cash_outlay,
        "mutations": mutations,
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


def retirement_from_dict(d: dict[str, Any] | None) -> RetirementBaseline:
    d = d or {}
    return RetirementBaseline(
        max_401k_contribution_allowed=float(
            d.get("max_401k_contribution_allowed") or 0
        ),
        # 0 => resolve from tax_year/age (SPE table); explicit engine value wins.
        combined_401k_limit=float(d.get("combined_401k_limit") or 0),
        combined_limit_absorbed=float(d.get("combined_limit_absorbed") or 0),
        tax_year=None if d.get("tax_year") is None else int(d.get("tax_year")),
        age=None if d.get("age") is None else int(d.get("age")),
    )


def rates_from_dict(d: dict[str, Any] | None) -> RatesInput:
    d = d or {}
    return RatesInput(
        federal_marginal_rate_pct=float(d.get("federal_marginal_rate_pct") or 24),
        state_marginal_rate_pct=float(d.get("state_marginal_rate_pct") or 0),
        nyc_marginal_rate_pct=float(d.get("nyc_marginal_rate_pct") or 0),
        resident_state=str(d.get("resident_state") or ""),
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
            rates=rates_from_dict(payload.get("rates")),
            strategy_change=None if sc is None else float(sc),
            tax_year=payload.get("tax_year"),
        )
    )
