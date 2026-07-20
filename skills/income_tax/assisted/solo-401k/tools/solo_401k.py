#!/usr/bin/env python3
"""
Deterministic Solo 401(k) contribution tool (ITA Solo401k.spe logic).

Source of truth:
  tax-strategy-content/IndUS/strategies/Solo 401k Contribution/Solo401k.spe
  tax-strategy-content/IndUS/strategies/common/shared401KLimit_*.spe
  project-air/ita-rules/solo-401k-strategy.md
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any


# Filing status codes from SPE (marriedMAGI = 2 or 5)
FILING_SINGLEISH = {1, 3, 4}
FILING_MARRIED = {2, 5}


# ---------------------------------------------------------------------------
# Combined §415(c) 401(k) limit by tax year + age-50 catch-up.
# SPE: shared401KLimit_GlobalScope.spe lines 39-83 (the same %included file the
# Solo401k.spe pulls in at lines 29-31). base: 2022=61000, 2023=66000,
# 2024=69000; age>=50 catch-up: 2022 +6500, 2023/2024 +7500.
#
# Mirrors ee_401k.resolve_combined_401k_limit so a caller that does NOT pass an
# engine `combined_401k_limit` gets the SPE-faithful year/age value instead of a
# silent hardcode. Extend this table each year the IRS updates §415(c).
# ---------------------------------------------------------------------------
COMBINED_401K_BASE_LIMIT_BY_YEAR: dict[int, int] = {
    2022: 61_000,
    2023: 66_000,
    2024: 69_000,
}
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

    Precedence (mirrors SPE shared401KLimit_GlobalScope.spe): an explicit engine
    value wins; otherwise use the year table + age-50 catch-up.
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


def _spe_round(value: float) -> int:
    """SPE decimalfmt '#' — whole dollars, banker's (half-even) rounding.

    The SPE Solo401k.spe test_suite anchor (line 385) asserts 6500 @ 49.30%
    -> 3204 (from an exact 3204.50), which only holds under HALF_EVEN, not
    HALF_UP. See ita-rules/SPE-PYTHON-FIDELITY-AUDIT.md.
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


@dataclass
class RatesInput:
    federal_marginal_rate_pct: float = 24.0
    state_marginal_rate_pct: float = 0.0
    nyc_marginal_rate_pct: float = 0.0
    resident_state: str = ""

    @property
    def non_conforming_state(self) -> bool:
        # Solo401k.spe added scope: PA zeros state/NYC for savings
        return (self.resident_state or "").upper() == "PA"

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
    """Engine / base-return fields used by shared401KLimit_*.spe."""

    max_solo401k_contribution_allowed: float = 0.0
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
class PersonInput:
    """One person (taxpayer or spouse) for Solo 401(k)."""

    taxpayer_spouse_or_joint: str = "taxpayer"  # taxpayer | spouse
    filing_status_code: int = 1
    all_se_income: float = 0.0
    earned_income: float = 0.0
    sep_ira: float = 0.0
    solo_elective_deferral: float = 0.0  # projection tpSEElectDef / spsEElectDef
    solo401k_contribution: float = 0.0  # ITA summary (display baseline)
    solo401k_catchup: float = 0.0
    # Simplified SPE Gate B: qualifying solo business without wages (or S-Corp+W2)
    biz_exists_without_wages: bool = True
    opposite_ein_wage_matches: bool = False
    # SPE applicableSolo401k first filter: seIncome || sCorpWages (not earned-alone)
    scorp_wages_present: bool = False


@dataclass
class AssessInput:
    person: PersonInput
    retirement: RetirementBaseline = field(default_factory=RetirementBaseline)


@dataclass
class EstimateInput:
    person: PersonInput
    retirement: RetirementBaseline = field(default_factory=RetirementBaseline)
    rates: RatesInput = field(default_factory=RatesInput)
    strategy_change: float | None = None  # advisor override; default = headroom
    tax_year: int | None = None


