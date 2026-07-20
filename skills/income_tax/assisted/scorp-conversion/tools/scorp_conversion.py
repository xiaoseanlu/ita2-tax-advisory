#!/usr/bin/env python3
"""
Deterministic S-Corp conversion tool (ita_002 / ITA Scorp SPE logic).

Governance: Tools hold thresholds, rates, and write formulas.
Skills must NOT embed this logic — they orchestrate this module + LLM judgment.

Source of truth for rules:
  tax-strategy-content/IndUS/strategies/Scorp/*.spe
  project-air/skills/income_tax/assisted/scorp-conversion/STRATEGY.md
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


# --- Indexed / statutory defaults (tool-owned; override via RatesInput) ---
# SPE reads employee-only rates from usITAIndexedAmount, then applies (rate * 2)
# for combined EE+ER. Defaults must be employee-only — not 12.4% / 2.9%.
DEFAULT_NET_EARNINGS_RATIO = 0.9235  # SE computation factor (netEarningRatio)
DEFAULT_SS_RATE = 0.062  # marginalRateSocialSecurity (employee); SPE does rate * 2
DEFAULT_MED_RATE = 0.0145  # marginalRateMedicare (employee); SPE does rate * 2
DEFAULT_SS_WAGE_BASE = 176_100  # maxSSwage — override per tax year when known
DEFAULT_OWNERSHIP_RECOMMEND_PCT = 50.0
DEFAULT_MIN_NET_EARNINGS = 0.0  # applicability: netEarnings > 0


def _spe_round(value: float) -> int:
    """SPE math:round — half away from zero / half-up for positives."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class RatesInput:
    """Tax-year / engine-indexed amounts. Prefer values from the tax engine when available."""

    net_earnings_ratio: float = DEFAULT_NET_EARNINGS_RATIO
    ss_rate: float = DEFAULT_SS_RATE
    med_rate: float = DEFAULT_MED_RATE
    ss_wage_base: float = DEFAULT_SS_WAGE_BASE
    federal_marginal_rate_pct: float = 24.0  # percent points, e.g. 24.0
    state_marginal_rate_pct: float = 0.0
    nyc_marginal_rate_pct: float = 0.0
    income_already_taxed_by_ss: float = 0.0
    # Owner's ALL SE income (pre netEarningRatio) from usITA*Items.allSEIncome —
    # includes other Schedule C / F / partnership SE, not just the activity being converted.
    starting_se_income: float = 0.0

    @property
    def total_marginal_rate_pct(self) -> float:
        return (
            self.federal_marginal_rate_pct
            + self.state_marginal_rate_pct
            + self.nyc_marginal_rate_pct
        )


@dataclass
class BusinessActivityInput:
    """One SE business activity (Schedule C / F / partnership SE)."""

    activity_id: str
    source: str  # Schedule C | Schedule F | Partnership | Schedule E | SCorp
    name: str
    net_income: float
    is_se_biz: bool = True
    ownership_pct: float = 100.0
    taxpayer_spouse_or_joint: str = "taxpayer"  # taxpayer | spouse | joint
    prefix: int = 1
    # Optional engine-provided; otherwise derived
    net_earnings: float | None = None

    def resolved_net_earnings(self, rates: RatesInput) -> float:
        if self.net_earnings is not None:
            return float(self.net_earnings)
        return round(self.net_income * rates.net_earnings_ratio)


@dataclass
class ApplyScorpInput:
    """
    Required + optional inputs to APPLY the conversion.

    Required:
      - activity (which SE business)
      - reasonable_wage (advisor-entered; tool never invents this)
      - rates (at least federal_marginal_rate_pct recommended)

    Optional:
      - tax_year, filing_status (for narration / LLM context, not core math)
    """

    activity: BusinessActivityInput
    reasonable_wage: float
    rates: RatesInput = field(default_factory=RatesInput)
    tax_year: int | None = None
    filing_status: str | None = None
    scenario_id: str | None = None


