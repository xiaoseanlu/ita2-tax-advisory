#!/usr/bin/env python3
"""
SPE-fidelity tests for the 403(b) Employee Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  403b Employee Contribution/employee-403b-contribution.spe
  SPE limits:   tax-strategy-content/IndUS/strategies/common/
                  shared401KLimit_GlobalScope.spe
                  shared401KLimit_GlobalScope_strategyLimit.spe
                  shared401KLimit_GlobalScope_validation.spe
  Python tool:  skills/income_tax/assisted/403b-employee/tools/ee_403b.py

The tool has two jobs — applicability and savings estimate — so the suite covers
BOTH: every condition / threshold / clamp from the SPE, plus savings + validation
math, and the year/age combined-limit table + PA/NJ non-conformity.

The 403(b) EE formula parallels the 401(k) EE formula but keys on the 403(b)
contribution field (wages403bContribution) and its recommend gate REQUIRES that
field to be > 0 (SPE lines 26-27), rather than blocking on 403b/457b like 401k.

Run:  python3 -m unittest test_403b_employee -v
  or:  python3 test_403b_employee.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

ee = load_tool(
    "skills/income_tax/assisted/403b-employee/tools/ee_403b.py", "ee_403b"
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
#   (457b / roth457b are NOT subtracted from the employee limit)
# ---------------------------------------------------------------------------
class TestHeadroomFormula(unittest.TestCase):
    def h(self, **r):
        return ee.compute_employee_headroom(ee.retirement_from_dict(r))

    def test_simple_max_allowed_binds(self):
        # maxAllowed 22500, combined 69000 (default), nothing used -> 22500
        self.assertEqual(self.h(max_401k_contribution_allowed=22_500), 22_500)

    def test_baseline_reduces_headroom(self):
        # 22500 - 5000(401k) = 17500 ; combined 69000 - 5000 = 64000 -> 17500
        self.assertEqual(
            self.h(max_401k_contribution_allowed=22_500, total_401k=5_000), 17_500
        )

    def test_all_baseline_buckets_subtracted(self):
        # 401k+roth401k+403b+roth403b+solo all reduce the pool (GlobalScope l.29-30)
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
        # employee_limit_absorbed reduces 'a' leg; combined absorbed the 'b' leg
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
        # shared401KLimit_GlobalScope_validation.spe l.3-4: same formula WITHOUT
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
# Applicability pool — employee-403b-contribution.spe line 20
#   applicableW2s = w2.general.deleteNextYear == 0 and w2.federal.wgFedwages > 0
# ---------------------------------------------------------------------------
class TestApplicabilityPool(unittest.TestCase):
    def base_w2(self, **over):
        # 403b recommend requires wages403bContribution > 0 (SPE line 26)
        w2 = dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                  wages_403b_contribution=1_000)
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
# Applicable gate — employee-403b-contribution.spe lines 24-25
#   applicableTaxPayer403b: taxPayerMaxAllowedContribution > 0  (headroom > 0)
#   applicableSpouse403b:   marriedMAGI && spouseMaxAllowedContribution > 0
#   (Note: unlike 401k, applicable does NOT gate on contribution<=headroom)
# ---------------------------------------------------------------------------
class TestApplicableGate(unittest.TestCase):
    def test_headroom_positive_is_applicable(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["applicable"])

    def test_zero_headroom_not_applicable(self):
        # taxPayerMaxAllowedContribution == 0 -> not applicable (SPE line 24)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000),
            retirement=dict(max_401k_contribution_allowed=0),
        )
        self.assertFalse(r["applicable"])

    def test_spouse_requires_married_filing(self):
        # filing_status 1 (single) -> spouse not applicable (marriedMAGI false)
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_applicable_when_married(self):
        # filing_status 2 (MFJ) -> spouse gate opens (SPE line 25)
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_filing_status_5_also_married(self):
        # SPE marriedMAGI = filingStatus 2 || 5 (line 10)
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            filing_status_code=5,
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — employee-403b-contribution.spe lines 26-27
#   taxPayer403b: wages403bContribution > 0 && taxPayerMaxAllowedContribution > 0
#   spouse403b:   marriedMAGI && wages403bContribution > 0 && spouseMax > 0
#   (403b KEYS ON the 403b field being present, opposite of the 401k blocker)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_zero_403b_contribution_blocks_recommend(self):
        # wages403bContribution == 0 -> no recommend (SPE line 26)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=0),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertFalse(r["recommended"])
        # ...but still applicable (applicable does not require the 403b field)
        self.assertTrue(r["applicable"])

    def test_positive_403b_contribution_recommends(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertTrue(r["recommended"])

    def test_zero_headroom_blocks_recommend(self):
        # taxPayerMaxAllowedContribution must be > 0 (SPE line 26)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=0),
        )
        self.assertFalse(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — employee-403b-contribution.spe line 49
#   strategyChange = min(fedwages, employeeMax403bContribution)
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_headroom_binds_when_below_wages(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["strategy_change_default"], 22_500)

    def test_wages_bind_when_below_headroom(self):
        # low wages cap the deferral (can't defer more than you earn)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=10_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["strategy_change_default"], 10_000)


# ---------------------------------------------------------------------------
# Savings math — employee-403b-contribution.spe lines 71-72 (recommendation),
#                lines 114-117 (added scope).
#   PROJECTED_TAX_SAVINGS = round(MARGINAL_RATE_TOTAL * strategyChange / 100)
#   CASH_OUTLAY = strategyChange - PROJECTED_TAX_SAVINGS [+ adjustments]
# SPE test_suite anchor (lines 245-252): 17000 @ 20% -> 3400 / 13600.
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_spe_anchor_17000_at_20pct(self):
        # SPE 'Recommendations test': fed 12 + state 8 = total 20; sc 17000
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8),
            filing_status_code=1,
            strategy_change=17_000,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["marginal_rate_total"], 20.0)
        self.assertEqual(r["savings"]["projected_tax_savings"], 3_400)
        self.assertEqual(r["savings"]["cash_outlay"], 13_600)

    def test_total_rate_sums_fed_state_nyc(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=300_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=8, nyc_marginal_rate_pct=4),
            filing_status_code=1,
            strategy_change=22_500,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)

    def test_nj_nonconforming_zeros_state_and_nyc(self):
        # SPE added-scope conformity line 107: NJ -> nonConformingState -> fed only
        # (SPE test_suite line 425-440 anchors NJ MARGINAL_RATE_STATE -> [])
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8,
                       resident_state="NJ"),
            filing_status_code=1,
            strategy_change=17_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 12.0)
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)

    def test_pa_nonconforming_zeros_state_and_nyc(self):
        # SPE test_suite line 459-474 anchors PA MARGINAL_RATE_STATE -> []
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8,
                       resident_state="PA"),
            filing_status_code=1,
            strategy_change=17_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 12.0)
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)
        # 17000 * 12% = 2040
        self.assertEqual(r["savings"]["projected_tax_savings"], 2_040)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12.345),
            filing_status_code=1,
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_cash_outlay_adjustment_added(self):
        # added scope line 116-117: cash outlay += totalCashOutlayAdjustments
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8),
            filing_status_code=1,
            strategy_change=17_000,
            total_cash_outlay_adjustments=1_000,
        )
        # base cash 13600 + 1000
        self.assertEqual(r["savings"]["cash_outlay"], 14_600)

    def test_default_strategy_change_used_when_omitted(self):
        # No strategy_change -> SPE default min(wages, headroom) = 22500 (line 49)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["strategy_change"], 22_500)
        # 22500 * 20% = 4500
        self.assertEqual(r["savings"]["projected_tax_savings"], 4_500)

    def test_projected_amount_adds_baseline(self):
        # SPE line 64/94: PROJECTED_AMOUNT = strategyChange + BASELINE_AMOUNT
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=5_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
            strategy_change=10_000,
        )
        self.assertEqual(r["savings"]["baseline_amount"], 5_000)
        self.assertEqual(r["savings"]["projected_amount"], 15_000)


# ---------------------------------------------------------------------------
# Validation clamp — employee-403b-contribution.spe lines 139-163
#   validationMax = min(baseWages|projectionWages, Validation*Employee)
#   assert STRATEGY_CHANGE in_range 0 .. validationMax
#   SPE 'Validation tests' anchor (lines 534-555): range 0..27000, -1 & 27001 fail
#   ITA UI copy when over: "Exceeds $X" and totals stay 0.
# ---------------------------------------------------------------------------
class TestValidationClamp(unittest.TestCase):
    def test_over_validation_max_is_exceeds_error(self):
        # headroom/validation both 22500, request 30000 -> Exceeds
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12, state_marginal_rate_pct=8),
            filing_status_code=1,
            strategy_change=30_000,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["validation_exceeded"])
        self.assertTrue(any("Exceeds" in e for e in r["errors"]))
        # capped strategy change = validationMax
        self.assertEqual(r["strategy_change"], 22_500)

    def test_negative_strategy_change_errors(self):
        # SPE validation: in_range 0 .. max ; -1 fails (test line 539-546)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
            strategy_change=-1,
        )
        self.assertFalse(r["ok"])

    def test_validation_max_from_projection_wages(self):
        # SPE lines 152-156: min(projectionWages, ValidationMaxContribution)
        # projection wages 18000 < validation headroom 22500 -> validationMax 18000
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=18_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
        )
        self.assertEqual(r["validation_max"], 18_000)

    def test_zero_validation_max_still_exceeds_when_requested_positive(self):
        # Exceeds fires even when validationMax == 0 (headroom exhausted)
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500,
                            total_401k=22_500),  # validation headroom -> 0
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
            strategy_change=5_000,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(r["validation_exceeded"])
        self.assertEqual(r["validation_max"], 0.0)


# ---------------------------------------------------------------------------
# Mutations — added scope lines 91-96
#   wages403bContribution += strategyChange ; wgFedwages -= strategyChange
#   update401KEmployee / update401KCombined = true -> absorbed += strategyChange
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_projection_writes_and_absorption(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=3, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
            strategy_change=10_000,
        )
        self.assertTrue(r["ok"])
        mut = r["mutations"][0]
        self.assertIn("prefix == 3", mut["path"])
        # SPE line 92-93: 403b field incremented, wages decremented
        self.assertEqual(mut["fields"]["wages403bContribution_delta"], 10_000)
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
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                    wages_403b_contribution=1_000),
            retirement=dict(max_401k_contribution_allowed=22_500),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
            strategy_change=30_000,
        )
        self.assertEqual(r["mutations"], [])


# ---------------------------------------------------------------------------
# Combined limit by tax year + age-50 catch-up.
# SPE: shared401KLimit_GlobalScope.spe lines 39-83 (included at 403b SPE l.13/97).
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
        # Beyond the table -> latest known base (69000). Team extends the table
        # each year; this guards the fallback until they do.
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
# State non-conformity is PA AND NJ (SPE line 107:
#   if {((resState == 'NJ') or (resState == 'PA'))}).
# This is a genuine 403b/401k DIFFERENCE — 401k is PA-only.
# ---------------------------------------------------------------------------
class TestNonConformingStates(unittest.TestCase):
    def test_pa_and_nj_are_non_conforming(self):
        self.assertEqual(ee.NON_CONFORMING_STATES, frozenset({"PA", "NJ"}))

    def test_other_states_conform(self):
        # SPE test_suite lines 391-457 anchor NE/NM/RI as conforming (state kept).
        for st in ("CA", "NY", "IL", "NE", "NM", "RI", "US", ""):
            r = savings(
                w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=100_000,
                        wages_403b_contribution=1_000),
                retirement=dict(max_401k_contribution_allowed=22_500),
                rates=dict(federal_marginal_rate_pct=12,
                           state_marginal_rate_pct=8, resident_state=st),
                filing_status_code=1,
                strategy_change=10_000,
            )
            self.assertEqual(
                r["savings"]["marginal_rate_total"], 20.0,
                f"state {st!r} should conform",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
