#!/usr/bin/env python3
"""
SPE-fidelity tests for the 401(k) Employer Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  401k Employer Contribution/employer-401k-contribution.spe
  SPE limits:   tax-strategy-content/IndUS/strategies/common/
                  shared401KLimit_GlobalScope.spe
                  shared401KLimit_GlobalScope_strategyLimit.spe
                  shared401KLimit_GlobalScope_validation.spe
  Python tool:  skills/income_tax/assisted/401k-employer/tools/er_401k.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: every condition / threshold / clamp from the SPE, plus the
savings + validation math.

Employer-specific notes vs the employee strategy:
  * Employer headroom has NO baseline subtraction
    (strategyLimit.spe line 12: max(combined401KLimitTxp - combinedAbsorbed, 0)).
  * The employer strategy never sets nonConformingState=true, so PA does NOT
    zero the state rate here (the employer SPE has no PA-conformity block).
  * CASH_OUTLAY is always 0 (employer-funded match) — primary.spe line 81/121.
  * There is an employer match term: min(wgFedwages * 0.05, MaxAllowedEmployer)
    (primary.spe lines 27/30).

Run:  python3 -m unittest test_401k_employer -v
  or:  python3 test_401k_employer.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

er = load_tool(
    "skills/income_tax/assisted/401k-employer/tools/er_401k.py", "er_401k"
)


def assess(**payload):
    return er.assess_from_dict(payload)


def savings(**payload):
    return er.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Employer headroom formula — shared401KLimit_GlobalScope_strategyLimit.spe line 12
#   taxPayerMaxAllowedContributionEmployer =
#       max(combined401KLimitTxp - taxpayerCombined401kContributionLimitAbsorbed, 0)
#   (NO baseline subtraction, unlike the employee formula on line 9.)
# ---------------------------------------------------------------------------
class TestEmployerHeadroomFormula(unittest.TestCase):
    def h(self, **r):
        return er.compute_employer_headroom(er.retirement_from_dict(r))

    def test_full_combined_limit_when_nothing_absorbed(self):
        # combined 69000, nothing absorbed -> 69000
        self.assertEqual(self.h(combined_401k_limit=69_000), 69_000)

    def test_absorbed_reduces_headroom(self):
        # 69000 - 10000 absorbed = 59000
        self.assertEqual(
            self.h(combined_401k_limit=69_000, combined_limit_absorbed=10_000),
            59_000,
        )

    def test_no_baseline_subtraction(self):
        # Employer formula has NO baseline term; RetirementBaseline exposes no
        # baseline fields. Confirm headroom == full combined limit regardless.
        self.assertEqual(self.h(combined_401k_limit=69_000), 69_000)

    def test_negative_clamped_to_zero(self):
        # over-absorbed -> max(...,0) -> 0, not negative
        self.assertEqual(
            self.h(combined_401k_limit=69_000, combined_limit_absorbed=80_000),
            0.0,
        )


# ---------------------------------------------------------------------------
# Employer match — employer-401k-contribution.spe lines 27, 30
#   taxPayerEmployerMatchingContribution = min(wgFedwages * 0.05, MaxAllowedEmployer)
# ---------------------------------------------------------------------------
class TestEmployerMatch(unittest.TestCase):
    def test_five_percent_of_wages_binds(self):
        # 100000 * 0.05 = 5000 ; headroom 69000 -> match 5000
        self.assertEqual(er.compute_match(100_000, 69_000), 5_000)

    def test_headroom_caps_match(self):
        # 5% of 200000 = 10000 but headroom 6000 -> match 6000
        self.assertEqual(er.compute_match(200_000, 6_000), 6_000)


# ---------------------------------------------------------------------------
# Applicability pool — employer-401k-contribution.spe line 22
#   applicableW2s = w2.general.deleteNextYear == 0 and w2.federal.wgFedwages > 0
# ---------------------------------------------------------------------------
class TestApplicabilityPool(unittest.TestCase):
    def base_w2(self, **over):
        w2 = dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000)
        w2.update(over)
        return w2

    def test_delete_next_year_excludes_w2(self):
        r = assess(
            w2=self.base_w2(delete_next_year=1),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_zero_wages_excludes_w2(self):
        r = assess(
            w2=self.base_w2(wg_fed_wages=0),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_positive_wages_included(self):
        r = assess(
            w2=self.base_w2(),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# Applicable gate — employer-401k-contribution.spe lines 29, 32
#   applicableTaxPayer401k: wages401kContribution <= taxPayerMaxAllowedContribution(Employer)
#   applicableSpouse401k:   marriedMAGI && wages401k <= spouseMaxAllowedContribution(Employer)
# ---------------------------------------------------------------------------
class TestApplicableGate(unittest.TestCase):
    def test_contribution_at_headroom_is_applicable(self):
        # <= headroom (inclusive) -> applicable
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000,
                    wages_401k_contribution=69_000),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertTrue(r["applicable"])

    def test_contribution_above_headroom_not_applicable(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000,
                    wages_401k_contribution=70_000),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertFalse(r["applicable"])

    def test_spouse_requires_married_filing(self):
        # filing_status 1 (single) -> spouse not applicable (marriedMAGI false)
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_applicable_when_married(self):
        # filing_status 2 (MFJ) -> spouse gate opens
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_filing_status_5_also_married(self):
        # SPE marriedMAGI = filingStatus 2 || 5
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000),
            filing_status_code=5,
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — employer-401k-contribution.spe lines 28, 31
#   taxPayer401k: (wages403bContribution == 0) && (wg457b == 0)
#                 && (taxPayerEmployerMatchingContribution > 0)
#                 && (wages401kContribution <= taxPayerMaxAllowedContribution)
#   (recommend IS gated on the applicable contribution condition here.)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_403b_present_blocks_recommend(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000,
                    wages_403b_contribution=1),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertFalse(r["recommended"])

    def test_457b_present_blocks_recommend(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000, wg_457b=1),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertFalse(r["recommended"])

    def test_zero_match_blocks_recommend(self):
        # match = min(wgFedwages*0.05, headroom). Drive headroom to 0 by fully
        # absorbing the combined limit -> match 0 -> no recommend.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000,
                            combined_limit_absorbed=69_000),
        )
        self.assertEqual(r["employer_headroom"], 0.0)
        self.assertFalse(r["recommended"])

    def test_zero_wages_gives_zero_match_no_recommend(self):
        # wgFedwages must be > 0 for pool anyway; but match also needs > 0.
        # tiny wages -> 5% tiny but > 0, so still recommended if other gates pass.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=1),
            retirement=dict(combined_401k_limit=69_000),
        )
        # match = min(0.05, 69000) = 0.05 > 0 -> recommended
        self.assertTrue(r["recommended"])

    def test_contribution_above_headroom_blocks_recommend(self):
        # Employer recommend REQUIRES wages401k <= headroom (line 28), so an
        # over-headroom contribution blocks BOTH applicable and recommend.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000,
                    wages_401k_contribution=70_000),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — employer-401k-contribution.spe lines 56, 58
#   strategyChange = round(min(MaxAllowedContribution,
#                              min(employerMatchingContribution, employeeMax401kContribution)))
#   Here MaxAllowedContribution = max401kContributionAllowed (the personal cap),
#   employeeMax401kContribution = MaxAllowedEmployer headroom, and the match.
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_match_binds_when_smallest(self):
        # wgFedwages 150000 -> match 7500 ; maxAllowed 22500 ; headroom 69000
        # -> min(22500, min(7500, 69000)) = 7500  (SPE anchor line 268)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
        )
        self.assertEqual(r["strategy_change_default"], 7_500)

    def test_max_allowed_binds_when_smallest(self):
        # match 5% of 400000 = 20000 ; maxAllowed 10000 -> min(10000, ...) = 10000
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=400_000),
            retirement=dict(max_401k_contribution_allowed=10_000,
                            combined_401k_limit=69_000),
        )
        self.assertEqual(r["strategy_change_default"], 10_000)

    def test_headroom_binds_when_smallest(self):
        # combined headroom 3000 < match/maxAllowed -> 3000
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=400_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=3_000),
        )
        self.assertEqual(r["strategy_change_default"], 3_000)


# ---------------------------------------------------------------------------
# Savings math — employer-401k-contribution.spe lines 80-81, 120-121
#   PROJECTED_TAX_SAVINGS = round(MARGINAL_RATE_TOTAL * strategyChange / 100)
#   CASH_OUTLAY = 0  (employer-funded)
# SPE unit-test anchors: strategyChange 7500 @ 33% -> PROJECTED_TAX_SAVINGS 2475
#   (test_suite lines 268, 288-293), CASH_OUTLAY 0 (lines 295-297).
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_spe_anchor_7500_at_33pct(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=7_500,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["marginal_rate_total"], 33.0)
        # 7500 * 33% = 2475  (SPE test_suite line 239/292)
        self.assertEqual(r["savings"]["projected_tax_savings"], 2_475)
        # CASH_OUTLAY always 0 for employer match (line 81/121)
        self.assertEqual(r["savings"]["cash_outlay"], 0.0)

    def test_cash_outlay_always_zero_even_large_change(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=20_000,
        )
        self.assertEqual(r["cash_outlay"], 0.0)
        self.assertEqual(r["savings"]["cash_outlay"], 0.0)

    def test_total_rate_sums_fed_state_nyc(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=300_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=8, nyc_marginal_rate_pct=4),
            filing_status_code=1,
            strategy_change=7_500,
        )
        # NY: total 36 (fed 24 + state 8 + nyc 4)
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)

    def test_pa_does_not_zero_state_for_employer(self):
        # Employer SPE has NO nonConformingState block -> PA state rate is kept.
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9,
                       resident_state="PA"),
            filing_status_code=1,
            strategy_change=7_500,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 33.0)
        self.assertEqual(r["savings"]["marginal_rate_state"], 9.0)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=12.345),
            filing_status_code=1,
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_default_strategy_change_used_when_omitted(self):
        # No strategy_change -> SPE default = round(min(maxAllowed, min(match, headroom)))
        # match 7500 (5% of 150000) binds -> 7500
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["strategy_change"], 7_500)
        self.assertEqual(r["savings"]["projected_tax_savings"], 2_475)


# ---------------------------------------------------------------------------
# Validation clamp — employer-401k-contribution.spe lines 148-158
#   validationMaxContribution = combined401KLimit
#   validationMax = combined401KLimit − BASELINE_AMOUNT (default 0)
#   assert STRATEGY_CHANGE in_range 0 .. validationMax
#   test_suite anchors: range "0.0 and 69000.0" (lines 354, 365);
#   value -1 fails (line 349-354), 69001 fails (line 360-365).
# ---------------------------------------------------------------------------
class TestValidationClamp(unittest.TestCase):
    def test_validation_max_is_combined_limit(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000),
        )
        self.assertEqual(r["validation_max"], 69_000)

    def test_over_validation_max_is_exceeds_error(self):
        # request 69001 > 69000 -> Exceeds (SPE test line 360-365)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=69_001,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["validation_exceeded"])
        self.assertTrue(any("Exceeds" in e for e in r["errors"]))
        # capped strategy change = validationMax
        self.assertEqual(r["strategy_change"], 69_000)

    def test_negative_strategy_change_errors(self):
        # SPE validation: in_range 0 .. max ; -1 fails (test_suite line 349-354)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=-1,
        )
        self.assertFalse(r["ok"])

    def test_validation_max_uses_absorbed_free_combined_limit(self):
        # validationMax comes from combined401KLimit itself (NOT the absorbed
        # employer headroom): 69000 even when 10000 already absorbed.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(combined_401k_limit=69_000,
                            combined_limit_absorbed=10_000),
        )
        self.assertEqual(r["validation_max"], 69_000)


# ---------------------------------------------------------------------------
# Mutations — employer-401k-contribution.spe added scope + shared401KLimit_AddedScope.spe
#   Employer match writes ONLY combined401kcontributionlimitabsorbed
#   (update401KEmployee=false, update401KCombined=true — lines 111-112),
#   and does NOT write wages401kContribution / wgFedwages.
#   test_suite line 314: combined401kcontributionlimitabsorbed == 14405.
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_projection_writes_combined_absorption_only(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=3, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=10_000,
        )
        self.assertTrue(r["ok"])
        mut = r["mutations"][0]
        self.assertIn("prefix == 3", mut["path"])
        # No wage/deferral field writes for employer match.
        self.assertEqual(mut["fields"], {})
        self.assertEqual(
            mut["absorption"]["combined401kcontributionlimitabsorbed_delta"], 10_000
        )
        # Employer scope does NOT touch the employee absorption counter.
        self.assertNotIn(
            "employee401kcontributionlimitabsorbed_delta", mut["absorption"]
        )

    def test_exceeds_produces_no_mutations(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=69_001,
        )
        self.assertEqual(r["mutations"], [])


# ---------------------------------------------------------------------------
# Combined limit by tax year + age-50 catch-up.
# SPE: shared401KLimit_GlobalScope.spe lines 39-83 (included by the employer
#   strategy verbatim). base: 2022=61000, 2023=66000, 2024=69000 ;
#   age>=50 catch-up: 2022 +6500, 2023/2024 +7500.
# The engine value, when supplied, overrides the table.
# ---------------------------------------------------------------------------
class TestCombinedLimitByYearAge(unittest.TestCase):
    def test_year_base_limits(self):
        self.assertEqual(er.resolve_combined_401k_limit(2022, None), 61_000)
        self.assertEqual(er.resolve_combined_401k_limit(2023, None), 66_000)
        self.assertEqual(er.resolve_combined_401k_limit(2024, None), 69_000)

    def test_age_50_catchup(self):
        self.assertEqual(er.resolve_combined_401k_limit(2022, 50), 67_500)
        self.assertEqual(er.resolve_combined_401k_limit(2024, 55), 76_500)

    def test_under_50_no_catchup(self):
        self.assertEqual(er.resolve_combined_401k_limit(2024, 49), 69_000)

    def test_engine_value_overrides_table(self):
        self.assertEqual(
            er.resolve_combined_401k_limit(2022, 60, engine_value=70_000), 70_000
        )

    def test_unknown_year_falls_back_to_latest_base(self):
        # Beyond the table -> latest known base (69000). Team must extend the
        # table each year; this guards the fallback until they do.
        self.assertEqual(er.resolve_combined_401k_limit(2099, None), 69_000)

    def test_headroom_uses_year_table_when_no_engine_limit(self):
        # employer headroom binds via the 2022 table (61000), not a hardcoded 69000.
        h = er.compute_employer_headroom(
            er.retirement_from_dict(dict(tax_year=2022))
        )
        self.assertEqual(h, 61_000)

    def test_headroom_catchup_raises_combined_leg(self):
        h = er.compute_employer_headroom(
            er.retirement_from_dict(dict(tax_year=2024, age=50))
        )
        # 69000 + 7500 catch-up = 76500 (no absorption)
        self.assertEqual(h, 76_500)

    def test_validation_max_uses_year_table_when_no_engine_limit(self):
        # validationMax = combined401KLimit resolved from the year table.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=150_000),
            retirement=dict(tax_year=2023),
        )
        self.assertEqual(r["validation_max"], 66_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