@dataclass
class ApplicabilityResult:
    applicable: bool
    recommended: bool
    reasons: list[str]
    net_earnings: float
    ownership_pct: float
    net_income: float
    source: str
    activity_id: str
    taxpayer_spouse_or_joint: str = "taxpayer"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectionMutation:
    """Declarative write the planning/tax layer should apply."""

    path: str
    action: str  # update | create | flag
    fields: dict[str, Any]
    secondary_id: str
    step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SavingsBreakdown:
    se_income_back_out_tax_savings: float
    se_tax_reduction: float
    se_deduction_lost_tax_cost: float
    wages_income_tax_cost: float
    wages_fica: float
    scorp_ordinary_income_tax_cost: float
    employer_fica_half_tax_savings: float
    projected_tax_savings: float
    cash_outlay: float
    ss_wage_base: float = 0.0
    income_already_taxed_by_ss: float = 0.0
    ss_headroom: float = 0.0
    starting_se_income: float = 0.0
    starting_se_net_earnings: float = 0.0
    change_in_ss_income: float = 0.0
    se_subject_to_ss: float = 0.0
    taxpayer_spouse_or_joint: str = "taxpayer"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApplyScorpResult:
    ok: bool
    errors: list[str]
    applicability: ApplicabilityResult | None
    reasonable_wage: float
    net_income: float
    wages_allocated: float
    scorp_ordinary_income: float
    wages_fica: float
    wages_fica_employer_half: float
    savings: SavingsBreakdown | None
    mutations: list[ProjectionMutation]
    primary_strategy_change: float  # −net_income per SPE
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "applicability": self.applicability.to_dict() if self.applicability else None,
            "reasonable_wage": self.reasonable_wage,
            "net_income": self.net_income,
            "wages_allocated": self.wages_allocated,
            "scorp_ordinary_income": self.scorp_ordinary_income,
            "wages_fica": self.wages_fica,
            "wages_fica_employer_half": self.wages_fica_employer_half,
            "savings": self.savings.to_dict() if self.savings else None,
            "mutations": [m.to_dict() for m in self.mutations],
            "primary_strategy_change": self.primary_strategy_change,
            "warnings": self.warnings,
        }


def _schedule_container(source: str) -> str:
    mapping = {
        "Schedule C": "usBusIncSum.usBusIncInp",
        "Schedule F": "usFarmIncSum.usFarmIncInp",
        "Schedule E": "usRentRoyInp",
        "Partnership": "usPassthrSum.usPShipInp",
        "SCorp": "usPassthrSum.usScorpInp",
    }
    return mapping.get(source, "usBusIncSum.usBusIncInp")


def assess_applicability(
    activity: BusinessActivityInput,
    rates: RatesInput | None = None,
) -> ApplicabilityResult:
    """
    Deterministic applicability / recommend gates from Scorp SPE global block.

    Applicable:  net_earnings > 0 AND is_se_biz
    Recommended: Applicable AND ownership_pct >= 50
    """
    rates = rates or RatesInput()
    net_earnings = activity.resolved_net_earnings(rates)
    reasons: list[str] = []
    owner = (activity.taxpayer_spouse_or_joint or "taxpayer").lower()
    if owner not in ("taxpayer", "spouse", "joint"):
        reasons.append(
            f"taxpayer_spouse_or_joint={activity.taxpayer_spouse_or_joint!r} is invalid; "
            "use taxpayer | spouse | joint."
        )
        owner = "taxpayer"

    applicable = bool(activity.is_se_biz and net_earnings > DEFAULT_MIN_NET_EARNINGS)
    if not activity.is_se_biz:
        reasons.append("Activity is not marked as subject to self-employment tax (is_se_biz=false).")
    if activity.net_income <= 0:
        reasons.append(
            f"net_income ({activity.net_income:.2f}) is not positive — "
            "little or no SE tax to save via S-Corp conversion."
        )
    if net_earnings <= DEFAULT_MIN_NET_EARNINGS:
        reasons.append(f"net_earnings ({net_earnings:.2f}) must be > 0.")

    recommended = applicable and activity.ownership_pct >= DEFAULT_OWNERSHIP_RECOMMEND_PCT
    if applicable and not recommended:
        reasons.append(
            f"ownership_pct ({activity.ownership_pct}) is below "
            f"{DEFAULT_OWNERSHIP_RECOMMEND_PCT}% recommend threshold."
        )
    if applicable and recommended:
        reasons.append(
            f"Meets SE earnings > 0 and ownership ≥ 50% recommend gate "
            f"(owner={owner})."
        )

    return ApplicabilityResult(
        applicable=applicable,
        recommended=recommended,
        reasons=reasons,
        net_earnings=net_earnings,
        ownership_pct=activity.ownership_pct,
        net_income=activity.net_income,
        source=activity.source,
        activity_id=activity.activity_id,
        taxpayer_spouse_or_joint=owner,
    )


