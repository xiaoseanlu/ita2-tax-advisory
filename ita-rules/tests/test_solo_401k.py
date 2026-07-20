#!/usr/bin/env python3
"""
SPE-fidelity tests for the Solo 401(k) Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  Solo 401k Contribution/Solo401k.spe
  SPE EIN match: tax-strategy-content/IndUS/strategies/common/matchEIN.spe
  SPE limits:   tax-strategy-content/IndUS/strategies/common/
                  shared401KLimit_GlobalScope.spe
                  shared401KLimit_GlobalScope_strategyLimit.spe
                  shared401KLimit_GlobalScope_validation.spe
  Python tool:  skills/income_tax/assisted/solo-401k/tools/solo_401k.py

Solo 401(k) differs from the W-2 401(k): it keys on self-employment /
Schedule-C or S-corp income (NOT earned income alone), has an opposite-EIN
recommend split, and its own contribution-limit math.

The tool is two-fold — applicability and savings estimate — so the suite covers
BOTH: every gate / threshold / clamp from the SPE plus the savings + validation
math and mutations.

Run:  python3 -m unittest test_solo_401k -v
  or:  python3 test_solo_401k.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

solo = load_tool(
    "skills/income_tax/assisted/solo-401k/tools/solo_401k.py", "solo_401k"
)


def assess(**payload):
    return solo.assess_from_dict(payload)


def savings(**payload):
    return solo.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Headroom formula — shared401KLimit_GlobalScope_strategyLimit.spe:
#   taxPayerMaxAllowedContributionEmployee =
#     min( max(maxSolo - baselineSum - employeeAbsorbed, 0),
#          max(combinedLimit - baselineSum - combinedAbsorbed, 0) )
#   baselineSum = total401k + totalRoth401k + total403b + totalRoth403b + solo401k
# ---------------------------------------------------------------------------
class TestHeadroomFormula(unittest.TestCase):
    def h(self, **r):
        return solo.compute_employee_headroom(solo.retirement_from_dict(r))

    def test_simple_max_allowed_binds(self):
        # maxSolo 22500, combined default 69000, nothing used -> min(22500,69000)
        self.assertEqual(self.h(max_solo401k_contribution_allowed=22_500), 22_500)

    def test_baseline_reduces_headroom(self):
        # 22500 - 5000(401k) = 17500 ; combined 69000 - 5000 = 64000 -> 17500
        self.assertEqual(
            self.h(max_solo401k_contribution_allowed=22_500, total_401k=5_000),
            17_500,
        )

    def test_all_baseline_buckets_subtracted(self):
        # 401k+roth401k+403b+roth403b+solo all reduce the pool
        h = self.h(
            max_solo401k_contribution_allowed=30_000,
            total_401k=1_000,
            total_roth_401k=2_000,
            total_403b=3_000,
            total_roth_403b=4_000,
            baseline_solo401k=5_000,
        )
        # 30000 - 15000 = 15000 ; combined 69000 - 15000 = 54000 -> 15000
        self.assertEqual(h, 15_000)

    def test_absorbed_counters_reduce_headroom(self):
        # employee_limit_absorbed reduces the 'a' leg; combined absorbed the 'b' leg
        h = self.h(
            max_solo401k_contribution_allowed=22_500,
            employee_limit_absorbed=5_000,
            combined_limit_absorbed=0,
        )
        self.assertEqual(h, 17_500)

    def test_combined_limit_can_bind(self):
        # combined smaller than max-allowed leg -> combined binds
        h = self.h(
            max_solo401k_contribution_allowed=80_000,
            combined_401k_limit=10_000,
        )
        self.assertEqual(h, 10_000)

    def test_negative_clamped_to_zero(self):
        # over-contributed baseline -> max(...,0) both legs -> 0, not negative
        h = self.h(max_solo401k_contribution_allowed=22_500, total_401k=30_000)
        self.assertEqual(h, 0.0)

    def test_validation_headroom_ignores_absorption(self):
        # shared401KLimit_GlobalScope_validation.spe: same formula WITHOUT
        # subtracting the absorbed counters.
        r = solo.retirement_from_dict(
            dict(
                max_solo401k_contribution_allowed=22_500,
                employee_limit_absorbed=5_000,
                combined_limit_absorbed=5_000,
            )
        )
        self.assertEqual(solo.compute_employee_headroom(r), 17_500)
        self.assertEqual(solo.compute_validation_employee_headroom(r), 22_500)


# ---------------------------------------------------------------------------
# Combined limit by tax year + age-50 catch-up.
# SPE: shared401KLimit_GlobalScope.spe lines 39-83 (%included by Solo401k.spe
# lines 29-31). base: 2022=61000, 2023=66000, 2024=69000 ;
# age>=50 catch-up: 2022 +6500, 2023/2024 +7500. Engine value overrides table.
# (Audit gap: solo_401k.py previously hardcoded 69000 — fixed to mirror ee_401k.)
# ---------------------------------------------------------------------------
class TestCombinedLimitByYearAge(unittest.TestCase):
    def test_year_base_limits(self):
        self.assertEqual(solo.resolve_combined_401k_limit(2022, None), 61_000)
        self.assertEqual(solo.resolve_combined_401k_limit(2023, None), 66_000)
        self.assertEqual(solo.resolve_combined_401k_limit(2024, None), 69_000)

    def test_age_50_catchup(self):
        self.assertEqual(solo.resolve_combined_401k_limit(2022, 50), 67_500)
        self.assertEqual(solo.resolve_combined_401k_limit(2024, 55), 76_500)

    def test_under_50_no_catchup(self):
        self.assertEqual(solo.resolve_combined_401k_limit(2024, 49), 69_000)

    def test_engine_value_overrides_table(self):
        self.assertEqual(
            solo.resolve_combined_401k_limit(2022, 60, engine_value=70_000), 70_000
        )

    def test_unknown_year_falls_back_to_latest_base(self):
        # Beyond the table -> latest known base (69000). Team must extend the
        # table each year; this guards the fallback until they do.
        self.assertEqual(solo.resolve_combined_401k_limit(2099, None), 69_000)

    def test_headroom_uses_year_table_when_no_engine_limit(self):
        # combined leg binds via the 2022 table (61000), not a hardcoded 69000.
        h = solo.compute_employee_headroom(
            solo.retirement_from_dict(
                dict(max_solo401k_contribution_allowed=70_000, tax_year=2022)
            )
        )
        self.assertEqual(h, 61_000)

    def test_headroom_catchup_raises_combined_leg(self):
        h = solo.compute_employee_headroom(
            solo.retirement_from_dict(
                dict(
                    max_solo401k_contribution_allowed=80_000,
                    tax_year=2024,
                    age=50,
                )
            )
        )
        # combined leg = 76500 (69000 + 7500); max-allowed leg = 80000 -> min
        self.assertEqual(h, 76_500)


# ---------------------------------------------------------------------------
# Applicability pool (SE income filter) — Solo401k.spe line 101:
#   applicableSolo401k = soloLoop.seIncome > 0
#                        || sCorp2perWagesTP.size() > 0 || sCorp2perWagesSP.size() > 0
# Earned income ALONE is NOT enough (that's the key Solo-vs-W2 difference).
# ---------------------------------------------------------------------------
class TestApplicabilitySEFilter(unittest.TestCase):
    def base_person(self, **over):
        p = dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )
        p.update(over)
        return p

    def test_se_income_makes_applicable(self):
        r = assess(
            person=self.base_person(all_se_income=50_000),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])

    def test_earned_income_alone_not_applicable(self):
        # SPE line 101 keys on seIncome / scorp wages, NOT earnedIncome.
        r = assess(
            person=self.base_person(
                all_se_income=0, earned_income=80_000, scorp_wages_present=False
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_scorp_wages_make_applicable(self):
        # sCorp2perWages*.size() > 0 opens the applicable pool without seIncome.
        r = assess(
            person=self.base_person(all_se_income=0, scorp_wages_present=True),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])

    def test_no_income_at_all_not_applicable(self):
        r = assess(
            person=self.base_person(all_se_income=0, scorp_wages_present=False),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])


# ---------------------------------------------------------------------------
# Business-without-wages gate + opposite-EIN split.
#   Solo401k.spe line 73-74:  bizExistsWithoutWagesAndScorp*
#   line 114-116: applicable = selector[NoWagesSet, OppositeMatchSet]{opposite==0}
#   -> opposite-EIN match makes the person APPLICABLE, but recommend (line 105,
#      117) requires bizExistsWithoutWagesAndScorp (NOT opposite-EIN alone).
# ---------------------------------------------------------------------------
class TestBizWagesAndOppositeEIN(unittest.TestCase):
    def base_person(self, **over):
        p = dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
        )
        p.update(over)
        return p

    def test_no_qualifying_biz_not_applicable(self):
        # no biz-without-wages AND no opposite-EIN match -> not applicable
        r = assess(
            person=self.base_person(
                biz_exists_without_wages=False, opposite_ein_wage_matches=False
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_biz_without_wages_applicable_and_recommend(self):
        r = assess(
            person=self.base_person(
                biz_exists_without_wages=True, opposite_ein_wage_matches=False
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_opposite_ein_applicable_but_not_recommended(self):
        # SPE selector: opposite-EIN match makes person applicable (line 114)
        # but recommend gate (line 105/117) needs biz-without-wages -> no recommend.
        r = assess(
            person=self.base_person(
                biz_exists_without_wages=False, opposite_ein_wage_matches=True
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])
        self.assertFalse(r["recommended"])
        self.assertTrue(
            any("opposite-EIN" in reason for reason in r["reasons"])
        )


# ---------------------------------------------------------------------------
# Spouse gate — Solo401k.spe line 106/118:
#   applicableSPNoWagesandScorp / applicableSpouse require marriedMAGI
#   marriedMAGI = filingStatus == 2 || 5 (line 10).
# ---------------------------------------------------------------------------
class TestSpouseGate(unittest.TestCase):
    def spouse_person(self, **over):
        p = dict(
            taxpayer_spouse_or_joint="spouse",
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )
        p.update(over)
        return p

    def test_spouse_requires_married_filing(self):
        # filing_status 1 (single) -> spouse not applicable
        r = assess(
            person=self.spouse_person(filing_status_code=1),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_applicable_when_married_2(self):
        r = assess(
            person=self.spouse_person(filing_status_code=2),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_spouse_filing_status_5_also_married(self):
        # SPE marriedMAGI = filingStatus 2 || 5
        r = assess(
            person=self.spouse_person(filing_status_code=5),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])

    def test_taxpayer_unaffected_by_single_filing(self):
        # marriedMAGI gate is spouse-only; taxpayer applicable when single.
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="taxpayer",
                filing_status_code=1,
                all_se_income=50_000,
                biz_exists_without_wages=True,
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# Recommend gate — Solo401k.spe line 117/118:
#   applicableTaxpayer = bizExistsWithoutWagesAndScorp
#                        && maxAllowedContribution > 0
#                        && (sepIRA == 0 || (soloContribution > 0 && sepIRA > 0))
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def base_person(self, **over):
        p = dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )
        p.update(over)
        return p

    def test_zero_headroom_blocks_recommend(self):
        # maxAllowedContribution must be > 0 (strict).
        r = assess(
            person=self.base_person(),
            retirement=dict(max_solo401k_contribution_allowed=0),
        )
        self.assertFalse(r["recommended"])

    def test_sep_ira_without_solo_deferral_blocks_recommend(self):
        # sepIRA > 0 and solo elective deferral 0 -> SEP conflict -> no recommend.
        r = assess(
            person=self.base_person(sep_ira=5_000, solo_elective_deferral=0),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["recommended"])
        self.assertTrue(any("SEP-IRA" in reason for reason in r["reasons"]))

    def test_sep_ira_with_solo_deferral_allows_recommend(self):
        # sepIRA > 0 AND soloContribution > 0 -> recommend allowed (SPE line 117).
        r = assess(
            person=self.base_person(sep_ira=5_000, solo_elective_deferral=1),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["recommended"])

    def test_no_sep_ira_recommend_allowed(self):
        r = assess(
            person=self.base_person(sep_ira=0),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — Solo401k.spe line 154:
#   strategyChange = maxSoloAllowed  (= headroom / maxAllowedContribution)
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_default_equals_headroom(self):
        r = savings(
            person=dict(
                taxpayer_spouse_or_joint="taxpayer",
                filing_status_code=1,
                all_se_income=50_000,
                biz_exists_without_wages=True,
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["strategy_change"], 22_500)


# ---------------------------------------------------------------------------
# Savings math — Solo401k.spe lines 181-182 (and added-scope 231-232):
#   PROJECTED_TAX_SAVINGS = round(MARGINAL_RATE_TOTAL * strategyChange / 100)
#   CASH_OUTLAY = strategyChange - PROJECTED_TAX_SAVINGS
# SPE anchor (test_suite line 379-385): 6500 @ 49.3% (Trent Reznor) -> 3204.
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def person(self, **over):
        p = dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )
        p.update(over)
        return p

    def test_spe_anchor_6500_at_49_3pct(self):
        # SPE test_suite line 382-385: MARGINAL_RATE_TOTAL 49.30, change 6500 ->
        # round(49.30 * 6500 / 100) = round(3204.5) = 3204 (half-up)
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=6_500),
            rates=dict(
                federal_marginal_rate_pct=37, state_marginal_rate_pct=12.30
            ),
            strategy_change=6_500,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["marginal_rate_total"], 49.30)
        self.assertEqual(r["savings"]["projected_tax_savings"], 3_204)
        self.assertEqual(r["savings"]["cash_outlay"], 6_500 - 3_204)

    def test_spe_anchor_27000_at_49_3pct(self):
        # SPE test_suite line 445-449 (Molly Ringwald): 27000 @ 49.30 ->
        # round(49.30 * 27000 / 100) = round(13311.0) = 13311; cash 13689.
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=27_000),
            rates=dict(
                federal_marginal_rate_pct=37, state_marginal_rate_pct=12.30
            ),
            strategy_change=27_000,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["projected_tax_savings"], 13_311)
        self.assertEqual(r["savings"]["cash_outlay"], 13_689)

    def test_total_rate_sums_fed_state_nyc(self):
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(
                federal_marginal_rate_pct=24,
                state_marginal_rate_pct=8,
                nyc_marginal_rate_pct=4,
            ),
            strategy_change=22_500,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)

    def test_rounding_is_half_even_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12.345),
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_rounding_half_even_at_exact_half(self):
        # SPE decimalfmt '#' is banker's rounding: 3204.50 -> 3204 (nearest even),
        # NOT 3205. This is the Solo401k.spe test_suite line 385 anchor.
        self.assertEqual(solo._spe_round(3204.50), 3204)
        self.assertEqual(solo._spe_round(3205.50), 3206)

    def test_projected_amount_adds_baseline(self):
        # parameters.PROJECTED_AMOUNT = strategyChange + BASELINE_AMOUNT
        # BASELINE_AMOUNT = solo401kContribution + solo401kCatchUp (line 151/167).
        r = savings(
            person=self.person(solo401k_contribution=1_000, solo401k_catchup=500),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=10_000,
        )
        self.assertEqual(r["baseline_amount"], 1_500)
        self.assertEqual(r["projected_amount"], 11_500)


# ---------------------------------------------------------------------------
# State conformity — Solo401k.spe added scope lines 218-225:
#   nonConformingState = (resState == 'PA') -> zeros state & NYC marginal.
# ---------------------------------------------------------------------------
class TestStateConformity(unittest.TestCase):
    def person(self):
        return dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )

    def test_pa_nonconforming_zeros_state_and_nyc(self):
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(
                federal_marginal_rate_pct=24,
                state_marginal_rate_pct=9,
                nyc_marginal_rate_pct=3,
                resident_state="PA",
            ),
            strategy_change=22_500,
        )
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)
        self.assertEqual(r["savings"]["marginal_rate_nyc"], 0.0)
        self.assertEqual(r["savings"]["marginal_rate_total"], 24.0)
        # 22500 * 24% = 5400
        self.assertEqual(r["savings"]["projected_tax_savings"], 5_400)

    def test_other_states_conform(self):
        for st in ("CA", "NY", "NE", "NJ", "US", ""):
            r = savings(
                person=self.person(),
                retirement=dict(max_solo401k_contribution_allowed=22_500),
                rates=dict(
                    federal_marginal_rate_pct=24,
                    state_marginal_rate_pct=9,
                    resident_state=st,
                ),
                strategy_change=10_000,
            )
            self.assertEqual(
                r["savings"]["marginal_rate_total"], 33.0,
                f"state {st!r} should conform",
            )


# ---------------------------------------------------------------------------
# Validation clamp — Solo401k.spe validation scope lines 262-275:
#   validationMax = Validation*MaxAllowedContributionEmployee (no absorption)
#   assert STRATEGY_CHANGE in_range 0 .. validationMax ; -1 fails (line 657-659).
# ITA UI copy when over: "Exceeds $X" and totals stay 0.
# ---------------------------------------------------------------------------
class TestValidationClamp(unittest.TestCase):
    def person(self):
        return dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )

    def test_over_validation_max_is_exceeds_error(self):
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=30_000,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["validation_exceeded"])
        self.assertTrue(any("Exceeds" in e for e in r["errors"]))
        # capped strategy change = validationMax
        self.assertEqual(r["strategy_change"], 22_500)

    def test_negative_strategy_change_errors(self):
        # SPE validation: in_range 0 .. max ; -1 fails (test_suite line 657-659).
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=-1,
        )
        self.assertFalse(r["ok"])

    def test_at_validation_max_is_ok(self):
        # in_range is inclusive of the max endpoint.
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=22_500,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertFalse(r["validation_exceeded"])

    def test_validation_max_ignores_absorption(self):
        # validation formula uses no absorbed subtraction (line 266).
        r = assess(
            person=self.person(),
            retirement=dict(
                max_solo401k_contribution_allowed=22_500,
                employee_limit_absorbed=5_000,
                combined_limit_absorbed=5_000,
            ),
        )
        self.assertEqual(r["max_allowed_contribution"], 17_500)
        self.assertEqual(r["validation_max"], 22_500)


# ---------------------------------------------------------------------------
# Mutations — added scope lines 204-207:
#   projectionSoloContribution += strategyChange written to tpSEElectDef /
#   spsEElectDef path. Exceeds -> no mutations.
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def person(self, **over):
        p = dict(
            taxpayer_spouse_or_joint="taxpayer",
            filing_status_code=1,
            all_se_income=50_000,
            biz_exists_without_wages=True,
        )
        p.update(over)
        return p

    def test_taxpayer_mutation_path_and_delta(self):
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=10_000,
        )
        self.assertTrue(r["ok"])
        mut = r["mutations"][0]
        self.assertIn("tpSEElectDef", mut["path"])
        self.assertEqual(mut["fields"]["delta"], 10_000)

    def test_spouse_mutation_path(self):
        r = savings(
            person=self.person(
                taxpayer_spouse_or_joint="spouse", filing_status_code=2
            ),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=10_000,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        mut = r["mutations"][0]
        self.assertIn("spsEElectDef", mut["path"])

    def test_exceeds_produces_no_mutations(self):
        r = savings(
            person=self.person(),
            retirement=dict(max_solo401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            strategy_change=30_000,
        )
        self.assertEqual(r["mutations"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
