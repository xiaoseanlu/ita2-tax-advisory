#!/usr/bin/env python3
"""
SPE-fidelity tests for the Backdoor Roth IRA tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  Backdoor Roth IRA/backdoorRothIRA.spe
  SPE includes: tax-strategy-content/IndUS/strategies/common/setup_global.spe
                tax-strategy-content/IndUS/strategies/common/rate_global.spe
  Python tool:  skills/income_tax/assisted/backdoor-roth-ira/tools/backdoor_roth.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: every condition / threshold / clamp from the SPE, plus the
savings math (which for backdoor Roth is deliberately 0 tax savings, cash = the
non-deductible contribution the advisor enters).

Notable SPE facts pinned here:
  * Applicable is `earnedIncome > 0` ONLY — NO married gate, NO MAGI phase-out.
    magiLimit is attached to each person (lines 27, 33) but is never referenced
    in any applicability/recommend condition, so there is no phase-out gating.
  * Spouse recommend additionally requires marriedStatus (lines 42) while
    applicable stays unconditionally true for the spouse group (line 44) — this
    is the "Backdoor spouse FS1 -> applicable True, recommended False" gate.
  * strategyChange default is 0 (line 72), PROJECTED_TAX_SAVINGS is 0 (line 89),
    CASH_OUTLAY = strategyChange - 0 (line 90) plus totalCashOutlayAdjustments
    (line 111).

Run:  python3 -m unittest test_backdoor_roth_ira -v
  or:  python3 test_backdoor_roth_ira.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

bd = load_tool(
    "skills/income_tax/assisted/backdoor-roth-ira/tools/backdoor_roth.py",
    "backdoor_roth",
)


def assess(**payload):
    return bd.assess_from_dict(payload)


def savings(**payload):
    return bd.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Applicable gate — backdoorRothIRA.spe line 39 + 43-44
#   applicableIRA        = applicability planConcat {iraLoop.earnedIncome > 0}
#   applicableTaxpayer   = applicability applicableGroups.isSpouse.false {true}
#   applicableSpouse     = applicability applicableGroups.isSpouse.true  {true}
# i.e. applicability is earnedIncome > 0 ONLY. No married / MAGI gate.
# ---------------------------------------------------------------------------
class TestApplicableGate(unittest.TestCase):
    def test_positive_earned_income_applicable(self):
        # earnedIncome 200000 > 0 -> applicable (spe line 39)
        r = assess(person=dict(earned_income=200_000), filing_status_code=1)
        self.assertTrue(r["applicable"])

    def test_zero_earned_income_not_applicable(self):
        # earnedIncome == 0 fails `> 0` (spe line 39) -> not applicable
        r = assess(person=dict(earned_income=0), filing_status_code=1)
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])
        self.assertTrue(
            any("earnedIncome must be > 0" in reason for reason in r["reasons"])
        )

    def test_negative_earned_income_not_applicable(self):
        # `> 0` is strict; negative fails (spe line 39)
        r = assess(person=dict(earned_income=-1), filing_status_code=1)
        self.assertFalse(r["applicable"])

    def test_applicable_ignores_filing_status_for_taxpayer(self):
        # applicableTaxpayer is unconditionally true over the earned-income group
        # (spe line 43) — single filing does NOT block applicable.
        r = assess(
            person=dict(taxpayer_spouse_or_joint="taxpayer", earned_income=150_000),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])

    def test_no_magi_phaseout_gate(self):
        # magiLimit is attached (spe lines 27, 33) but never used in a condition.
        # A very high earner (well above any Roth phase-out) is still applicable.
        r = assess(person=dict(earned_income=1_000_000), filing_status_code=1)
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — backdoorRothIRA.spe lines 41-42
#   recommendTaxpayer = applicability groups.false {txpNonDeductible > 0}
#   recommendSpouse   = applicability groups.true  {marriedStatus && spsND > 0}
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_taxpayer_recommend_requires_nondeductible(self):
        # txpNonDeductible > 0 (spe line 41)
        r = assess(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_taxpayer_zero_nondeductible_not_recommended(self):
        # nonDeductible == 0 fails `> 0` (spe line 41) -> applicable but not rec
        r = assess(
            person=dict(earned_income=200_000, non_deductible_ira=0),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_recommend_requires_applicable(self):
        # recommend is computed over the applicable (earnedIncome>0) group only
        # (spe line 41 operates on applicableGroups). No earned income -> no rec.
        r = assess(
            person=dict(earned_income=0, non_deductible_ira=6_500),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    # --- Spouse gate: the "FS1 -> applicable True, recommended False" case -----
    def test_spouse_single_filing_applicable_but_not_recommended(self):
        # spe line 44: applicableSpouse == true (unconditional over earned group)
        # spe line 42: recommendSpouse needs marriedStatus; FS1 (single) fails it
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=200_000,
                non_deductible_ira=6_500,
            ),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])   # applicable True
        self.assertFalse(r["recommended"])  # recommended False
        self.assertTrue(
            any("married filing" in reason for reason in r["reasons"])
        )

    def test_spouse_married_filing_2_recommended(self):
        # marriedStatus = filingStatus 2 || 5 (spe line 20). FS2 opens the gate.
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=200_000,
                non_deductible_ira=6_500,
            ),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])
        self.assertTrue(r["recommended"])

    def test_spouse_married_filing_5_recommended(self):
        # marriedStatus also true for filingStatus 5 (spe line 20)
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=200_000,
                non_deductible_ira=6_500,
            ),
            filing_status_code=5,
        )
        self.assertTrue(r["recommended"])

    def test_spouse_married_but_zero_nondeductible_not_recommended(self):
        # marriedStatus true but spsNonDeductible == 0 fails `> 0` (spe line 42)
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=200_000,
                non_deductible_ira=0,
            ),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_taxpayer_not_subject_to_married_gate(self):
        # The married gate (spe line 42) applies to the SPOUSE group only; a
        # taxpayer with nonDeductible > 0 is recommended even when single (FS1).
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="taxpayer",
                earned_income=200_000,
                non_deductible_ira=6_500,
            ),
            filing_status_code=1,
        )
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — backdoorRothIRA.spe line 72
#   strategyChange = eval {0}   (editable true, advisor overrides)
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_default_strategy_change_is_zero(self):
        # spe line 72/78-81: default STRATEGY_CHANGE value is 0
        r = assess(person=dict(earned_income=200_000), filing_status_code=1)
        self.assertEqual(r["strategy_change_default"], 0.0)

    def test_savings_uses_zero_when_strategy_change_omitted(self):
        # No advisor override -> strategyChange default 0 -> cash 0
        r = savings(person=dict(earned_income=200_000), filing_status_code=1)
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["strategy_change"], 0.0)
        self.assertEqual(r["savings"]["cash_outlay"], 0.0)


# ---------------------------------------------------------------------------
# Savings math — backdoorRothIRA.spe lines 89-90, 108-109, 111
#   PROJECTED_TAX_SAVINGS = 0
#   CASH_OUTLAY = strategyChange - PROJECTED_TAX_SAVINGS  (= strategyChange)
#   added scope: CASH_OUTLAY += totalCashOutlayAdjustments
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_smoke_anchor_6500_single(self):
        # Repo smoke anchor (scripts/test_retirement_spe_tools.py lines 190-198):
        #   earned 200000, non_deductible 6500, FS1, strategy_change 6500
        #   -> projected_tax_savings 0, cash_outlay 6500
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=6_500,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["projected_tax_savings"], 0)  # spe line 89
        self.assertEqual(r["savings"]["cash_outlay"], 6_500)        # spe line 90

    def test_tax_savings_always_zero(self):
        # spe line 89: PROJECTED_TAX_SAVINGS = eval {0}, independent of amount
        r = savings(
            person=dict(earned_income=500_000, non_deductible_ira=7_000),
            filing_status_code=2,
            strategy_change=7_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 0)

    def test_cash_outlay_equals_strategy_change(self):
        # spe line 90: CASH_OUTLAY = strategyChange - 0
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=7_000),
            filing_status_code=1,
            strategy_change=7_000,
        )
        self.assertEqual(r["savings"]["cash_outlay"], 7_000)

    def test_cash_outlay_adjustment_added(self):
        # spe line 110-111 (added scope): CASH_OUTLAY += totalCashOutlayAdjustments
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=6_500,
            total_cash_outlay_adjustments=1_000,
        )
        self.assertEqual(r["savings"]["cash_outlay"], 7_500)  # 6500 + 1000

    def test_projected_amount_equals_strategy_change_plus_baseline(self):
        # spe line 85/107: PROJECTED_AMOUNT = strategyChange + BASELINE_AMOUNT.
        # Tool models baseline as 0 -> projected == strategy_change.
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=6_500,
        )
        self.assertEqual(r["baseline_amount"], 0.0)         # spe line 82
        self.assertEqual(r["projected_amount"], 6_500)      # strategyChange + 0

    def test_owner_label_carried_through(self):
        # recommendation scope splits TP/SP; tool surfaces the person owner.
        r = savings(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=200_000,
                non_deductible_ira=6_500,
            ),
            filing_status_code=2,
            strategy_change=6_500,
        )
        self.assertEqual(r["savings"]["taxpayer_spouse_or_joint"], "spouse")


# ---------------------------------------------------------------------------
# Not-applicable path — savings errors out when earnedIncome gate fails.
# (spe: recommendation/savings only emitted for the applicable set, line 39.)
# ---------------------------------------------------------------------------
class TestNotApplicableSavings(unittest.TestCase):
    def test_zero_earned_income_savings_not_ok(self):
        r = savings(
            person=dict(earned_income=0, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=6_500,
        )
        self.assertFalse(r["ok"])
        self.assertIsNone(r["savings"])
        self.assertTrue(r["errors"])

    def test_not_applicable_still_reports_zero_savings_shape(self):
        # Even on the error path the SPE savings numbers are 0-tax / cash=change.
        r = savings(
            person=dict(earned_income=0, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=6_500,
        )
        self.assertEqual(r["cash_outlay"], 6_500)   # strategyChange passthrough
        self.assertEqual(r["baseline_amount"], 0.0)


# ---------------------------------------------------------------------------
# Validation range — backdoorRothIRA.spe lines 125-126
#   assert silent STRATEGY_CHANGE in_range 0.0 .. MAX_VALUE
#   assert silent BASELINE_AMOUNT in_range 0.0 .. MAX_VALUE
# The asserts are `silent` and the test_suite (lines 262-264) shows even
# 99,999,991 passes with 0 errors -> large positive values are NOT rejected.
# ---------------------------------------------------------------------------
class TestValidationRange(unittest.TestCase):
    def test_large_positive_strategy_change_accepted(self):
        # spe test_suite line 262-264: 99999991 -> speErrors size == 0
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=99_999_991,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["cash_outlay"], 99_999_991)

    def test_zero_strategy_change_accepted(self):
        # spe test_suite line 258-260: 0 -> speErrors size == 0
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=0,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["cash_outlay"], 0.0)


# ---------------------------------------------------------------------------
# Mutations — the backdoor SPE writes strategyChange into nonDeductibleIRA but
# tracks no absorption/limit counters; the tool emits no mutation records.
# (spe recommendation scope lines 92-93 set modelPathId only.)
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_no_mutations_emitted(self):
        r = savings(
            person=dict(earned_income=200_000, non_deductible_ira=6_500),
            filing_status_code=1,
            strategy_change=6_500,
        )
        self.assertEqual(r["mutations"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