def _ss_headroom(rates: RatesInput) -> float:
    return max(0.0, rates.ss_wage_base - rates.income_already_taxed_by_ss)


def _se_ss_change(
    net_earnings: float,
    rates: RatesInput,
    *,
    activity_net_income: float | None = None,
) -> tuple[float, float, float]:
    """
    SPE changeInSSIncome when removing this activity's netEarnings.

    startingSEIncome = round(allSEIncome × netEarningRatio)  # ALL SE for that owner
    startingSS = min(incomeTaxedBySocSec + startingSE, maxSSwage)
    endingSS   = max(min(incomeTaxedBySocSec + startingSE − netEarnings, maxSSwage), 0)
    changeInSS = startingSS − endingSS
    subjectSS  = min(changeInSS, netEarnings)

    Other Schedule C / SE activities sit inside allSEIncome, so they correctly
    consume SS wage-base headroom with W-2 wages.
    """
    # Prefer engine allSEIncome; if omitted, assume this activity is the only SE.
    all_se = rates.starting_se_income
    if all_se <= 0 and activity_net_income is not None:
        all_se = float(activity_net_income)
    starting_se_ne = float(_spe_round(all_se * rates.net_earnings_ratio))
    already = rates.income_already_taxed_by_ss
    base = rates.ss_wage_base
    starting_ss = min(already + starting_se_ne, base)
    ending_ss = max(min(already + starting_se_ne - net_earnings, base), 0.0)
    change_in_ss = starting_ss - ending_ss
    subject_ss = min(change_in_ss, net_earnings)
    return starting_se_ne, change_in_ss, subject_ss


def _se_tax_reduction(
    net_earnings: float,
    rates: RatesInput,
    *,
    activity_net_income: float | None = None,
) -> tuple[float, float, float, float]:
    """
    SPE SETaxReductionSETax. Returns
    (se_tax_dollars, starting_se_net_earnings, change_in_ss, se_subject_to_ss).
    """
    starting_se_ne, change_in_ss, subject_ss = _se_ss_change(
        net_earnings, rates, activity_net_income=activity_net_income
    )
    ss = _spe_round(subject_ss * (rates.ss_rate * 2))
    med = _spe_round(net_earnings * (rates.med_rate * 2))
    return float(ss + med), starting_se_ne, change_in_ss, subject_ss


def _wages_fica(wage: float, rates: RatesInput) -> tuple[float, float]:
    """
    SPE WagesFICA / WagesFICAEmployerHalf.

    Primary SPE uses min(maxSSwage, wages) for SS wages (not remaining headroom).
    """
    subject_ss = min(rates.ss_wage_base, wage)
    ss = _spe_round(subject_ss * (rates.ss_rate * 2))
    med = _spe_round(wage * (rates.med_rate * 2))
    total = float(ss + med)
    employer_half = float(_spe_round(total * 0.5))
    return total, employer_half


