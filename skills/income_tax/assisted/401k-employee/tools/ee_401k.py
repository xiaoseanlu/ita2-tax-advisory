#!/usr/bin/env python3
"""
Deterministic 401(k) Employee Contribution tool (ITA employee-401k-contribution.spe).

Source of truth:
  tax-strategy-content/IndUS/strategies/401k Employee Contribution/employee-401k-contribution.spe
  tax-strategy-content/IndUS/strategies/common/shared401KLimit_*.spe
  project-air/ita-rules/401k-employee-strategy.md
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FILING_MARRIED = {2, 5}


def _spe_round(value: float) -> int:
    """SPE decimalfmt '#' — half-up whole dollars."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Combined §415(c) limit by tax year, with age-50 catch-up.
#
# SPE source: shared401KLimit_GlobalScope.spe lines 39-83. The SPE only
# recomputes combined401KLimit inside `if actualyear < 2023` and adds the
# age-50 catch-up; otherwise it trusts the engine-provided combined limit.
#
# We surface the same table here so a caller that does NOT pass an engine
# `combined_401k_limit` gets the SPE-faithful value for the given tax year and
# age instead of a silent hardcode. This table MUST be extended each year the
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


# States whose personal income tax does NOT conform to the 401(k) deferral
# (SPE added-scope conformity block, employee-401k-contribution.spe line 139).
# Only PA is non-conforming; keep as a set so future non-conformers are explicit.
NON_CONFORMING_STATES: frozenset[str] = frozenset({"PA"})


