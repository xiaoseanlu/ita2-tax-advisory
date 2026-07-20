#!/usr/bin/env python3
"""
SPE-fidelity tests for the Traditional IRA Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  Traditional IRA/contribution-Traditional-IRA.spe
  SPE includes: strategies/common/rate_calculations.spe   (fed + state + NYC total)
                strategies/common/rate_global.spe / setup_global.spe
  Python tool:  skills/income_tax/assisted/traditional-ira/tools/traditional_ira.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: every condition / threshold / clamp from the SPE, plus the
savings + cash-outlay math.

Traditional IRA has its own logic (NOT the shared 401k limit files):
  - applicable gate: earnedIncome > 0 (spouse also requires marriedMAGI)
  - recommend gate: iraContribution < maxIRAAllowed && rothCont == 0
                    && (hasPlan == 0 || (hasPlan == 1 && iRAMagi < iRAPhaseOutBegin))
  - lever:  strategyChange = maxIRAAllowed - iraContribution
  - savings/cash: same round-half-up + nonconforming-state pattern as 401k.

Run:  python3 -m unittest test_traditional_ira -v
  or:  python3 test_traditional_ira.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

tira = load_tool(
    "skills/income_tax/assisted/traditional-ira/tools/traditional_ira.py",
    "traditional_ira",
)


def assess(**payload):
    return tira.assess_from_dict(payload)


def savings(**payload):
    return tira.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Applicability pool — contribution-Traditional-IRA.spe line 38
#   applicableIRA = applicability planConcat {iraLoop.earnedIncome > 0}
# Spouse also gated by marriedMAGI (line 44):
#   applicableSpouseIRA = {(marriedMAGI) && (ira.earnedIncome > 0)}
#   marriedMAGI = filingStatus == 2 || filingStatus == 5   (line 16)
# ---------------------------------------------------------------------------
class TestApplicabilityPool(unittest.TestCase):
    def test_positive_earned_income_taxpayer_applicable(self):
        # earned_income > 0, taxpayer -> applicable
        r = assess(
            person=dict(earned_income=100_000, max_ira_allowed=6_000),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])

    def test_zero_earned_income_not_applicable(self):
        # SPE line 38: earnedIncome must be strictly > 0
        r = assess(
            person=dict(earned_income=0, max_ira_allowed=6_000),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_requires_married_filing(self):
        # SPE line 44: spouse applicable only when marriedMAGI (2 or 5).
        # filing 1 (single) -> spouse not applicable.
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=100_000,
                max_ira_allowed=6_000,
            ),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_spouse_applicable_when_mfj(self):
        # SPE line 16: marriedMAGI includes filingStatus 2
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=100_000,
                max_ira_allowed=6_000,
            ),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])

    def test_spouse_applicable_when_filing_status_5(self):
        # SPE line 16: marriedMAGI also includes filingStatus 5
        r = assess(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=100_000,
                max_ira_allowed=6_000,
            ),
            filing_status_code=5,
        )
        self.assertTrue(r["applicable"])

    def test_taxpayer_unaffected_by_married_status(self):
        # SPE line 43: applicableTaxpayerIRA has no marriedMAGI gate.
        r = assess(
            person=dict(earned_income=50_000, max_ira_allowed=6_000),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — contribution-Traditional-IRA.spe lines 41-42
#   applicableTaxpayer = {
#     (ira.iraContribution < ira.maxIRAContributionAllowed) &&
#     (ira.rothCont == 0) &&
#     ((ira.hasPlan == 0) ||
#      ((ira.hasPlan == 1) && (ira.iRAMagi < ira.iRAPhaseOutBegin)))
#   }
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def base(self, **over):
        p = dict(
            earned_income=100_000,
            ira_contribution=0,
            max_ira_allowed=6_000,
            roth_cont=0,
            has_plan=0,
        )
        p.update(over)
        return p

    def test_all_gates_open_recommends(self):
        r = assess(person=self.base(), filing_status_code=1)
        self.assertTrue(r["recommended"])

    def test_contribution_at_or_above_max_blocks(self):
        # SPE line 41: strictly < max. Equal -> not recommended.
        r = assess(
            person=self.base(ira_contribution=6_000, max_ira_allowed=6_000),
            filing_status_code=1,
        )
        self.assertFalse(r["recommended"])
        self.assertTrue(
            any("ira_contribution >= max_ira_allowed" in x for x in r["reasons"])
        )

    def test_roth_contribution_blocks_recommend(self):
        # SPE line 41: rothCont == 0 required (Roth interaction).
        r = assess(person=self.base(roth_cont=1_000), filing_status_code=1)
        self.assertFalse(r["recommended"])
        self.assertTrue(any("roth_cont != 0" in x for x in r["reasons"]))

    def test_has_plan_with_magi_below_phaseout_ok(self):
        # SPE line 41: hasPlan == 1 allowed when iRAMagi < iRAPhaseOutBegin.
        r = assess(
            person=self.base(has_plan=1, ira_magi=50_000, ira_phase_out_begin=73_000),
            filing_status_code=1,
        )
        self.assertTrue(r["recommended"])

    def test_has_plan_with_magi_at_phaseout_blocks(self):
        # SPE line 41: needs iRAMagi < begin (strict). Equal -> blocked.
        r = assess(
            person=self.base(has_plan=1, ira_magi=73_000, ira_phase_out_begin=73_000),
            filing_status_code=1,
        )
        self.assertFalse(r["recommended"])
        self.assertTrue(
            any("has_plan and ira_magi >= phase_out_begin" in x for x in r["reasons"])
        )

    def test_has_plan_with_magi_above_phaseout_blocks(self):
        r = assess(
            person=self.base(has_plan=1, ira_magi=90_000, ira_phase_out_begin=73_000),
            filing_status_code=1,
        )
        self.assertFalse(r["recommended"])

    def test_no_plan_ignores_magi(self):
        # SPE line 41: hasPlan == 0 short-circuits the MAGI branch entirely.
        r = assess(
            person=self.base(has_plan=0, ira_magi=500_000, ira_phase_out_begin=73_000),
            filing_status_code=1,
        )
        self.assertTrue(r["recommended"])

    def test_not_applicable_blocks_recommend(self):
        # SPE: recommend is computed from the applicable set; earned_income 0
        # -> not applicable -> not recommended.
        r = assess(
            person=self.base(earned_income=0),
            filing_status_code=1,
        )
        self.assertFalse(r["recommended"])


# ---------------------------------------------------------------------------
# STRATEGY_CHANGE default — contribution-Traditional-IRA.spe line 78
#   strategyChange = maxIRAAllowed - iraContributionMade
# The Python default additionally clamps to >= 0 (documented divergence: the
# SPE does not clamp here, but a negative default only arises when the recommend
# gate at line 41 is already false, and the validation scope asserts
# STRATEGY_CHANGE in_range 0..validationMax at line 207).
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_default_is_max_minus_contribution(self):
        # smoke anchor: 6000 - 4000 = 2000
        r = assess(
            person=dict(
                earned_income=100_000, ira_contribution=4_000, max_ira_allowed=6_000
            ),
            filing_status_code=1,
        )
        self.assertEqual(r["strategy_change_default"], 2_000)

    def test_default_full_room_when_no_prior_contribution(self):
        r = assess(
            person=dict(
                earned_income=100_000, ira_contribution=0, max_ira_allowed=6_000
            ),
            filing_status_code=1,
        )
        self.assertEqual(r["strategy_change_default"], 6_000)

    def test_default_clamped_to_zero_when_over_contributed(self):
        # Python clamp: max(6000 - 7000, 0) = 0 (recommend gate already blocks).
        r = assess(
            person=dict(
                earned_income=100_000, ira_contribution=7_000, max_ira_allowed=6_000
            ),
            filing_status_code=1,
        )
        self.assertEqual(r["strategy_change_default"], 0.0)


# ---------------------------------------------------------------------------
# Savings math — contribution-Traditional-IRA.spe lines 118-119
#   PROJECTED_TAX_SAVINGS = decimalfmt {(MARGINAL_RATE_TOTAL * strategyChange)/100} '#'
#   CASH_OUTLAY = strategyChange - PROJECTED_TAX_SAVINGS
# SPE unit-test anchor (test_suite line 383-408):
#   change 2000 @ 37% -> savings 740, cash 1260.
# Smoke anchor (scripts/test_retirement_spe_tools.py line 156):
#   earned 100000, contribution 4000, max 6000, fed 37 -> change 2000, 740, 1260.
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_spe_anchor_2000_at_37pct(self):
        r = savings(
            person=dict(
                earned_income=100_000,
                ira_contribution=4_000,
                max_ira_allowed=6_000,
                roth_cont=0,
                has_plan=0,
            ),
            rates=dict(federal_marginal_rate_pct=37),
            filing_status_code=1,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["strategy_change"], 2_000)
        self.assertEqual(r["savings"]["marginal_rate_total"], 37.0)
        self.assertEqual(r["savings"]["projected_tax_savings"], 740)
        self.assertEqual(r["savings"]["cash_outlay"], 1_260)
        # baseline is the prior contribution; projected = change + baseline
        self.assertEqual(r["savings"]["baseline_amount"], 4_000)
        self.assertEqual(r["savings"]["projected_amount"], 6_000)

    def test_total_rate_sums_fed_state_nyc(self):
        # rate_calculations.spe: MARGINAL_RATE_TOTAL = fed + state + NYC
        r = savings(
            person=dict(
                earned_income=100_000, ira_contribution=0, max_ira_allowed=6_000
            ),
            rates=dict(
                federal_marginal_rate_pct=24,
                state_marginal_rate_pct=8,
                nyc_marginal_rate_pct=4,
            ),
            filing_status_code=1,
            strategy_change=6_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)
        # 6000 * 36% = 2160
        self.assertEqual(r["savings"]["projected_tax_savings"], 2_160)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            person=dict(
                earned_income=100_000, ira_contribution=0, max_ira_allowed=6_000
            ),
            rates=dict(federal_marginal_rate_pct=12.345),
            filing_status_code=1,
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_cash_outlay_adjustment_added(self):
        # SPE added scope lines 164-165: cash outlay += totalCashOutlayAdjustments
        r = savings(
            person=dict(
                earned_income=100_000, ira_contribution=4_000, max_ira_allowed=6_000
            ),
            rates=dict(federal_marginal_rate_pct=37),
            filing_status_code=1,
            total_cash_outlay_adjustments=500,
        )
        # base cash 1260 + 500
        self.assertEqual(r["savings"]["cash_outlay"], 1_760)

    def test_default_strategy_change_used_when_omitted(self):
        # No strategy_change -> SPE default maxIRAAllowed - contribution = 2000
        r = savings(
            person=dict(
                earned_income=100_000, ira_contribution=4_000, max_ira_allowed=6_000
            ),
            rates=dict(federal_marginal_rate_pct=37),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["strategy_change"], 2_000)
        self.assertEqual(r["savings"]["projected_tax_savings"], 740)


# ---------------------------------------------------------------------------
# State non-conformity — contribution-Traditional-IRA.spe lines 109-112, 154-157
#   if resState in (MA, NH, NJ, PA): nonConformingState = true;
#       PARTIAL_STATE_FACTOR = 0  -> state & NYC zeroed in rate_calculations.spe.
# ---------------------------------------------------------------------------
class TestNonConformingStates(unittest.TestCase):
    def test_nonconforming_set_is_ma_nh_nj_pa(self):
        # SPE lines 109 / 154 list exactly these four states.
        self.assertEqual(
            tira.NON_CONFORMING_STATES, {"MA", "NH", "NJ", "PA"}
        )

    def test_pa_zeros_state_and_nyc(self):
        r = savings(
            person=dict(
                earned_income=100_000, ira_contribution=0, max_ira_allowed=6_000
            ),
            rates=dict(
                federal_marginal_rate_pct=24,
                state_marginal_rate_pct=9,
                nyc_marginal_rate_pct=3,
                resident_state="PA",
            ),
            filing_status_code=1,
            strategy_change=6_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)
        self.assertEqual(r["savings"]["marginal_rate_nyc"], 0.0)
        self.assertEqual(r["savings"]["marginal_rate_total"], 24.0)
        # 6000 * 24% = 1440
        self.assertEqual(r["savings"]["projected_tax_savings"], 1_440)

    def test_each_nonconforming_state_zeros_state(self):
        for st in ("MA", "NH", "NJ", "PA"):
            r = savings(
                person=dict(
                    earned_income=100_000, ira_contribution=0, max_ira_allowed=6_000
                ),
                rates=dict(
                    federal_marginal_rate_pct=24,
                    state_marginal_rate_pct=9,
                    resident_state=st,
                ),
                filing_status_code=1,
                strategy_change=6_000,
            )
            self.assertEqual(
                r["savings"]["marginal_rate_total"], 24.0, f"{st} should be nonconforming"
            )

    def test_conforming_state_preserves_rate(self):
        for st in ("CA", "NY", "IL", "US", ""):
            r = savings(
                person=dict(
                    earned_income=100_000, ira_contribution=0, max_ira_allowed=6_000
                ),
                rates=dict(
                    federal_marginal_rate_pct=24,
                    state_marginal_rate_pct=9,
                    resident_state=st,
                ),
                filing_status_code=1,
                strategy_change=6_000,
            )
            self.assertEqual(
                r["savings"]["marginal_rate_total"], 33.0, f"{st!r} should conform"
            )


# ---------------------------------------------------------------------------
# Not-applicable path — the tool returns ok=False with no savings when the
# SPE applicable gate (earnedIncome > 0) is not met.
# ---------------------------------------------------------------------------
class TestNotApplicablePath(unittest.TestCase):
    def test_zero_earned_income_savings_errors(self):
        r = savings(
            person=dict(earned_income=0, max_ira_allowed=6_000),
            rates=dict(federal_marginal_rate_pct=37),
            filing_status_code=1,
        )
        self.assertFalse(r["ok"])
        self.assertIsNone(r["savings"])
        self.assertTrue(any("not applicable" in e for e in r["errors"]))

    def test_spouse_single_filing_savings_errors(self):
        r = savings(
            person=dict(
                taxpayer_spouse_or_joint="spouse",
                earned_income=100_000,
                max_ira_allowed=6_000,
            ),
            rates=dict(federal_marginal_rate_pct=37),
            filing_status_code=1,
        )
        self.assertFalse(r["ok"])


# ---------------------------------------------------------------------------
# Mutations — the SPE writes the projection node in the added scope
# (lines 139-143). The static tool reports no mutations (parity with the other
# retirement tools' static estimate contract).
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_no_mutations_emitted(self):
        r = savings(
            person=dict(
                earned_income=100_000, ira_contribution=4_000, max_ira_allowed=6_000
            ),
            rates=dict(federal_marginal_rate_pct=37),
            filing_status_code=1,
        )
        self.assertEqual(r["mutations"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