def apply_scorp_conversion(inp: ApplyScorpInput) -> ApplyScorpResult:
    """
    Deterministic apply: split net_income into wages + S-Corp ordinary,
    produce projection mutations + savings rollup mirroring SPE.
    """
    errors: list[str] = []
    warnings: list[str] = [
        "Reasonable compensation is advisor-determined. This tool does not invent a wage.",
        "This is a static SPE-faithful estimate, not a live ITA engine / Lacerte recalculation.",
    ]

    if inp.reasonable_wage is None:
        errors.append("reasonable_wage is required.")
    elif inp.reasonable_wage < 0:
        errors.append("reasonable_wage must be >= 0.")

    if inp.activity.net_income is None:
        errors.append("activity.net_income is required.")

    appl = assess_applicability(inp.activity, inp.rates)
    if not appl.applicable:
        errors.append("Activity is not applicable for S-Corp conversion under SPE gates.")

    wage = float(inp.reasonable_wage or 0)
    net_income = float(inp.activity.net_income or 0)

    if wage > net_income and not errors:
        warnings.append(
            f"reasonable_wage ({wage:.2f}) exceeds net_income ({net_income:.2f}); "
            "S-Corp ordinary income will be <= 0 after split."
        )

    if errors:
        return ApplyScorpResult(
            ok=False,
            errors=errors,
            applicability=appl,
            reasonable_wage=wage,
            net_income=net_income,
            wages_allocated=0.0,
            scorp_ordinary_income=0.0,
            wages_fica=0.0,
            wages_fica_employer_half=0.0,
            savings=None,
            mutations=[],
            primary_strategy_change=0.0,
            warnings=warnings,
        )

    rates = inp.rates
    net_earnings = appl.net_earnings
    owner = appl.taxpayer_spouse_or_joint
    ss_headroom = _ss_headroom(rates)
    wages_allocated = wage
    fica, fica_er_half = _wages_fica(wages_allocated, rates)
    # Card Step 6 STRATEGY_CHANGE = netIncome − wages (not net of employer FICA).
    # Model write / K-1 also nets employer FICA/2 (ScorpDistributionMinusFICA).
    scorp_distribution = net_income - wages_allocated
    scorp_k1 = scorp_distribution - fica_er_half
    scorp_ordinary = scorp_distribution  # savings rollup / card Step 6 uses this

    if rates.income_already_taxed_by_ss <= 0:
        warnings.append(
            f"income_already_taxed_by_ss is 0 for owner={owner}. "
            "If that person has other W-2 wages, Social Security savings may be overstated."
        )
    if rates.starting_se_income <= 0:
        warnings.append(
            f"starting_se_income (allSEIncome) not provided for owner={owner}; "
            "defaulting to this activity's net_income only. Other Schedule C / SE "
            "will not reduce SS headroom."
        )

    total_rate = rates.total_marginal_rate_pct / 100.0

    se_tax_reduction, starting_se_ne, change_in_ss, se_subject_ss = _se_tax_reduction(
        net_earnings, rates, activity_net_income=net_income
    )
    if change_in_ss + 1e-9 < net_earnings:
        warnings.append(
            f"SS subject on SE removal is {change_in_ss:.2f} of net_earnings "
            f"{net_earnings:.2f} — other W-2 and/or SE (allSEIncome={rates.starting_se_income or net_income:.2f}) "
            f"already consume the wage base for owner={owner}."
        )

    # Income-tax-at-rate lines: ITA card shows whole dollars (decimalfmt '#').
    se_back_out = float(_spe_round(net_income * total_rate))
    half_se = float(_spe_round(se_tax_reduction * 0.5))
    # SPE primary sCorp-SE-Tax-Savings.spe: secSeTaxDeductionLost uses MARGINAL_RATE_FED only
    # (secondary SE_Tax_Adj_Impact display may use total — primary PROJECTED_TAX_SAVINGS uses FED).
    fed_rate = rates.federal_marginal_rate_pct / 100.0
    se_deduction_lost = float(_spe_round(half_se * fed_rate))
    wages_income_tax = float(_spe_round(wages_allocated * total_rate))
    # SPE allows negative when wages > netIncome (credits the rollup).
    scorp_income_tax = float(_spe_round(scorp_ordinary * total_rate))
    er_fica_tax_savings = float(_spe_round(fica_er_half * total_rate))

    projected = (
        se_back_out
        + se_tax_reduction
        - se_deduction_lost
        - wages_income_tax
        - fica
        - scorp_income_tax
        + er_fica_tax_savings
    )

    savings = SavingsBreakdown(
        se_income_back_out_tax_savings=se_back_out,
        se_tax_reduction=se_tax_reduction,
        se_deduction_lost_tax_cost=se_deduction_lost,
        wages_income_tax_cost=wages_income_tax,
        wages_fica=fica,
        scorp_ordinary_income_tax_cost=scorp_income_tax,
        employer_fica_half_tax_savings=er_fica_tax_savings,
        projected_tax_savings=projected,
        cash_outlay=0.0,
        ss_wage_base=rates.ss_wage_base,
        income_already_taxed_by_ss=rates.income_already_taxed_by_ss,
        ss_headroom=round(ss_headroom, 2),
        starting_se_income=float(rates.starting_se_income or net_income),
        starting_se_net_earnings=round(starting_se_ne, 2),
        change_in_ss_income=round(change_in_ss, 2),
        se_subject_to_ss=round(se_subject_ss, 2),
        taxpayer_spouse_or_joint=owner,
    )

    container = _schedule_container(inp.activity.source)
    orig_path = (
        f"$.projection.return.income.usIncSum.{container}"
        f"[?(@.prefix == {inp.activity.prefix})]"
    )
    new_w2_prefix = max(100, inp.activity.prefix + 100)  # demo namespace
    new_scorp_prefix = max(200, inp.activity.prefix + 200)

    mutations = [
        ProjectionMutation(
            path=orig_path,
            action="flag",
            fields={
                "generalInformation.deleteNextYear": 1,
                "primary.STRATEGY_CHANGE": -net_income,
                "netIncome": 0,
            },
            secondary_id="SE_Income_ZeroOut",
            step="1 — zero original SE activity",
        ),
        ProjectionMutation(
            path="$.projection.return.adjustments.usAdjSum.defaultSection.sETaxAdjCalc",
            action="update",
            fields={"note": "Remove SE tax / apply SE tax adjustment impact (engine-owned)"},
            secondary_id="SE_Income_TaxSavings+SE_Tax_Adj_Impact",
            step="2–3 — SE tax out; lose ½ SE deduction",
        ),
        ProjectionMutation(
            path=(
                "$.projection.return.income.usIncSum.usWageSum.usWageInp"
                f"[?(@.prefix == {new_w2_prefix})]"
            ),
            action="create",
            fields={
                "federal.wgFedwages": wages_allocated,
                "federal.wgSSwages": min(wages_allocated, rates.ss_wage_base),
                "federal.wgMedwages": wages_allocated,
                "other.wgSCorp2PctShrhldr": 1,
                "general.namEmp": f"New S-Corp employer ({inp.activity.name})",
            },
            secondary_id="new_w2",
            step="4 — reasonable wage on new W-2",
        ),
        ProjectionMutation(
            path=(
                "$.projection.return.income.usIncSum.usPassthrSum.usScorpInp"
                f"[?(@.prefix == {new_scorp_prefix})]"
            ),
            action="create",
            fields={
                # Model write nets employer FICA/2; card STRATEGY_CHANGE is distribution only.
                "netIncomeLossOverride.iTAScorpNetincLoss": scorp_k1,
                "STRATEGY_CHANGE": scorp_distribution,
            },
            secondary_id="new_scorp",
            step="5–6 — residual as S-Corp ordinary income",
        ),
    ]

    return ApplyScorpResult(
        ok=True,
        errors=[],
        applicability=appl,
        reasonable_wage=wages_allocated,
        net_income=net_income,
        wages_allocated=wages_allocated,
        scorp_ordinary_income=round(scorp_ordinary, 2),
        wages_fica=round(fica, 2),
        wages_fica_employer_half=round(fica_er_half, 2),
        savings=savings,
        mutations=mutations,
        primary_strategy_change=-net_income,
        warnings=warnings,
    )