@dataclass
class ApplicabilityResult:
    applicable: bool
    recommended: bool
    reasons: list[str]
    taxpayer_spouse_or_joint: str
    max_allowed_contribution: float
    validation_max: float
    filing_status_code: int
    all_se_income: float
    earned_income: float

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
    max_allowed_contribution: float
    taxpayer_spouse_or_joint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_employee_headroom(retirement: RetirementBaseline) -> float:
    """
    shared401KLimit_GlobalScope_strategyLimit.spe employee formula:

      min(
        max(maxSolo − baseline401k − … − absorbedEmployee, 0),
        max(combinedLimit − same baselines − absorbedCombined, 0)
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
        retirement.max_solo401k_contribution_allowed
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
    """SPE validation formula — no absorption subtraction."""
    baseline_sum = (
        retirement.total_401k
        + retirement.total_roth_401k
        + retirement.total_403b
        + retirement.total_roth_403b
        + retirement.baseline_solo401k
    )
    a = max(retirement.max_solo401k_contribution_allowed - baseline_sum, 0.0)
    b = max(retirement.effective_combined_401k_limit - baseline_sum, 0.0)
    return float(min(a, b))


def assess_applicability(inp: AssessInput) -> ApplicabilityResult:
    """
    Solo401k.spe gates:

    Applicable first filter: seIncome > 0 OR sCorpWages (earned-alone is NOT enough).
    Biz: no-wages biz OR opposite-EIN (applicable); recommend requires no-wages biz only.
    Spouse: married filing (2|5).
    Recommended: maxAllowed > 0 AND SEP rule AND no-wages biz (not opposite-EIN-only).
    """
    p = inp.person
    owner = (p.taxpayer_spouse_or_joint or "taxpayer").lower()
    if owner not in ("taxpayer", "spouse"):
        owner = "taxpayer"

    reasons: list[str] = []
    max_allowed = compute_employee_headroom(inp.retirement)
    validation_max = compute_validation_employee_headroom(inp.retirement)
    married = int(p.filing_status_code) in FILING_MARRIED

    # SPE ~101: seIncome || sCorpWages — not earnedIncome alone
    pool_income = float(p.all_se_income) > 0 or bool(p.scorp_wages_present)
    biz_no_wages = bool(p.biz_exists_without_wages)
    opposite = bool(p.opposite_ein_wage_matches)
    biz_for_applicable = biz_no_wages or opposite

    if owner == "spouse" and not married:
        reasons.append(
            f"Spouse Solo 401(k) requires married filing status (SPE marriedMAGI: "
            f"filingStatus 2 or 5); got {p.filing_status_code}."
        )

    applicable = bool(
        pool_income and biz_for_applicable and (owner != "spouse" or married)
    )
    if not pool_income:
        reasons.append(
            "Need all_se_income > 0 or scorp_wages_present "
            "(SPE: earnedIncome alone is not enough for applicableSolo401k)."
        )
    if not biz_for_applicable:
        reasons.append(
            "No qualifying solo business without wages (and no opposite-EIN wage match)."
        )

    sep_ok = p.sep_ira == 0 or p.solo_elective_deferral > 0
    # SPE recommend requires bizExistsWithoutWagesAndScorp — NOT opposite-EIN alone
    recommended = bool(
        applicable and biz_no_wages and max_allowed > 0 and sep_ok
    )
    if applicable and not biz_no_wages and opposite:
        reasons.append(
            "Recommend blocked: opposite-EIN match is applicable-only in SPE "
            "(recommend requires biz without wages)."
        )
    if applicable and max_allowed <= 0:
        reasons.append(f"maxAllowedContribution ({max_allowed:.2f}) is not > 0.")
    if applicable and not sep_ok:
        reasons.append(
            "SEP-IRA conflict: sepIRA > 0 and solo elective deferral is 0 "
            "(SPE blocks recommend)."
        )
    if recommended:
        reasons.append(
            f"Meets Solo 401(k) recommend gates (owner={owner}, "
            f"headroom={max_allowed:.2f})."
        )

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        taxpayer_spouse_or_joint=owner,
        max_allowed_contribution=max_allowed,
        validation_max=validation_max,
        filing_status_code=int(p.filing_status_code),
        all_se_income=float(p.all_se_income),
        earned_income=float(p.earned_income),
    )


def estimate_savings(inp: EstimateInput) -> dict[str, Any]:
    """
    Part 2 — SPE savings:

      PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE × MARGINAL_RATE_TOTAL / 100)
      CASH_OUTLAY = STRATEGY_CHANGE − PROJECTED_TAX_SAVINGS
    """
    warnings: list[str] = [
        "This is a static SPE-faithful estimate, not a live ITA engine recalculation.",
        "maxSolo401kContributionAllowed is engine-computed; pass it — do not invent.",
    ]
    errors: list[str] = []
    appl = assess_applicability(
        AssessInput(person=inp.person, retirement=inp.retirement)
    )
    max_allowed = appl.max_allowed_contribution
    validation_max = float(appl.validation_max or 0)
    baseline = float(inp.person.solo401k_contribution + inp.person.solo401k_catchup)
    validation_exceeded = False
    requested_strategy_change: float | None = None

    if inp.strategy_change is None:
        strategy_change = max_allowed
    else:
        requested_strategy_change = float(inp.strategy_change)
        strategy_change = requested_strategy_change
        if strategy_change < 0:
            errors.append("strategy_change must be >= 0.")
        if strategy_change > validation_max + 1e-9:
            validation_exceeded = True
            errors.append(f"Exceeds ${validation_max:,.0f}")
            strategy_change = max(0.0, validation_max)
        elif strategy_change > max_allowed + 1e-9:
            warnings.append(
                f"strategy_change ({strategy_change:.2f}) exceeds SPE headroom "
                f"({max_allowed:.2f})."
            )

    if not appl.applicable and not appl.recommended:
        errors.append("Person is not applicable or recommended for Solo 401(k) under SPE gates.")

    rates = inp.rates
    if rates.non_conforming_state:
        warnings.append(
            "Resident state PA — SPE added scope zeros state/NYC marginal for savings."
        )

    total = rates.total_marginal_rate_pct
    tax_savings = float(_spe_round(strategy_change * total / 100.0))
    cash_outlay = float(strategy_change - tax_savings)
    projected_amount = strategy_change + baseline

    owner = appl.taxpayer_spouse_or_joint
    if owner == "spouse":
        path = (
            "$.projection.return.adjustments.usAdjSum.usAdjIncInp"
            ".sepsimpleQualifiedPlansspouse.spsEElectDef"
        )
    else:
        path = (
            "$.projection.return.adjustments.usAdjSum.usAdjIncInp"
            ".sepsimpleQualifiedPlansTaxpayer.tpSEElectDef"
        )

    savings = SavingsBreakdown(
        projected_tax_savings=tax_savings,
        cash_outlay=cash_outlay,
        marginal_rate_fed=rates.federal_marginal_rate_pct,
        marginal_rate_state=0.0 if rates.non_conforming_state else rates.state_marginal_rate_pct,
        marginal_rate_nyc=0.0 if rates.non_conforming_state else rates.nyc_marginal_rate_pct,
        marginal_rate_total=total,
        strategy_change=strategy_change,
        baseline_amount=baseline,
        projected_amount=projected_amount,
        max_allowed_contribution=max_allowed,
        taxpayer_spouse_or_joint=owner,
    )

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
                "fields": {"delta": strategy_change},
                "secondary_id": "primary",
                "step": "Add Solo 401(k) elective deferral",
            }
        ],
    }


def person_from_dict(d: dict[str, Any]) -> PersonInput:
    return PersonInput(
        taxpayer_spouse_or_joint=str(d.get("taxpayer_spouse_or_joint") or "taxpayer"),
        filing_status_code=int(d.get("filing_status_code") or 1),
        all_se_income=float(d.get("all_se_income") or 0),
        earned_income=float(d.get("earned_income") or 0),
        sep_ira=float(d.get("sep_ira") or 0),
        solo_elective_deferral=float(d.get("solo_elective_deferral") or 0),
        solo401k_contribution=float(d.get("solo401k_contribution") or 0),
        solo401k_catchup=float(d.get("solo401k_catchup") or 0),
        biz_exists_without_wages=bool(d.get("biz_exists_without_wages", True)),
        opposite_ein_wage_matches=bool(d.get("opposite_ein_wage_matches", False)),
        scorp_wages_present=bool(d.get("scorp_wages_present", False)),
    )


def retirement_from_dict(d: dict[str, Any] | None) -> RetirementBaseline:
    d = d or {}
    return RetirementBaseline(
        max_solo401k_contribution_allowed=float(
            d.get("max_solo401k_contribution_allowed") or 0
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
    )


def assess_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    person = person_from_dict(payload.get("person") or {})
    retirement = retirement_from_dict(payload.get("retirement"))
    return assess_applicability(
        AssessInput(person=person, retirement=retirement)
    ).to_dict()


def savings_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    person = person_from_dict(payload.get("person") or {})
    retirement = retirement_from_dict(payload.get("retirement"))
    rates = rates_from_dict(payload.get("rates"))
    sc = payload.get("strategy_change")
    return estimate_savings(
        EstimateInput(
            person=person,
            retirement=retirement,
            rates=rates,
            strategy_change=None if sc is None else float(sc),
            tax_year=payload.get("tax_year"),
        )
    )
