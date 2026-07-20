#!/usr/bin/env python3
"""Deterministic 403(b) Employee Contribution tool (employee-403b-contribution.spe)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FILING_MARRIED = {2, 5}
# States whose personal income tax does NOT conform to the 403(b) deferral.
# SPE added-scope conformity block, employee-403b-contribution.spe line 107:
#   if {((resState == 'NJ') or (resState == 'PA'))}: nonConformingState = true
# NOTE: unlike 401k (PA-only), the 403b SPE lists BOTH NJ and PA.
NON_CONFORMING_STATES: frozenset[str] = frozenset({"PA", "NJ"})


def _spe_round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Combined §415(c) limit by tax year, with age-50 catch-up.
#
# SPE source: shared401KLimit_GlobalScope.spe lines 39-83 (included at the top
# of employee-403b-contribution.spe line 13, and again in added scope line 97).
# The SPE only recomputes combined401KLimit inside `if actualyear < 2023` and
# adds the age-50 catch-up; otherwise it trusts the engine-provided combined
# limit (combined401KLimitTxp / combined401KLimitSps).
#
# We surface the same table here so a caller that does NOT pass an engine
# `combined_401k_limit` gets the SPE-faithful value for the given tax year and
# age instead of a silent hardcode. Extend this table each year the IRS updates
# §415(c); keep prior years so multiple tax years stay supported.
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
    Resolve the per-person combined 401(k)/403(b) §415(c) limit.

    Precedence (mirrors SPE): an explicit engine value wins; otherwise use the
    year table + age-50 catch-up.
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
    apply_pa_nj_nonconforming: bool = True

    @property
    def non_conforming_state(self) -> bool:
        return self.apply_pa_nj_nonconforming and (
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
class RetirementBaseline:
    max_401k_contribution_allowed: float = 0.0
    # Engine-provided combined §415(c) limit. When 0/None, it is resolved from
    # tax_year + age via resolve_combined_401k_limit (SPE year table).
    combined_401k_limit: float = 0.0
    total_401k: float = 0.0
    total_roth_401k: float = 0.0
    total_403b: float = 0.0
    total_roth_403b: float = 0.0
    baseline_solo401k: float = 0.0
    employee_limit_absorbed: float = 0.0
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
    wages_403b_contribution: float = 0.0

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
    total_cash_outlay_adjustments: float = 0.0
    tax_year: int | None = None


@dataclass
class ApplicabilityResult:
    applicable: bool
    recommended: bool
    reasons: list[str]
    taxpayer_spouse_or_joint: str
    employee_headroom: float
    strategy_change_default: float
    validation_max: float
    filing_status_code: int
    wg_fed_wages: float
    wages_403b_contribution: float
    nam_emp: str
    prefix: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_employee_headroom(retirement: RetirementBaseline) -> float:
    baseline_sum = (
        retirement.total_401k
        + retirement.total_roth_401k
        + retirement.total_403b
        + retirement.total_roth_403b
        + retirement.baseline_solo401k
    )
    a = max(
        retirement.max_401k_contribution_allowed
        - baseline_sum
        - retirement.employee_limit_absorbed,
        0.0,
    )
    b = max(
        retirement.effective_combined_401k_limit
        - baseline_sum
        - retirement.combined_limit_absorbed,
        0.0,
    )
    return float(min(a, b))


def compute_validation_employee_headroom(retirement: RetirementBaseline) -> float:
    """SPE validation — no absorption subtraction."""
    baseline_sum = (
        retirement.total_401k
        + retirement.total_roth_401k
        + retirement.total_403b
        + retirement.total_roth_403b
        + retirement.baseline_solo401k
    )
    a = max(retirement.max_401k_contribution_allowed - baseline_sum, 0.0)
    b = max(retirement.effective_combined_401k_limit - baseline_sum, 0.0)
    return float(min(a, b))


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    w2 = inp.w2
    owner = w2.owner
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED
    headroom = compute_employee_headroom(inp.retirement)
    validation_headroom = compute_validation_employee_headroom(inp.retirement)
    contrib403b = float(w2.wages_403b_contribution or 0)

    pool_ok = int(w2.delete_next_year) == 0 and float(w2.wg_fed_wages) > 0
    if not pool_ok:
        reasons.append(
            "W-2 must have deleteNextYear == 0 and wgFedwages > 0 (SPE applicableW2s)."
        )

    if owner == "spouse" and not married:
        reasons.append(
            f"Spouse 403(b) EE requires married filing (filingStatus 2 or 5); "
            f"got {inp.filing_status_code}."
        )

    applicable = bool(
        pool_ok and headroom > 0 and (owner != "spouse" or married)
    )
    if pool_ok and headroom <= 0:
        reasons.append("Applicable blocked: employee headroom is not > 0.")

    recommended = bool(
        applicable and contrib403b > 0 and headroom > 0 and (owner != "spouse" or married)
    )
    if applicable and contrib403b <= 0:
        reasons.append("Recommend blocked: wages403bContribution is not > 0.")
    if recommended:
        reasons.append(
            f"Meets 403(b) EE recommend gates (owner={owner}, headroom={headroom:.2f})."
        )

    strategy_change_default = float(min(float(w2.wg_fed_wages), headroom))
    validation_max = float(min(float(w2.wg_fed_wages), validation_headroom))

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        employee_headroom=headroom,
        strategy_change_default=strategy_change_default,
        validation_max=validation_max,
        filing_status_code=int(inp.filing_status_code),
        wg_fed_wages=float(w2.wg_fed_wages),
        wages_403b_contribution=contrib403b,
        nam_emp=str(w2.nam_emp or ""),
        prefix=int(w2.prefix),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    warnings: list[str] = [
        "Static SPE-faithful estimate — not a live ITA engine recalculation.",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(
            w2=inp.w2,
            retirement=inp.retirement,
            filing_status_code=inp.filing_status_code,
        )
    )
    baseline = float(inp.w2.wages_403b_contribution or 0)
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
        errors.append("W-2 is not applicable or recommended for 403(b) EE under SPE gates.")

    rates = inp.rates
    if rates.non_conforming_state:
        warnings.append(
            f"Resident state {rates.resident_state.upper()} — SPE added scope zeros "
            "state/NYC marginal for savings."
        )

    total = rates.total_marginal_rate_pct
    tax_savings = float(_spe_round(strategy_change * total / 100.0))
    cash_outlay = float(
        strategy_change
        - tax_savings
        + float(inp.total_cash_outlay_adjustments or 0)
    )
    projected_amount = strategy_change + baseline

    savings = {
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
        "projected_amount": projected_amount,
        "employee_headroom": appl.employee_headroom,
        "taxpayer_spouse_or_joint": appl.taxpayer_spouse_or_joint,
    }

    mutations = [
        {
            "path": (
                "$.projection.return.income.usIncSum.usWageSum.usWageInp"
                f"[?(@.prefix == {inp.w2.prefix})]"
            ),
            "action": "update",
            "fields": {
                "wages403bContribution_delta": strategy_change,
                "wgFedwages_delta": -strategy_change,
            },
            "absorption": {
                "employee401kcontributionlimitabsorbed_delta": strategy_change,
                "combined401kcontributionlimitabsorbed_delta": strategy_change,
            },
            "secondary_id": "primary",
            "step": "Increase W-2 403(b) EE deferral; reduce Box 1 wages",
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
            "savings": savings if validation_exceeded else None,
            "strategy_change": strategy_change,
            "baseline_amount": baseline,
            "projected_amount": projected_amount,
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
        "savings": savings,
        "strategy_change": strategy_change,
        "baseline_amount": baseline,
        "projected_amount": projected_amount,
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
        wages_403b_contribution=float(d.get("wages_403b_contribution") or 0),
    )


def retirement_from_dict(d: dict[str, Any] | None) -> RetirementBaseline:
    d = d or {}
    return RetirementBaseline(
        max_401k_contribution_allowed=float(
            d.get("max_401k_contribution_allowed") or 0
        ),
        # 0 => resolve from tax_year/age (SPE table); explicit engine value wins.
        combined_401k_limit=float(d.get("combined_401k_limit") or 0),
        total_401k=float(d.get("total_401k") or 0),
        total_roth_401k=float(d.get("total_roth_401k") or 0),
        total_403b=float(d.get("total_403b") or 0),
        total_roth_403b=float(d.get("total_roth_403b") or 0),
        baseline_solo401k=float(d.get("baseline_solo401k") or 0),
        employee_limit_absorbed=float(d.get("employee_limit_absorbed") or 0),
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
        apply_pa_nj_nonconforming=bool(d.get("apply_pa_nj_nonconforming", True)),
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
            total_cash_outlay_adjustments=float(
                payload.get("total_cash_outlay_adjustments") or 0
            ),
            tax_year=payload.get("tax_year"),
        )
    )