def estimate_scorp_savings(inp: ApplyScorpInput) -> dict[str, Any]:
    """
    Part 2 tool: deterministic savings only (SPE rollup).

    Requires confirmed reasonable_wage. Does not invent wages.
    Returns savings breakdown + split amounts; mutations are included for
    apply-ready callers but this operation's contract is savings-first.
    """
    full = apply_scorp_conversion(inp)
    return {
        "ok": full.ok,
        "errors": full.errors,
        "warnings": full.warnings,
        "applicability": full.applicability.to_dict() if full.applicability else None,
        "reasonable_wage": full.reasonable_wage,
        "net_income": full.net_income,
        "wages_allocated": full.wages_allocated,
        "scorp_ordinary_income": full.scorp_ordinary_income,
        "wages_fica": full.wages_fica,
        "wages_fica_employer_half": full.wages_fica_employer_half,
        "savings": full.savings.to_dict() if full.savings else None,
        # Included so apply can reuse the same payload; Skill Part 2 surfaces savings.
        "mutations": [m.to_dict() for m in full.mutations],
        "primary_strategy_change": full.primary_strategy_change,
    }


def assess_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """JSON entrypoint for assess_scorp_applicability."""
    activity = activity_from_dict(payload["activity"])
    rates = rates_from_dict(payload.get("rates"))
    return assess_applicability(activity, rates).to_dict()


