#!/usr/bin/env python3
"""
SPE-fidelity tests for the 403(b) Employer Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  403b Employer Contribution/employer-403b-contribution.spe
  SPE limits:   tax-strategy-content/IndUS/strategies/common/
                  shared401KLimit_GlobalScope.spe
                  shared401KLimit_GlobalScope_strategyLimit.spe
                  shared401KLimit_GlobalScope_validation.spe
                  shared401KLimit_AddedScope.spe
  Python tool:  skills/income_tax/assisted/403b-employer/tools/er_403b.py

IMPORTANT — which headroom formula this strategy uses:
  The 403(b) EMPLOYER SPE (employer-403b-contribution.spe lines 18-19) assigns
    taxPayerMaxAllowedContribution = taxPayerMaxAllowedContributionEmployee
  i.e. it uses the *employee* baseline-subtraction headroom
  (shared401KLimit_GlobalScope_strategyLimit.spe line 9), NOT the employer
  combined-limit formula (line 12) that the 401k EMPLOYER SPE uses. So this
  tool's compute_employee_headroom is the SPE-faithful choice here.

The purpose of the tool is two-fold — applicability and savings estimate — so
the suite covers BOTH: every condition / threshold / clamp from the SPE, plus
the savings + validation math.

Run:  python3 -m unittest test_403b_employer -v
  (from ita-rules/tests so spe_loader is importable)
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

er = load_tool(
    "skills/income_tax/assisted/403b-employer/tools/er_403b.py", "er_403b"
)


def assess(**payload):
    return er.assess_from_dict(payload)


def savings(**payload):
    return er.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Headroom formula — shared401KLimit_GlobalScope_strategyLimit.spe line 9
#   taxPayerMaxAllowedContributionEmployee =
#     min( max(maxAllowed - baselineSum - employeeAbsorbed, 0),
#          max(combinedLimit - baselineSum - combinedAbsorbed, 0) )
#   baselineSum = total401k + totalRoth401k + total403b + totalRoth403b + solo401k
#   (403b EMPLOYER uses this employee formula — SPE primary lines 18-19)
# ---------------------------------------------------------------------------
class TestHeadroomFormula(unittest.TestCase):
    def h(self, **r):
        return er.compute_employee_headroom(er.retirement_from_dict(r))

    def test_simple_max_allowed_binds(self):
        # maxAllowed 22500, combined 69000, nothing used -> min(22500, 69000)=22500
        self.assertEqual(self.h(max_401k_contribution_allowed=22_500), 22_500)

    def test_baseline_reduces_headroom(self):
        # 22500 - 5000(403b) = 17500 ; combined 69000 - 5000 = 64000 -> 17500
        self.assertEqual(
            self.h(max_401k_contribution_allowed=22_500, total_403b=5_000), 17_500
        )

    def test_all_baseline_buckets_subtracted(self):
        # 401k+roth401k+403b+roth403b+solo all reduce the pool
        h = self.h(
            max_401k_contribution_allowed=30_000,
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
            max_401k_contribution_allowed=22_500,
            employee_limit_absorbed=5_000,
            combined_limit_absorbed=0,
        )
        self.assertEqual(h, 17_500)

    def test_combined_limit_can_bind(self):
        # combined smaller than max-allowed leg -> combined binds
        h = self.h(
            max_401k_contribution_allowed=22_500,
            combined_401k_limit=10_000,
        )
        self.assertEqual(h, 10_000)

    def test_negative_clamped_to_zero(self):
        # over-contributed baseline -> max(...,0) both legs -> 0, not negative
        h = self.h(max_401k_contribution_allowed=22_500, total_403b=30_000)
        self.assertEqual(h, 0.0)


# ---------------------------------------------------------------------------
# Applicability pool — employer-403b-contribution.spe line 22
#   applicableW2s = w2.general.deleteNextYear == 0 and w2.federal.wgFedwages > 0
# ---------------------------------------------------------------------------
class TestApplicabilityPool(unittest.TestCase):
    def base_w2(self, **over):
        # 403b contribution present so recommend gate (wages403b > 0) can open
        w2 = dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                  wages_403b_contribution=5_000)
        w2.update(over)
        return w2

    def test_delete_next_year_excludes_w2(self):
        r = assess(
            w2=self.base_w2(delete_next_year=1),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_zero_wages_excludes_w2(self):
        r = assess(
            w2=self.base_w2(wg_fed_wages=0),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_positive_wages_included(self):
        r = assess(
            w2=self.base_w2(),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# Applicable gate — employer-403b-contribution.spe lines 32-33
#   applicableTaxPayer403b: wages403bContribution <= taxPayerMaxAllowedContribution
#   applicableSpouse403b:   marriedMAGI && wages403b <= spouseMaxAllowedContribution
# ---------------------------------------------------------------------------
class TestApplicableGate(unittest.TestCase):
    def test_contribution_at_headroom_is_applicable(self):
        # <= headroom (inclusive) -> applicable
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=22_500),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])

    def test_contribution_above_headroom_not_applicable(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=23_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])

    def test_spouse_requires_married_filing(self):
        # filing_status 1 (single) -> spouse not applicable (marriedMAGI false)
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_applicable_when_married(self):
        # filing_status 2 (MFJ) -> spouse gate opens
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_filing_status_5_also_married(self):
        # SPE marriedMAGI = filingStatus 2 || 5
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=5,
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — employer-403b-contribution.spe lines 29-30
#   taxPayer403b: wages403bContribution > 0
#                 && taxPayerEmployerMatchingContribution > 0
#                 && wages403bContribution <= taxPayerMaxAllowedContribution
#   employer match = min(wgFedwages * 0.05, maxAllowed)  (SPE lines 26-27)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_zero_403b_blocks_recommend(self):
        # wages403bContribution must be > 0 for the employer strategy
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=0),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["recommended"])

    def test_zero_match_blocks_recommend(self):
        # zero wages -> match = min(0*0.05, headroom) = 0 -> no recommend.
        # (also fails pool gate; both block recommend)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=0,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["recommended"])

    def test_match_is_five_percent_of_wages_capped_by_headroom(self):
        # match = min(wgFedwages*0.05, headroom)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=40_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        # 40000 * 0.05 = 2000 ; headroom 22500 - 1000 = 21500 -> match 2000
        self.assertEqual(r["employer_match"], 2_000)
        self.assertTrue(r["recommended"])

    def test_match_capped_by_headroom_when_headroom_small(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=0),
            retirement=dict(max_401k_contribution_allowed=1_000),
        )
        # 100000*0.05 = 5000 but headroom 1000 -> match 1000
        self.assertEqual(r["employer_match"], 1_000)

    def test_contribution_above_headroom_blocks_recommend(self):
        # SPE recommend gate requires wages403b <= maxAllowed
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=30_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — employer-403b-contribution.spe lines 59-60
#   strategyChange = round( min(MaxAllowedContribution,
#                               min(employerMatchingContribution,
#                                   employeeMax403bContribution)) )
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_match_binds_default(self):
        # match = min(100000*0.05, 22500)=5000 ; headroom 22500 ; max 22500 -> 5000
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["strategy_change_default"], 5_000)

    def test_headroom_binds_default(self):
        # match=5000, but headroom 800 (22500-... n/a) -> min pulls headroom
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=0),
            retirement=dict(max_401k_contribution_allowed=800),
        )
        # match = min(5000, 800) = 800 ; headroom 800 ; max 800 -> 800
        self.assertEqual(r["strategy_change_default"], 800)

    def test_spe_anchor_2250(self):
        # SPE test_suite 'add recommendation' line 262: strategyChange == 2250
        # wages 45000 -> match 2250 ; headroom 27000-5000=22000 ; max 27000 -> 2250
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=45_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=27_000,
                            combined_401k_limit=69_000),
        )
        self.assertEqual(r["strategy_change_default"], 2_250)


# ---------------------------------------------------------------------------
# Savings math — employer-403b-contribution.spe lines 79-80, 125-126
#   PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE * MARGINAL_RATE_TOTAL / 100)
#   CASH_OUTLAY = 0   (employer match is a match, not the employee's cash)
# SPE unit-test anchor (line 262-280): 2250 @ 20% -> 450 savings, cash 0.
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_spe_anchor_2250_at_20pct(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=45_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=27_000,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8),
            filing_status_code=1,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["marginal_rate_total"], 20.0)
        self.assertEqual(r["savings"]["strategy_change"], 2_250)
        self.assertEqual(r["savings"]["projected_tax_savings"], 450)
        self.assertEqual(r["savings"]["cash_outlay"], 0)

    def test_cash_outlay_always_zero(self):
        # SPE line 80/126: CASH_OUTLAY = 0 for employer 403(b)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=5_000,
        )
        self.assertEqual(r["savings"]["cash_outlay"], 0)

    def test_total_rate_sums_fed_state_nyc(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=300_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=8, nyc_marginal_rate_pct=4),
            filing_status_code=1,
            strategy_change=5_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12.345),
            filing_status_code=1,
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_default_strategy_change_used_when_omitted(self):
        # No strategy_change -> SPE default (match binds) = 5000
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["strategy_change"], 5_000)
        # 5000 * 33% = 1650
        self.assertEqual(r["savings"]["projected_tax_savings"], 1_650)


# ---------------------------------------------------------------------------
# Validation clamp — employer-403b-contribution.spe lines 153-166
#   validationMax = validationMaxContribution (employee headroom)
#   assert STRATEGY_CHANGE in_range 0 .. validationMax
#   ITA UI copy when over: "Exceeds $X" and totals stay 0.
# ---------------------------------------------------------------------------
class TestValidationClamp(unittest.TestCase):
    def test_over_validation_max_is_exceeds_error(self):
        # headroom/validation 22500, request 30000 -> Exceeds
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=30_000,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["validation_exceeded"])
        self.assertTrue(any("Exceeds" in e for e in r["errors"]))
        # capped strategy change = validationMax
        self.assertEqual(r["strategy_change"], 22_500)

    def test_negative_strategy_change_errors(self):
        # SPE validation: in_range 0 .. max ; -1 fails (test line 406-413)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=-1,
        )
        self.assertFalse(r["ok"])

    def test_27000_in_range_no_error(self):
        # SPE test line 398: STRATEGY_CHANGE 27000 valid when validationMax 27000
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=27_000,
                            combined_401k_limit=69_000),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8),
            filing_status_code=1,
            strategy_change=27_000,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["strategy_change"], 27_000)


# ---------------------------------------------------------------------------
# Mutations — employer-403b-contribution.spe lines 104-105 + AddedScope.
#   update401KEmployee = false ; update401KCombined = true
#   => only combined401kcontributionlimitabsorbed is incremented; the tool
#      does NOT write wages403bContribution / wgFedwages for the employer match.
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_combined_absorption_only(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=3, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=4_000,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        mut = r["mutations"][0]
        self.assertIn("prefix == 3", mut["path"])
        # employer 403b does NOT write wages/box1 fields
        self.assertEqual(mut["fields"], {})
        self.assertEqual(
            mut["absorption"]["combined401kcontributionlimitabsorbed_delta"], 4_000
        )
        # employee absorbed must NOT be written (update401KEmployee == false)
        self.assertNotIn(
            "employee401kcontributionlimitabsorbed_delta", mut["absorption"]
        )

    def test_exceeds_produces_no_mutations(self):
        # over validationMax -> no projection writes (ITA totals stay 0)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=30_000,
        )
        self.assertEqual(r["mutations"], [])


# ---------------------------------------------------------------------------
# Combined limit by tax year + age-50 catch-up.
# SPE: shared401KLimit_GlobalScope.spe lines 39-83.
#   base: 2022=61000, 2023=66000, 2024=69000
#   age>=50 catch-up: 2022 +6500, 2023/2024 +7500
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
        # combined leg binds via the 2022 table (61000), not a hardcoded 69000.
        h = er.compute_employee_headroom(
            er.retirement_from_dict(
                dict(max_401k_contribution_allowed=70_000, tax_year=2022)
            )
        )
        self.assertEqual(h, 61_000)

    def test_headroom_catchup_raises_combined_leg(self):
        h = er.compute_employee_headroom(
            er.retirement_from_dict(
                dict(max_401k_contribution_allowed=80_000, tax_year=2024, age=50)
            )
        )
        # combined leg = 76500 (69000 + 7500); max-allowed leg = 80000 -> min
        self.assertEqual(h, 76_500)


# ---------------------------------------------------------------------------
# State non-conformity is NJ-only for 403b EMPLOYER
# (employer-403b-contribution.spe lines 117-119: only `resState == 'NJ'`).
# SPE test_suite confirms: NJ -> state rate dropped (line 331-332);
# PA -> state rate preserved / conforms (line 365-366).
# ---------------------------------------------------------------------------
class TestNonConformingStates(unittest.TestCase):
    def test_nj_is_non_conforming(self):
        self.assertEqual(er.NON_CONFORMING_STATES, frozenset({"NJ"}))

    def test_nj_zeros_state_and_nyc(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8,
                       resident_state="NJ"),
            filing_status_code=1,
            strategy_change=5_000,
        )
        # NJ non-conforming -> fed only (SPE line 328-329 total 12)
        self.assertEqual(r["savings"]["marginal_rate_total"], 12.0)
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)

    def test_pa_and_others_conform(self):
        # PA conforms here (contrast with 401k EE). NE/NM/RI conform too.
        for st in ("PA", "NE", "NM", "RI", "CA", "NY", ""):
            r = savings(
                w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                        wages_403b_contribution=5_000),
                retirement=dict(max_401k_contribution_allowed=22_500),
                rates=dict(federal_marginal_rate_pct=12,
                           state_marginal_rate_pct=8, resident_state=st),
                filing_status_code=1,
                strategy_change=5_000,
            )
            self.assertEqual(
                r["savings"]["marginal_rate_total"], 20.0,
                f"state {st!r} should conform",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
