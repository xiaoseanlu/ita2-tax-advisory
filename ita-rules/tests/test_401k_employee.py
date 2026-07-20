#!/usr/bin/env python3
"""
SPE-fidelity tests for the 401(k) Employee Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  401k Employee Contribution/employee-401k-contribution.spe
  SPE limits:   tax-strategy-content/IndUS/strategies/common/
                  shared401KLimit_GlobalScope.spe
                  shared401KLimit_GlobalScope_strategyLimit.spe
                  shared401KLimit_GlobalScope_validation.spe
  Python tool:  skills/income_tax/assisted/401k-employee/tools/ee_401k.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: every condition / threshold / clamp from the SPE, plus the
savings + validation math.

Run:  python3 -m unittest ita-rules/tests/test_401k_employee.py -v
  or:  python3 ita-rules/tests/test_401k_employee.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

ee = load_tool(
    "skills/income_tax/assisted/401k-employee/tools/ee_401k.py", "ee_401k"
)


def assess(**payload):
    return ee.assess_from_dict(payload)


def savings(**payload):
    return ee.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Headroom formula — shared401KLimit_GlobalScope_strategyLimit.spe line 9
#   min( max(maxAllowed - baselineSum - employeeAbsorbed, 0),
#        max(combinedLimit - baselineSum - combinedAbsorbed, 0) )
#   baselineSum = total401k + totalRoth401k + total403b + totalRoth403b + solo401k
#   (NOTE: 457b / roth457b are NOT subtracted from the employee limit)
# ---------------------------------------------------------------------------
class TestHeadroomFormula(unittest.TestCase):
    def h(self, **r):
        return ee.compute_employee_headroom(ee.retirement_from_dict(r))

    def test_simple_max_allowed_binds(self):
        # maxAllowed 22500, combined 69000, nothing used -> min(22500, 69000)=22500
        self.assertEqual(self.h(max_401k_contribution_allowed=22_500), 22_500)

    def test_baseline_reduces_headroom(self):
        # 22500 - 5000(401k) = 17500 ; combined 69000 - 5000 = 64000 -> 17500
        self.assertEqual(
            self.h(max_401k_contribution_allowed=22_500, total_401k=5_000), 17_500
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

    def test_457b_not_subtracted_from_employee_limit(self):
        # SPE employee formula omits 457b/roth457b. Tool has no such field ->
        # confirm passing generic buckets doesn't accidentally include them.
        # (regression guard: baseline_sum has exactly 5 terms)
        h = self.h(max_401k_contribution_allowed=22_500, total_401k=22_500)
        self.assertEqual(h, 0.0)

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
        h = self.h(max_401k_contribution_allowed=22_500, total_401k=30_000)
        self.assertEqual(h, 0.0)

    def test_validation_headroom_ignores_absorption(self):
        # shared401KLimit_GlobalScope_validation.spe: same formula WITHOUT
        # subtracting the absorbed counters.
        r = ee.retirement_from_dict(
            dict(
                max_401k_contribution_allowed=22_500,
                employee_limit_absorbed=5_000,
                combined_limit_absorbed=5_000,
            )
        )
        self.assertEqual(ee.compute_employee_headroom(r), 17_500)
        self.assertEqual(ee.compute_validation_employee_headroom(r), 22_500)


# ---------------------------------------------------------------------------
# Applicability pool — employee-401k-contribution.spe line 20
#   applicableW2s = w2.general.deleteNextYear == 0 and w2.federal.wgFedwages > 0
# ---------------------------------------------------------------------------
class TestApplicabilityPool(unittest.TestCase):
    def base_w2(self, **over):
        w2 = dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000)
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
# Applicable gate — employee-401k-contribution.spe lines 24-25
#   applicableTaxPayer401k: wages401kContribution <= taxPayerMaxAllowedContribution
#   applicableSpouse401k:   marriedMAGI && wages401k <= spouseMaxAllowedContribution
# ---------------------------------------------------------------------------
class TestApplicableGate(unittest.TestCase):
    def test_contribution_at_headroom_is_applicable(self):
        # <= headroom (inclusive) -> applicable
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_401k_contribution=22_500),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])

    def test_contribution_above_headroom_not_applicable(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_401k_contribution=23_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])

    def test_spouse_requires_married_filing(self):
        # filing_status 1 (single) -> spouse not applicable (marriedMAGI false)
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_applicable_when_married(self):
        # filing_status 2 (MFJ) -> spouse gate opens
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_filing_status_5_also_married(self):
        # SPE marriedMAGI = filingStatus 2 || 5
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=5,
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — employee-401k-contribution.spe lines 26-27
#   taxPayer401k: wages403bContribution == 0 && wg457b == 0
#                 && taxPayerMaxAllowedContribution > 0
#   (recommend is INDEPENDENT of applicable — audit fix item)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_403b_present_blocks_recommend(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["recommended"])

    def test_457b_present_blocks_recommend(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000, wg_457b=1),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["recommended"])

    def test_zero_headroom_blocks_recommend(self):
        # headroom must be > 0 (strictly). maxAllowed 0 -> no recommend.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=0),
        )
        self.assertFalse(r["recommended"])

    def test_recommend_independent_of_applicable(self):
        # Contribution ABOVE headroom -> not applicable, but 403b/457b are zero
        # and headroom > 0, so recommend can still be True (SPE separates sets).
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_401k_contribution=30_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["applicable"])
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — employee-401k-contribution.spe line 53
#   strategyChange = min(fedwages, employeeMax401kContribution)
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_headroom_binds_when_below_wages(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["strategy_change_default"], 22_500)

    def test_wages_bind_when_below_headroom(self):
        # low wages cap the deferral (can't defer more than you earn)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=10_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["strategy_change_default"], 10_000)


# ---------------------------------------------------------------------------
# Savings math — employee-401k-contribution.spe lines 80-81
#   PROJECTED_TAX_SAVINGS = round(STRATEGY_CHANGE * MARGINAL_RATE_TOTAL / 100)
#   CASH_OUTLAY = STRATEGY_CHANGE - PROJECTED_TAX_SAVINGS
# SPE unit-test anchor (test_suite line 316,340,345): 22500 @ 33% -> 7425 / 15075
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_spe_anchor_22500_at_33pct(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=22_500,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["marginal_rate_total"], 33.0)
        self.assertEqual(r["savings"]["projected_tax_savings"], 7_425)
        self.assertEqual(r["savings"]["cash_outlay"], 15_075)

    def test_total_rate_sums_fed_state_nyc(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=300_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=8, nyc_marginal_rate_pct=4),
            filing_status_code=1,
            strategy_change=22_500,
        )
        # NY anchor from SPE test line 644: total 36
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)

    def test_pa_nonconforming_zeros_state_and_nyc(self):
        # SPE added-scope state conformity: PA -> nonConformingState -> fed only
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9,
                       resident_state="PA"),
            filing_status_code=1,
            strategy_change=22_500,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 24.0)
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)
        # 22500 * 24% = 5400
        self.assertEqual(r["savings"]["projected_tax_savings"], 5_400)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12.345),
            filing_status_code=1,
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_cash_outlay_adjustment_added(self):
        # added scope line 149-150: cash outlay += totalCashOutlayAdjustments
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
            strategy_change=22_500,
            total_cash_outlay_adjustments=1_000,
        )
        # base cash 15075 + 1000
        self.assertEqual(r["savings"]["cash_outlay"], 16_075)

    def test_default_strategy_change_used_when_omitted(self):
        # No strategy_change -> SPE default min(wages, headroom) = 22500
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24, state_marginal_rate_pct=9),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["strategy_change"], 22_500)
        self.assertEqual(r["savings"]["projected_tax_savings"], 7_425)


# ---------------------------------------------------------------------------
# Validation clamp — employee-401k-contribution.spe lines 92-99, 199-213
#   validationMax = min(baseWages|projectionWages, Validation*Employee)
#   assert STRATEGY_CHANGE in_range 0 .. validationMax
#   ITA UI copy when over: "Exceeds $X" and totals stay 0.
# ---------------------------------------------------------------------------
class TestValidationClamp(unittest.TestCase):
    def test_over_validation_max_is_exceeds_error(self):
        # headroom/validation both 22500, request 30000 -> Exceeds
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
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
        # SPE validation: in_range 0 .. max ; -1 fails (test_suite line 702-707)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=-1,
        )
        self.assertFalse(r["ok"])

    def test_validation_max_uses_base_wages_when_present(self):
        # SPE line 90-92: base wages preferred over projection wages
        # base wages 15000 < validation headroom 22500 -> validationMax 15000
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    base_wg_fed_wages=15_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["validation_max"], 15_000)

    def test_validation_max_falls_back_to_projection_wages(self):
        # No base wages -> projection wgFedwages used
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=18_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["validation_max"], 18_000)

    def test_zero_validation_max_still_exceeds_when_requested_positive(self):
        # audit fix: Exceeds fires even when validationMax == 0
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_401k_contribution=22_500),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            total_401k=22_500),  # headroom -> 0
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=5_000,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["validation_exceeded"])
        self.assertEqual(r["validation_max"], 0.0)


# ---------------------------------------------------------------------------
# Mutations — added scope lines 122-123, 126-127
#   wages401kContribution += strategyChange ; wgFedwages -= strategyChange
#   employee/combined absorbed += strategyChange
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_projection_writes_and_absorption(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=3, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24),
            filing_status_code=1,
            strategy_change=10_000,
        )
        self.assertTrue(r["ok"])
        mut = r["mutations"][0]
        self.assertIn("prefix == 3", mut["path"])
        self.assertEqual(mut["fields"]["wages401kContribution_delta"], 10_000)
        self.assertEqual(mut["fields"]["wgFedwages_delta"], -10_000)
        self.assertEqual(
            mut["absorption"]["employee401kcontributionlimitabsorbed_delta"], 10_000
        )
        self.assertEqual(
            mut["absorption"]["combined401kcontributionlimitabsorbed_delta"], 10_000
        )

    def test_exceeds_produces_no_mutations(self):
        # over validationMax -> no projection writes (ITA totals stay 0)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
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
        self.assertEqual(ee.resolve_combined_401k_limit(2022, None), 61_000)
        self.assertEqual(ee.resolve_combined_401k_limit(2023, None), 66_000)
        self.assertEqual(ee.resolve_combined_401k_limit(2024, None), 69_000)

    def test_age_50_catchup(self):
        self.assertEqual(ee.resolve_combined_401k_limit(2022, 50), 67_500)
        self.assertEqual(ee.resolve_combined_401k_limit(2024, 55), 76_500)

    def test_under_50_no_catchup(self):
        self.assertEqual(ee.resolve_combined_401k_limit(2024, 49), 69_000)

    def test_engine_value_overrides_table(self):
        self.assertEqual(
            ee.resolve_combined_401k_limit(2022, 60, engine_value=70_000), 70_000
        )

    def test_unknown_year_falls_back_to_latest_base(self):
        # Beyond the table -> latest known base (69000). Team must extend the
        # table each year; this guards the fallback until they do.
        self.assertEqual(ee.resolve_combined_401k_limit(2099, None), 69_000)

    def test_headroom_uses_year_table_when_no_engine_limit(self):
        # combined leg binds via the 2022 table (61000), not a hardcoded 69000.
        h = ee.compute_employee_headroom(
            ee.retirement_from_dict(
                dict(max_401k_contribution_allowed=70_000, tax_year=2022)
            )
        )
        self.assertEqual(h, 61_000)

    def test_headroom_catchup_raises_combined_leg(self):
        h = ee.compute_employee_headroom(
            ee.retirement_from_dict(
                dict(max_401k_contribution_allowed=80_000, tax_year=2024, age=50)
            )
        )
        # combined leg = 76500 (69000 + 7500); max-allowed leg = 80000 -> min
        self.assertEqual(h, 76_500)


# ---------------------------------------------------------------------------
# State non-conformity is PA-only (SPE line 139: only `resState == 'PA'`).
# ---------------------------------------------------------------------------
class TestNonConformingStates(unittest.TestCase):
    def test_pa_is_non_conforming(self):
        self.assertEqual(ee.NON_CONFORMING_STATES, frozenset({"PA"}))

    def test_other_states_conform(self):
        for st in ("CA", "NY", "IL", "NH", "US", ""):
            r = savings(
                w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
                retirement=dict(max_401k_contribution_allowed=22_500),
                rates=dict(federal_marginal_rate_pct=24,
                           state_marginal_rate_pct=9, resident_state=st),
                filing_status_code=1,
                strategy_change=10_000,
            )
            # non-PA -> state rate preserved -> total 33
            self.assertEqual(
                r["savings"]["marginal_rate_total"], 33.0,
                f"state {st!r} should conform",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
