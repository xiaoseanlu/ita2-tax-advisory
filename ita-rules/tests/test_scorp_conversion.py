#!/usr/bin/env python3
"""
SPE-fidelity tests for the S-Corp Conversion tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary rollup:  tax-strategy-content/IndUS/strategies/Scorp/
                         sCorp-SE-Tax-Savings.spe
  SPE SE-tax detail:   tax-strategy-content/IndUS/strategies/Scorp/SE_Income.spe
  SPE W-2 leg:         tax-strategy-content/IndUS/strategies/Scorp/new_w2.spe
  SPE S-Corp leg:      tax-strategy-content/IndUS/strategies/Scorp/new_scorp.spe
  SPE unit tests:      tax-strategy-content/IndUS/strategies/Scorp/unitTests.spe
  Python tool:         skills/income_tax/assisted/scorp-conversion/tools/scorp_conversion.py

The tool's purpose is two-fold — applicability and savings estimate — so the
suite covers BOTH: every gate/threshold/clamp, the SE-tax computation, the
reasonable-wage split, and the projected-savings rollup.

Scope note on the primary vs. secondaries
------------------------------------------
The Python tool implements the PRIMARY sCorp-SE-Tax-Savings.spe rollup
(secondarySavingsTotal, line 263). The 0.9% ADDITIONAL Medicare tax appears
ONLY in the DISPLAY secondaries (SE_Income.spe l.396-400, new_w2.spe l.95),
NOT in the primary SE-tax / FICA lines (sCorp-SE-Tax-Savings.spe l.211-220,
217-220). The primary uses exactly:
    SS  = round(subjectSS * rateSS*2)      # 12.4% OASDI on SS-capped amount
    MED = round(netEarnings * rateMed*2)   # 2.9% Medicare on full net earnings
So this suite verifies the primary path WITHOUT additional Medicare — which is
faithful to the rollup the tool reproduces.

Run:  python3 -m unittest test_scorp_conversion -v
  or:  python3 test_scorp_conversion.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

sc = load_tool(
    "skills/income_tax/assisted/scorp-conversion/tools/scorp_conversion.py",
    "scorp_conversion",
)


def activity(**over):
    d = dict(activity_id="a1", source="Schedule C", name="Biz", net_income=100_000)
    d.update(over)
    return sc.BusinessActivityInput(**d)


def rates(**over):
    return sc.RatesInput(**over)


def apply(act, wage, r=None):
    return sc.apply_scorp_conversion(
        sc.ApplyScorpInput(activity=act, reasonable_wage=wage, rates=r or sc.RatesInput())
    )


# ---------------------------------------------------------------------------
# Statutory / indexed rate defaults.
# SPE reads EMPLOYEE-only rates from usITAIndexedAmount then applies (rate*2).
#   marginalRateSocialSecurity (employee) = 6.2%  -> *2 = 12.4% (unitTests l.463)
#   marginalRateMedicare       (employee) = 1.45% -> *2 = 2.90% (unitTests l.460)
#   netEarningRatio = 0.9235 (unitTests l.58: 2499646 * .9235 = 2308423)
#   maxSSwage = SS wage base cap (sCorp-SE-Tax-Savings.spe l.196)
# ---------------------------------------------------------------------------
class TestRateDefaults(unittest.TestCase):
    def test_employee_only_defaults(self):
        # SPE stores employee-only rates; tool defaults must be 6.2% / 1.45%.
        self.assertEqual(sc.DEFAULT_SS_RATE, 0.062)
        self.assertEqual(sc.DEFAULT_MED_RATE, 0.0145)

    def test_net_earnings_ratio(self):
        # unitTests.spe l.58 anchor: 92.35% net-earnings factor.
        self.assertEqual(sc.DEFAULT_NET_EARNINGS_RATIO, 0.9235)

    def test_combined_rates_double_the_employee_rate(self):
        # SPE l.212-213 uses rateSS*2 and rateMed*2 -> 12.4% + 2.9%.
        self.assertAlmostEqual(sc.DEFAULT_SS_RATE * 2, 0.124)
        self.assertAlmostEqual(sc.DEFAULT_MED_RATE * 2, 0.029)


# ---------------------------------------------------------------------------
# net-earnings factor — sCorp-SE-Tax-Savings.spe l.67,74:
#   netEarningsCF = round(netIncomeSE * seIncomeFactor)
# unitTests.spe l.54-58: 2499646 Sch-C income * .9235 = 2308423 (rounded).
# ---------------------------------------------------------------------------
class TestNetEarningsFactor(unittest.TestCase):
    def test_92_35_pct_rounded(self):
        r = sc.assess_applicability(activity(net_income=200_000))
        # round(200000 * 0.9235) = 184700
        self.assertEqual(r.net_earnings, 184_700)

    def test_unittest_anchor_2499646(self):
        # unitTests.spe l.56-58: round(2499646 * .9235) = 2308423
        r = sc.assess_applicability(activity(net_income=2_499_646))
        self.assertEqual(r.net_earnings, 2_308_423)

    def test_engine_net_earnings_overrides_factor(self):
        # activity.net_earnings supplied -> used verbatim (no re-derivation).
        r = sc.assess_applicability(activity(net_income=100_000, net_earnings=12_345))
        self.assertEqual(r.net_earnings, 12_345)


# ---------------------------------------------------------------------------
# Applicability gate — sCorp-SE-Tax-Savings.spe l.9-11:
#   applicability biz {(biz.netEarnings > 0) && biz.isSEBiz}
# ---------------------------------------------------------------------------
class TestApplicabilityGate(unittest.TestCase):
    def test_positive_net_earnings_and_se_biz_applicable(self):
        r = sc.assess_applicability(activity(net_income=100_000))
        self.assertTrue(r.applicable)

    def test_zero_net_income_not_applicable(self):
        # netEarnings = round(0*.9235) = 0, not > 0.
        r = sc.assess_applicability(activity(net_income=0))
        self.assertFalse(r.applicable)

    def test_negative_net_income_not_applicable(self):
        r = sc.assess_applicability(activity(net_income=-5_000))
        self.assertFalse(r.applicable)

    def test_not_se_biz_not_applicable(self):
        # isSEBiz == false fails the gate even with positive earnings.
        r = sc.assess_applicability(activity(net_income=100_000, is_se_biz=False))
        self.assertFalse(r.applicable)


# ---------------------------------------------------------------------------
# Recommend gate — sCorp-SE-Tax-Savings.spe l.17-19:
#   recommendedSE... = applicability tpSEApplicableGroups biz {(biz.ownershipPct >= 50)}
#   (recommend requires applicable AND ownership >= 50%)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_ownership_at_50_recommended(self):
        # inclusive threshold: >= 50
        r = sc.assess_applicability(activity(source="Partnership", ownership_pct=50))
        self.assertTrue(r.recommended)

    def test_ownership_below_50_applicable_not_recommended(self):
        r = sc.assess_applicability(activity(source="Partnership", ownership_pct=40))
        self.assertTrue(r.applicable)
        self.assertFalse(r.recommended)

    def test_ownership_100_recommended(self):
        r = sc.assess_applicability(activity(ownership_pct=100))
        self.assertTrue(r.recommended)

    def test_not_applicable_cannot_be_recommended(self):
        # recommend is a subset of applicable (SPE derives it from the applicable set).
        r = sc.assess_applicability(activity(net_income=0, ownership_pct=100))
        self.assertFalse(r.applicable)
        self.assertFalse(r.recommended)


# ---------------------------------------------------------------------------
# SE-tax computation — sCorp-SE-Tax-Savings.spe l.202-214:
#   startingSS = min(incomeTaxedBySocSec + startingSE, maxSSwage)
#   endingSS   = max(min(incomeTaxedBySocSec + startingSE - netEarnings, maxSSwage), 0)
#   changeInSS = startingSS - endingSS
#   SEsubjectSS = min(changeInSS, netEarnings)
#   SSTax  = round(SEsubjectSS * rateSS*2)     # 12.4% capped at SS wage base
#   MEDTax = round(netEarnings * rateMed*2)    # 2.9% on FULL net earnings
#   SETaxReductionSETax = SSTax + MEDTax
# ---------------------------------------------------------------------------
class TestSETaxComputation(unittest.TestCase):
    def test_below_ss_wage_base_full_ss_and_med(self):
        # net_income 100000 -> ne 92350; below cap 176100 so all subject to SS.
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24))
        # SS  = round(92350 * .124) = 11451 ; MED = round(92350 * .029) = 2678
        self.assertEqual(r.savings.se_tax_reduction, 11_451 + 2_678)  # 14129

    def test_above_ss_wage_base_ss_capped_med_full(self):
        # net 500000 -> ne 461750. startingSS=min(461750,176100)=176100;
        # endingSS=max(min(461750-461750,176100),0)=0; change=176100; subject=176100.
        r = apply(activity(net_income=500_000), 200_000,
                  rates(federal_marginal_rate_pct=37, ss_wage_base=176_100))
        self.assertEqual(r.savings.change_in_ss_income, 176_100)
        self.assertEqual(r.savings.se_subject_to_ss, 176_100)
        # SS  = round(176100 * .124) = 21836 ; MED = round(461750 * .029) = 13391
        self.assertEqual(r.savings.se_tax_reduction, 21_836 + 13_391)  # 35227

    def test_income_already_taxed_by_ss_consumes_headroom(self):
        # incomeTaxedBySocSec == maxSSwage -> no SS headroom -> SS portion 0.
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24,
                        ss_wage_base=176_100,
                        income_already_taxed_by_ss=176_100))
        self.assertEqual(r.savings.change_in_ss_income, 0.0)
        # SE tax reduction = Medicare only: round(92350 * .029) = 2678
        self.assertEqual(r.savings.se_tax_reduction, 2_678)

    def test_starting_se_income_includes_other_se(self):
        # allSEIncome (starting_se_income) larger than this activity -> starting SE
        # net-earnings consumes SS headroom before this activity does.
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24,
                        ss_wage_base=176_100,
                        starting_se_income=200_000))
        # startingSE_ne = round(200000*.9235)=184700; startingSS=min(184700,176100)=176100
        self.assertEqual(r.savings.starting_se_net_earnings, 184_700)


# ---------------------------------------------------------------------------
# Wages FICA — sCorp-SE-Tax-Savings.spe l.217-222:
#   subjectToSSTax = min(maxSSwage, netIncomeAllocatedToWages)   # full base, not headroom
#   SSTax  = round(subjectToSSTax * rateSS*2)
#   MEDTax = round(netIncomeAllocatedToWages * rateMed*2)
#   WagesFICA = SSTax + MEDTax
#   WagesFICAEmployerHalf = round(WagesFICA * 0.5)
# ---------------------------------------------------------------------------
class TestWagesFICA(unittest.TestCase):
    def test_wages_below_ss_base(self):
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, ss_wage_base=176_100))
        # SS = round(40000*.124)=4960 ; MED = round(40000*.029)=1160 -> 6120
        self.assertEqual(r.savings.wages_fica, 6_120)
        # employer half = round(6120 * 0.5) = 3060
        self.assertEqual(r.wages_fica_employer_half, 3_060)

    def test_wages_ss_capped_at_wage_base(self):
        # wage 200000 > 176100 -> SS on 176100 only, Medicare on full 200000.
        r = apply(activity(net_income=500_000), 200_000,
                  rates(federal_marginal_rate_pct=37, ss_wage_base=176_100))
        # SS = round(176100*.124)=21836 ; MED = round(200000*.029)=5800 -> 27636
        self.assertEqual(r.savings.wages_fica, 27_636)
        # employer half = round(27636 * 0.5) = 13818
        self.assertEqual(r.wages_fica_employer_half, 13_818)


# ---------------------------------------------------------------------------
# Reasonable-wage split — sCorp-SE-Tax-Savings.spe l.225 / new_scorp.spe l.11:
#   netIncomeAllocatedToScorpDistribution = netIncome - netIncomeAllocatedToWages
#   K-1 (ScorpDistributionMinusFICA, l.93/227) = distribution - WagesFICAEmployerHalf
# ---------------------------------------------------------------------------
class TestReasonableWageSplit(unittest.TestCase):
    def test_distribution_is_net_income_minus_wage(self):
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24))
        self.assertEqual(r.scorp_ordinary_income, 60_000)  # 100000 - 40000
        self.assertEqual(r.wages_allocated, 40_000)

    def test_k1_nets_employer_fica_half(self):
        # new_scorp.spe l.122: scorpK1 = netIncome - wages - WagesFICAEmployerHalf
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, ss_wage_base=176_100))
        k1_mut = next(m for m in r.mutations if m.secondary_id == "new_scorp")
        # distribution 60000 - employer half 3060 = 56940
        self.assertEqual(k1_mut.fields["netIncomeLossOverride.iTAScorpNetincLoss"], 56_940)
        self.assertEqual(k1_mut.fields["STRATEGY_CHANGE"], 60_000)


# ---------------------------------------------------------------------------
# AUDIT FIX 1 — half-SE-tax deduction lost is FEDERAL-ONLY.
# sCorp-SE-Tax-Savings.spe l.254:
#   secSeTaxDeductionLost = round(SETaxReductionSETax * 0.5) * (MARGINAL_RATE_FED/100)
# (uses MARGINAL_RATE_FED, NOT MARGINAL_RATE_TOTAL — state/NYC excluded).
# ---------------------------------------------------------------------------
class TestHalfSEDeductionFederalOnly(unittest.TestCase):
    def test_deduction_lost_uses_fed_rate_only(self):
        # fed 24 + state 10 = total 34, but deduction-lost must use fed 24 only.
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, state_marginal_rate_pct=10))
        se_red = r.savings.se_tax_reduction  # 14129
        half = sc._spe_round(se_red * 0.5)   # round(7064.5) = 7065
        self.assertEqual(half, 7_065)
        # federal-only: round(7065 * 0.24) = round(1695.6) = 1696
        self.assertEqual(r.savings.se_deduction_lost_tax_cost, 1_696)

    def test_state_rate_does_not_change_deduction_lost(self):
        base = apply(activity(net_income=100_000), 40_000,
                     rates(federal_marginal_rate_pct=24, state_marginal_rate_pct=0))
        with_state = apply(activity(net_income=100_000), 40_000,
                           rates(federal_marginal_rate_pct=24, state_marginal_rate_pct=10))
        # Half-SE deduction cost identical regardless of state rate (federal-only).
        self.assertEqual(
            base.savings.se_deduction_lost_tax_cost,
            with_state.savings.se_deduction_lost_tax_cost,
        )


# ---------------------------------------------------------------------------
# AUDIT FIX 2 — negative ordinary tax allowed when wage > net income.
# sCorp-SE-Tax-Savings.spe l.225,246:
#   netIncomeAllocatedToScorpDistribution = netIncome - wages   (can be < 0)
#   secNewSCorpIncomeTaxCosts = distribution * (MARGINAL_RATE_TOTAL/100)  (NO clamp)
# When wages exceed net income the ordinary-income tax cost goes NEGATIVE
# (a credit into the rollup) — the tool must not clamp it to 0.
# ---------------------------------------------------------------------------
class TestNegativeOrdinaryTax(unittest.TestCase):
    def test_wage_exceeds_net_income_negative_distribution(self):
        r = apply(activity(net_income=100_000), 120_000,
                  rates(federal_marginal_rate_pct=24))
        self.assertEqual(r.scorp_ordinary_income, -20_000)

    def test_ordinary_tax_cost_goes_negative(self):
        r = apply(activity(net_income=100_000), 120_000,
                  rates(federal_marginal_rate_pct=24))
        # round(-20000 * 0.24) = -4800, NOT clamped to 0.
        self.assertEqual(r.savings.scorp_ordinary_income_tax_cost, -4_800)
        self.assertLess(r.savings.scorp_ordinary_income_tax_cost, 0)

    def test_still_ok_when_wage_exceeds_income(self):
        # This is a valid (if unusual) computation, not an error.
        r = apply(activity(net_income=100_000), 120_000,
                  rates(federal_marginal_rate_pct=24))
        self.assertTrue(r.ok)


# ---------------------------------------------------------------------------
# Projected-savings rollup — sCorp-SE-Tax-Savings.spe l.263-264:
#   secondarySavingsTotal =
#       SEIncomeBackOutTaxSavings          (l.241, netIncome * TOTAL rate)
#     + SETaxReductionSETax                (l.214)
#     - secSeTaxDeductionLost              (l.254, fed-only)
#     - wagesIncomeTaxCosts                (l.243, wages * TOTAL rate)
#     - WagesFICA                          (l.220)
#     - secNewSCorpIncomeTaxCosts          (l.246, distribution * TOTAL rate)
#     + secNewSCorpFICATaxSavings          (l.249, employer half * TOTAL rate)
#   PROJECTED_TAX_SAVINGS = decimalfmt {secondarySavingsTotal} '#'  (whole dollars)
# ---------------------------------------------------------------------------
class TestProjectedSavingsRollup(unittest.TestCase):
    def test_backout_uses_total_rate(self):
        # SEIncomeBackOutTaxSavings = round(netIncome * TOTAL/100)
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, state_marginal_rate_pct=10))
        # total 34%: round(100000 * .34) = 34000
        self.assertEqual(r.savings.se_income_back_out_tax_savings, 34_000)

    def test_wages_income_tax_uses_total_rate(self):
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, state_marginal_rate_pct=10))
        # round(40000 * .34) = 13600
        self.assertEqual(r.savings.wages_income_tax_cost, 13_600)

    def test_employer_fica_savings_uses_total_rate(self):
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, ss_wage_base=176_100))
        # employer half 3060 * 24% = round(734.4) = 734
        self.assertEqual(r.savings.employer_fica_half_tax_savings, 734)

    def test_full_rollup_fed_only(self):
        # End-to-end anchor with fed 24% only (state 0), net 100000, wage 40000.
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, ss_wage_base=176_100))
        s = r.savings
        # backout 24000 + seTaxRed 14129 - dedLost 1696 - wagesTax 9600
        #   - wagesFICA 6120 - scorpTax 14400 + erFICA 734 = 7047
        expected = (24_000 + 14_129 - 1_696 - 9_600 - 6_120 - 14_400 + 734)
        self.assertEqual(expected, 7_047)
        self.assertEqual(s.projected_tax_savings, 7_047)

    def test_rollup_whole_dollar_rounding(self):
        # decimalfmt '#' -> each line rounds half-up to whole dollars.
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24))
        self.assertEqual(r.savings.projected_tax_savings,
                         int(r.savings.projected_tax_savings))


# ---------------------------------------------------------------------------
# NYC rate — sCorp-SE-Tax-Savings.spe l.234-239:
#   MARGINAL_RATE_TOTAL = FED + STATE + NYC   (NYC only when residentState.index == 9)
# unitTests.spe 'NYC rate' test uses nyc 3.85; here we exercise the additive total.
# ---------------------------------------------------------------------------
class TestNYCRate(unittest.TestCase):
    def test_nyc_rate_adds_into_total(self):
        r = apply(activity(net_income=100_000), 40_000,
                  rates(federal_marginal_rate_pct=24, state_marginal_rate_pct=10,
                        nyc_marginal_rate_pct=3.85))
        # total = 24 + 10 + 3.85 = 37.85 -> backout round(100000 * .3785) = 37850
        self.assertEqual(r.savings.se_income_back_out_tax_savings, 37_850)


# ---------------------------------------------------------------------------
# Mutations — projection writes mirroring the SPE secondaries.
#   SE_Income_ZeroOut (SE_Income.spe l.21): STRATEGY_CHANGE = -netIncome, netIncome->0
#   new_w2 (new_w2.spe l.113-115): wgFedwages = wage; wgSSwages = min(wage, maxSSwage)
#   new_scorp (new_scorp.spe l.181): iTAScorpNetincLoss = netIncome - wages - erFICA/2
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_zero_out_primary_strategy_change(self):
        r = apply(activity(net_income=100_000, prefix=1), 40_000,
                  rates(federal_marginal_rate_pct=24))
        z = next(m for m in r.mutations if m.secondary_id == "SE_Income_ZeroOut")
        self.assertEqual(z.fields["primary.STRATEGY_CHANGE"], -100_000)
        self.assertEqual(z.fields["netIncome"], 0)
        self.assertEqual(r.primary_strategy_change, -100_000)

    def test_new_w2_ss_wages_capped(self):
        r = apply(activity(net_income=500_000), 200_000,
                  rates(federal_marginal_rate_pct=37, ss_wage_base=176_100))
        w2 = next(m for m in r.mutations if m.secondary_id == "new_w2")
        self.assertEqual(w2.fields["federal.wgFedwages"], 200_000)
        self.assertEqual(w2.fields["federal.wgSSwages"], 176_100)  # capped
        self.assertEqual(w2.fields["federal.wgMedwages"], 200_000)
        self.assertEqual(w2.fields["other.wgSCorp2PctShrhldr"], 1)

    def test_schedule_container_by_source(self):
        # sCorp-SE-Tax-Savings.spe l.122-130 schedule map.
        for source, frag in [
            ("Schedule C", "usBusIncSum.usBusIncInp"),
            ("Schedule F", "usFarmIncSum.usFarmIncInp"),
            ("Schedule E", "usRentRoyInp"),
            ("Partnership", "usPassthrSum.usPShipInp"),
            ("SCorp", "usPassthrSum.usScorpInp"),
        ]:
            r = apply(activity(source=source, net_income=100_000), 40_000,
                      rates(federal_marginal_rate_pct=24))
            z = next(m for m in r.mutations if m.secondary_id == "SE_Income_ZeroOut")
            self.assertIn(frag, z.path, f"source {source}")


# ---------------------------------------------------------------------------
# Validation / error paths.
#   reasonable_wage required (>= 0); not-applicable activity errors out.
# additional_info min_validation.value = 0 (sCorp-SE-Tax-Savings.spe l.332).
# ---------------------------------------------------------------------------
class TestValidationErrors(unittest.TestCase):
    def test_negative_wage_errors(self):
        r = apply(activity(net_income=100_000), -1,
                  rates(federal_marginal_rate_pct=24))
        self.assertFalse(r.ok)
        self.assertTrue(any("reasonable_wage" in e for e in r.errors))

    def test_not_applicable_errors(self):
        r = apply(activity(net_income=0), 10_000,
                  rates(federal_marginal_rate_pct=24))
        self.assertFalse(r.ok)
        self.assertTrue(any("not applicable" in e.lower() for e in r.errors))

    def test_zero_wage_allowed(self):
        # wage 0 is valid (>= min 0): entire net income becomes distribution.
        r = apply(activity(net_income=100_000), 0,
                  rates(federal_marginal_rate_pct=24))
        self.assertTrue(r.ok)
        self.assertEqual(r.scorp_ordinary_income, 100_000)


# ---------------------------------------------------------------------------
# JSON entrypoints — estimate_scorp_savings / assess (Skill Part 1 & Part 2).
# ---------------------------------------------------------------------------
class TestJSONEntrypoints(unittest.TestCase):
    def test_assess_from_dict(self):
        out = sc.assess_from_dict(
            {"activity": {"activity_id": "a1", "source": "Schedule C",
                          "name": "B", "net_income": 200_000, "ownership_pct": 100}}
        )
        self.assertTrue(out["applicable"])
        self.assertTrue(out["recommended"])
        self.assertEqual(out["net_earnings"], 184_700)

    def test_savings_from_dict_requires_wage(self):
        out = sc.savings_from_dict(
            {"activity": {"activity_id": "a1", "source": "Schedule C",
                          "name": "B", "net_income": 100_000}}
        )
        self.assertFalse(out["ok"])

    def test_savings_from_dict_full(self):
        out = sc.savings_from_dict(
            {"activity": {"activity_id": "a1", "source": "Schedule C",
                          "name": "B", "net_income": 100_000},
             "reasonable_wage": 40_000,
             "rates": {"federal_marginal_rate_pct": 24, "ss_wage_base": 176_100}}
        )
        self.assertTrue(out["ok"], out.get("errors"))
        self.assertEqual(out["savings"]["projected_tax_savings"], 7_047)


if __name__ == "__main__":
    unittest.main(verbosity=2)