def savings_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """JSON entrypoint for estimate_scorp_savings."""
    activity = activity_from_dict(payload["activity"])
    rates = rates_from_dict(payload.get("rates"))
    if "reasonable_wage" not in payload:
        return {
            "ok": False,
            "errors": ["reasonable_wage is required for savings estimation."],
            "savings": None,
        }
    inp = ApplyScorpInput(
        activity=activity,
        reasonable_wage=float(payload["reasonable_wage"]),
        rates=rates,
        tax_year=payload.get("tax_year"),
        filing_status=payload.get("filing_status"),
        scenario_id=payload.get("scenario_id"),
    )
    return estimate_scorp_savings(inp)


def tool_spec() -> dict[str, Any]:
    """MCP-style tool descriptors — two operations for the two Skill parts."""
    return {
        "mcp_asset_alias": "tax-mcp",
        "tools": [
            {
                "name": "assess_scorp_applicability",
                "description": (
                    "Part 1 — Deterministic S-Corp applicability/recommend gates "
                    "(SE net earnings > 0, is_se_biz; recommend if ownership >= 50%). "
                    "No LLM. Does not require reasonable_wage."
                ),
                "required_inputs": [
                    "activity.activity_id",
                    "activity.source",
                    "activity.name",
                    "activity.net_income",
                    "activity.is_se_biz",
                ],
                "recommended_inputs": [
                    "activity.ownership_pct",
                    "rates.net_earnings_ratio",
                    "activity.net_earnings",
                ],
                "outputs": [
                    "applicable",
                    "recommended",
                    "reasons",
                    "net_earnings",
                    "ownership_pct",
                ],
            },
            {
                "name": "estimate_scorp_savings",
                "description": (
                    "Part 2 — Deterministic SPE-faithful savings estimate given a confirmed "
                    "reasonable_wage: wage/FICA/SE rollup + projection mutations. No LLM."
                ),
                "required_inputs": [
                    "activity.* (same as Part 1)",
                    "reasonable_wage",
                ],
                "recommended_inputs": [
                    "rates.federal_marginal_rate_pct",
                    "rates.state_marginal_rate_pct",
                    "rates.ss_wage_base",
                    "tax_year",
                ],
                "outputs": [
                    "savings",
                    "wages_allocated",
                    "scorp_ordinary_income",
                    "mutations",
                    "warnings",
                ],
            },
        ],
        "note": (
            "Neither tool requires an LLM. LLM is optional only for unstructured "
            "extraction or prose explanation outside the Skill's core path."
        ),
    }


def activity_from_dict(d: dict[str, Any]) -> BusinessActivityInput:
    return BusinessActivityInput(
        activity_id=str(d["activity_id"]),
        source=str(d.get("source") or "Schedule C"),
        name=str(d.get("name") or d["activity_id"]),
        net_income=float(d["net_income"]),
        is_se_biz=bool(d.get("is_se_biz", True)),
        ownership_pct=float(d.get("ownership_pct", 100)),
        taxpayer_spouse_or_joint=str(d.get("taxpayer_spouse_or_joint") or "taxpayer"),
        prefix=int(d.get("prefix", 1)),
        net_earnings=float(d["net_earnings"]) if d.get("net_earnings") is not None else None,
    )


def rates_from_dict(d: dict[str, Any] | None) -> RatesInput:
    d = d or {}
    return RatesInput(
        **{
            k: float(d[k])
            for k in (
                "net_earnings_ratio",
                "ss_rate",
                "med_rate",
                "ss_wage_base",
                "federal_marginal_rate_pct",
                "state_marginal_rate_pct",
                "nyc_marginal_rate_pct",
                "income_already_taxed_by_ss",
                "starting_se_income",
            )
            if k in d and d[k] is not None
        }
    )


def apply_from_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """JSON-friendly entrypoint — alias of estimate/apply with full result."""
    return savings_from_dict(payload)