@dataclass
class RatesInput:
    federal_marginal_rate_pct: float = 24.0
    state_marginal_rate_pct: float = 0.0
    nyc_marginal_rate_pct: float = 0.0
    resident_state: str = ""
    # Recommendation scope uses full rates; added scope zeros PA state/NYC.
    apply_pa_nonconforming: bool = True

    @property
    def non_conforming_state(self) -> bool:
        return (
            self.apply_pa_nonconforming
            and (self.resident_state or "").upper() in NON_CONFORMING_STATES
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
    """Engine / base-return fields from shared401KLimit_GlobalScope*.spe (per person)."""

    max_401k_contribution_allowed: float = 0.0  # engine max401kContributionAllowed
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
    """One W-2 activity for 401(k) EE strategy."""

    delete_next_year: int = 0
    wg_tp_sp: int = 0  # 0=taxpayer, 1=spouse
    nam_emp: str = ""
    prefix: int = 1
    wg_fed_wages: float = 0.0  # projection wages (STRATEGY_CHANGE default)
    # SPE validationMax prefers base wages when present, else projection.
    base_wg_fed_wages: float | None = None
    wages_401k_contribution: float = 0.0
    wages_403b_contribution: float = 0.0
    wg_457b: float = 0.0

    @property
    def owner(self) -> str:
        return "spouse" if int(self.wg_tp_sp) == 1 else "taxpayer"

    @property
    def validation_wages(self) -> float:
        if self.base_wg_fed_wages is not None:
            return float(self.base_wg_fed_wages)
        return float(self.wg_fed_wages)


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
    employee_max_401k_contribution: float
    strategy_change_default: float
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
    employee_max_401k_contribution: float
    taxpayer_spouse_or_joint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_employee_headroom(retirement: RetirementBaseline) -> float:
    """
    shared401KLimit_GlobalScope_strategyLimit.spe — employee formula:

      min(
        max(max401k − baseline_sum − absorbedEmployee, 0),
        max(combinedLimit − baseline_sum − absorbedCombined, 0)
      )
    """
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
    """
    Validation headroom does NOT subtract absorption counters
    (shared401KLimit_GlobalScope_validation.spe).
    """
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
    """
    employee-401k-contribution.spe global + recommendation gates for one W-2.
    """
    w2 = inp.w2
    owner = w2.owner
    reasons: list[str] = []
    married = int(inp.filing_status_code) in FILING_MARRIED
    headroom = compute_employee_headroom(inp.retirement)
    validation_headroom = compute_validation_employee_headroom(inp.retirement)

    pool_ok = int(w2.delete_next_year) == 0 and float(w2.wg_fed_wages) > 0
    if not pool_ok:
        reasons.append(
            "W-2 must have deleteNextYear == 0 and wgFedwages > 0 "
            "(SPE applicableW2s)."
        )

    if owner == "spouse" and not married:
        reasons.append(
            f"Spouse 401(k) EE requires married filing (SPE marriedMAGI: "
            f"filingStatus 2 or 5); got {inp.filing_status_code}."
        )

    # Applicable: wages401kContribution <= person MaxAllowedContributionEmployee
    # (SPE applicableTaxPayer401k / applicableSpouse401k — independent of recommend)
    contrib = float(w2.wages_401k_contribution or 0)
    applicable = bool(
        pool_ok
        and contrib <= headroom + 1e-9
        and (owner != "spouse" or married)
    )
    if pool_ok and contrib > headroom + 1e-9:
        reasons.append(
            f"wages401kContribution ({contrib:.2f}) exceeds employee headroom "
            f"({headroom:.2f})."
        )

    # Recommend: SPE taxPayer401k / spouse401k — independent of applicable set.
    # Requires no 403b/457b and headroom > 0 (not contrib <= headroom).
    no_403b = float(w2.wages_403b_contribution or 0) == 0
    no_457b = float(w2.wg_457b or 0) == 0
    recommended = bool(
        pool_ok
        and no_403b
        and no_457b
        and headroom > 0
        and (owner != "spouse" or married)
    )
    if pool_ok and not no_403b:
        reasons.append("Recommend blocked: wages403bContribution != 0 on this W-2.")
    if pool_ok and not no_457b:
        reasons.append("Recommend blocked: wg457b != 0 on this W-2.")
    if pool_ok and headroom <= 0:
        reasons.append("Recommend blocked: employee headroom is not > 0.")
    if recommended:
        reasons.append(
            f"Meets 401(k) EE recommend gates (owner={owner}, "
            f"employer={w2.nam_emp or '—'}, headroom={headroom:.2f})."
        )

    strategy_change_default = float(min(float(w2.wg_fed_wages), headroom))
    # SPE: validationMax = min(baseWages|projectionWages, Validation*Employee)
    validation_max = float(min(w2.validation_wages, validation_headroom))

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        employee_max_401k_contribution=headroom,
        strategy_change_default=strategy_change_default,
        validation_max=validation_max,
        filing_status_code=int(inp.filing_status_code),
        wg_fed_wages=float(w2.wg_fed_wages),
        wages_401k_contribution=contrib,
        nam_emp=str(w2.nam_emp or ""),
        prefix=int(w2.prefix),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    """
    Part 2 — SPE savings (recommendation / added scope):

      PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE × MARGINAL_RATE_TOTAL / 100)
      CASH_OUTLAY = STRATEGY_CHANGE − PROJECTED_TAX_SAVINGS
                    [+ totalCashOutlayAdjustments in added scope]
    """
    warnings: list[str] = [
        "This is a static SPE-faithful estimate, not a live ITA engine recalculation.",
        "max401kContributionAllowed and combined401KLimit are engine-computed — pass them.",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(
            w2=inp.w2,
            retirement=inp.retirement,
            filing_status_code=inp.filing_status_code,
        )
    )
    headroom = appl.employee_max_401k_contribution
    validation_max = float(appl.validation_max or 0)
    baseline = float(inp.w2.wages_401k_contribution or 0)
    requested_strategy_change: float | None = None
    validation_exceeded = False

    if inp.strategy_change is None:
        # SPE recommendation default: min(wgFedwages, employeeMax401kContribution)
        strategy_change = appl.strategy_change_default
    else:
        requested_strategy_change = float(inp.strategy_change)
        strategy_change = requested_strategy_change
        if strategy_change < 0:
            errors.append("strategy_change must be >= 0.")
        # SPE validation scope:
        #   assert STRATEGY_CHANGE in_range 0 .. validationMax
        # ITA UI copy when over: "Exceeds $X" (including validationMax == 0)
        if strategy_change > validation_max + 1e-9:
            validation_exceeded = True
            errors.append(f"Exceeds ${validation_max:,.0f}")
            # Do not credit savings above SPE validationMax (ITA totals stay 0).
            strategy_change = max(0.0, validation_max)
        elif strategy_change > headroom + 1e-9:
            warnings.append(
                f"strategy_change ({strategy_change:.2f}) exceeds employee headroom "
                f"({headroom:.2f})."
            )

    # SPE can recommend without applicable; allow estimate on either list.
    if not appl.applicable and not appl.recommended:
        errors.append("W-2 is not applicable or recommended for 401(k) EE under SPE gates.")

    rates = inp.rates
    if rates.non_conforming_state:
        warnings.append(
            "Resident state PA — SPE added scope zeros state/NYC marginal for savings."
        )

    total = rates.total_marginal_rate_pct
    tax_savings = float(_spe_round(strategy_change * total / 100.0))
    cash_outlay = float(
        strategy_change - tax_savings + float(inp.total_cash_outlay_adjustments or 0)
    )
    projected_amount = strategy_change + baseline

    path = (
        "$.projection.return.income.usIncSum.usWageSum.usWageInp"
        f"[?(@.prefix == {inp.w2.prefix})]"
    )

    savings = SavingsBreakdown(
        projected_tax_savings=tax_savings,
        cash_outlay=cash_outlay,
        marginal_rate_fed=rates.federal_marginal_rate_pct,
        marginal_rate_state=(
            0.0 if rates.non_conforming_state else rates.state_marginal_rate_pct
        ),
        marginal_rate_nyc=(
            0.0 if rates.non_conforming_state else rates.nyc_marginal_rate_pct
        ),
        marginal_rate_total=total,
        strategy_change=strategy_change,
        baseline_amount=baseline,
        projected_amount=projected_amount,
        employee_max_401k_contribution=headroom,
        taxpayer_spouse_or_joint=appl.taxpayer_spouse_or_joint,
    )

    # SPE: over-validationMax is invalid (ITA red "Exceeds $X", totals 0).
    # Still return capped savings so the hub can show max-allowed math.
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
            "baseline_amount": baseline,
            "projected_amount": projected_amount,
            "cash_outlay": cash_outlay if validation_exceeded else None,
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
        "baseline_amount": baseline,
        "projected_amount": projected_amount,
        "cash_outlay": cash_outlay,
        "mutations": [
            {
                "path": path,
                "action": "update",
                "fields": {
                    "wages401kContribution_delta": strategy_change,
                    "wgFedwages_delta": -strategy_change,
                },
                "absorption": {
                    "employee401kcontributionlimitabsorbed_delta": strategy_change,
                    "combined401kcontributionlimitabsorbed_delta": strategy_change,
                },
                "secondary_id": "primary",
                "step": "Increase W-2 401(k) EE deferral; reduce Box 1 wages",
            }
        ],
    }


def w2_from_dict(d: dict[str, Any]) -> W2Input:
    base_raw = d.get("base_wg_fed_wages", d.get("base_wages"))
    return W2Input(
        delete_next_year=int(d.get("delete_next_year") or 0),
        wg_tp_sp=int(d.get("wg_tp_sp") or 0),
        nam_emp=str(d.get("nam_emp") or ""),
        prefix=int(d.get("prefix") or 1),
        wg_fed_wages=float(d.get("wg_fed_wages") or 0),
        base_wg_fed_wages=None if base_raw is None or base_raw == "" else float(base_raw),
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
        apply_pa_nonconforming=bool(d.get("apply_pa_nonconforming", True)),
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
