#!/usr/bin/env python3
"""
SPE-fidelity tests for the SEP-IRA Contribution tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/SEP-IRA/SEP-IRA.spe
  SPE includes: strategies/common/setup_global.spe
                strategies/common/rate_global.spe
                strategies/common/rate_calculations.spe
  Python tool:  skills/income_tax/assisted/sep-ira/tools/sep_ira.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: every condition / threshold / clamp from the SPE, plus the
savings + state-conformity math.

NOTE on max_sep_ira as an input (SPE lines 16-17, 69-83):
  The SPE computes the per-person SEP cap as
      totalMaxSepAllowed = round(0.25 * scorpWages) + taxPayerMaxAllowedContribution
  where `taxPayerMaxAllowedContribution` (node maxSepIRA) is the SE-income-based
  ceiling the ITA engine has ALREADY computed upstream. The recommendation and
  validation scopes then consume that resolved `activity.maxSepIRA` directly
  (SPE lines 133, 138, 256). The Python tool likewise receives the resolved
  `max_sep_ira` as an input and does NOT recompute the SE-income basis or the
  25%-of-S-Corp-wages component. Tests therefore exercise max_sep_ira as a given.

Run:  python3 -m unittest test_sep_ira -v
  or:  python3 test_sep_ira.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

sep = load_tool(
    "skills/income_tax/assisted/sep-ira/tools/sep_ira.py", "sep_ira"
)


def assess(**payload):
    return sep.assess_from_dict(payload)


def savings(**payload):
    return sep.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Applicability gate — SEP-IRA.spe line 100 (applicableSEPIRA) and
#   applicableTaxpayerSEP line 105:  (allSEincome > 0) || (wagesPaidBysCorp > 0)
# ---------------------------------------------------------------------------
class TestApplicabilityGate(unittest.TestCase):
    def test_se_income_makes_applicable(self):
        # SPE line 105: allSEincome > 0 -> applicable (taxpayer)
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=11_182))
        self.assertTrue(r["applicable"])

    def test_scorp_wages_make_applicable(self):
        # SPE line 100/105: wagesPaidBysCorp > 0 -> applicable even w/o SE income
        r = assess(person=dict(all_se_income=0, wages_paid_by_scorp=1))
        self.assertTrue(r["applicable"])

    def test_no_se_no_scorp_not_applicable(self):
        # SPE line 100: neither leg true -> not applicable
        r = assess(person=dict(all_se_income=0, wages_paid_by_scorp=0))
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_zero_se_income_not_applicable(self):
        # SPE line 100 uses strict > 0, so exactly 0 SE income fails
        r = assess(person=dict(all_se_income=0, max_sep_ira=11_182))
        self.assertFalse(r["applicable"])


# ---------------------------------------------------------------------------
# Spouse applicability — SEP-IRA.spe line 106 (applicableSpouseSEP):
#   (marriedMAGI) && (allSEincome > 0) || (wagesPaidBysCorp > 0)
#   && binds tighter than ||, so: (married && SE>0) || wagesPaidBysCorp>0
#   marriedMAGI (line 9) = filingStatus in {2, 5}
# ---------------------------------------------------------------------------
class TestSpouseApplicability(unittest.TestCase):
    def test_spouse_se_income_needs_married(self):
        # single filer + spouse SE income -> NOT applicable (marriedMAGI false)
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse", all_se_income=50_000),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])

    def test_spouse_se_income_married_applicable(self):
        # MFJ (2) + spouse SE income -> applicable
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse", all_se_income=50_000,
                        max_sep_ira=11_182),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])

    def test_filing_status_5_is_married(self):
        # SPE line 9: marriedMAGI includes filingStatus 5
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse", all_se_income=50_000,
                        max_sep_ira=11_182),
            filing_status_code=5,
        )
        self.assertTrue(r["applicable"])

    def test_spouse_scorp_wages_applicable_even_unmarried(self):
        # SPE line 106 second leg: wagesPaidBysCorp > 0 is OR'd OUTSIDE married
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse", all_se_income=0,
                        wages_paid_by_scorp=2),
            filing_status_code=1,
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# strategy_change default — SEP-IRA.spe line 101/138:
#   strategyChange = maxSepIRA - sepIRA
#   (Python clamps at 0; SPE global is unclamped but validation line 266-268
#    asserts in_range 0..validationMax, so the effective UI floor is 0.)
# ---------------------------------------------------------------------------
class TestStrategyChangeDefault(unittest.TestCase):
    def test_headroom_is_max_minus_contribution(self):
        # SPE line 138: 11182 - 500 = 10682 (the smoke anchor)
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=11_182,
                               sep_ira_contribution=500))
        self.assertEqual(r["strategy_change_default"], 10_682)

    def test_second_anchor_taxpayer(self):
        # SPE test_suite line 378: 11293 - 1000 = 10293
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=11_293,
                               sep_ira_contribution=1_000))
        self.assertEqual(r["strategy_change_default"], 10_293)

    def test_contribution_over_max_clamps_to_zero(self):
        # already contributed past the cap -> floor 0 (validation in_range 0..)
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=5_000,
                               sep_ira_contribution=8_000))
        self.assertEqual(r["strategy_change_default"], 0.0)


# ---------------------------------------------------------------------------
# Recommend gate — SEP-IRA.spe line 103 (applicableTaxpayer):
#   ((strategyChange > 0) && ((solo401K == 0) || (solo401K > 0 && sepIRA > 0)))
#   || (wagesPaidBysCorp > 0)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_positive_headroom_no_solo_recommends(self):
        # solo401K == 0 branch, strategyChange > 0 -> recommend
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=11_182,
                               sep_ira_contribution=500, solo401k=0))
        self.assertTrue(r["recommended"])

    def test_zero_headroom_blocks_recommend(self):
        # strategyChange <= 0 and no S-Corp wages -> no recommend
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=500,
                               sep_ira_contribution=500, solo401k=0))
        self.assertFalse(r["recommended"])

    def test_solo401k_present_without_sep_blocks_recommend(self):
        # SPE line 103: solo401K > 0 requires sepIRA > 0 -> here sepIRA==0 blocks
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=11_182,
                               sep_ira_contribution=0, solo401k=5_000))
        self.assertFalse(r["recommended"])

    def test_solo401k_present_with_sep_recommends(self):
        # SPE line 103: solo401K > 0 && sepIRA > 0 -> gate opens
        r = assess(person=dict(all_se_income=50_000, max_sep_ira=11_182,
                               sep_ira_contribution=500, solo401k=5_000))
        self.assertTrue(r["recommended"])

    def test_scorp_wages_recommend_despite_zero_headroom(self):
        # SPE line 103 second leg: wagesPaidBysCorp > 0 -> recommend regardless
        r = assess(person=dict(all_se_income=0, max_sep_ira=0,
                               sep_ira_contribution=0, wages_paid_by_scorp=1))
        self.assertTrue(r["recommended"])

    def test_spouse_recommend_requires_married_when_no_scorp(self):
        # SPE line 104: applicableSpouse gated by marriedMAGI (unless S-Corp wages)
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse", all_se_income=50_000,
                        max_sep_ira=11_182, sep_ira_contribution=500),
            filing_status_code=1,
        )
        self.assertFalse(r["recommended"])


# ---------------------------------------------------------------------------
# Savings math — SEP-IRA.spe lines 175-178:
#   taxSavings = round(MARGINAL_RATE_TOTAL * strategyChange / 100)
#   cashOutlay = strategyChange - taxSavings
# SPE test_suite anchor (lines 420,440,444): 10682 @ 12% -> 1282 / 9400
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def test_spe_anchor_10682_at_12pct(self):
        # Smoke anchor + SPE test_suite lines 420/440/444
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=500,
                        max_sep_ira=11_182, solo401k=0),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["strategy_change"], 10_682)
        self.assertEqual(r["savings"]["projected_tax_savings"], 1_282)
        self.assertEqual(r["savings"]["cash_outlay"], 9_400)

    def test_second_anchor_taxpayer_10293_at_12pct(self):
        # SPE test_suite line 378/389: 10293 @ 12% -> round(1235.16)=1235
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=1_000,
                        max_sep_ira=11_293, solo401k=0),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 1_235)

    def test_total_rate_sums_fed_state_nyc(self):
        # rate_calculations: MARGINAL_RATE_TOTAL = fed + state + nyc
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=0,
                        max_sep_ira=10_000),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=8, nyc_marginal_rate_pct=4),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["marginal_rate_total"], 36.0)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=0,
                        max_sep_ira=10_000),
            rates=dict(federal_marginal_rate_pct=12.345),
            filing_status_code=1,
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], 123)

    def test_cash_outlay_adjustment_added(self):
        # SPE added scope lines 224-225: cashOutlay += totalCashOutlayAdjustments
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=500,
                        max_sep_ira=11_182),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
            total_cash_outlay_adjustments=1_000,
        )
        # base cash 9400 + 1000
        self.assertEqual(r["savings"]["cash_outlay"], 10_400)

    def test_default_strategy_change_used_when_omitted(self):
        # No strategy_change -> SPE default maxSepIRA - sepIRA = 10682
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=500,
                        max_sep_ira=11_182),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
        )
        self.assertEqual(r["savings"]["strategy_change"], 10_682)


# ---------------------------------------------------------------------------
# projected/baseline amounts — SEP-IRA.spe lines 149, 155:
#   BASELINE_AMOUNT = sepiraContributionMade
#   PROJECTED_AMOUNT = strategyChange + BASELINE_AMOUNT  (= maxSepIRA when default)
# SPE test_suite line 424: PROJECTED_AMOUNT == 11182
# ---------------------------------------------------------------------------
class TestProjectedBaseline(unittest.TestCase):
    def test_projected_equals_max_at_default(self):
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=500,
                        max_sep_ira=11_182),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
        )
        # 10682 + 500 = 11182
        self.assertEqual(r["savings"]["projected_amount"], 11_182)
        self.assertEqual(r["savings"]["baseline_amount"], 500)


# ---------------------------------------------------------------------------
# State conformity — SEP-IRA.spe lines 168-171 / 214-217:
#   nonConformingState if resState in {MA, NJ, PA} -> PARTIAL_STATE_FACTOR 0,
#   so state (and NYC) rate is zeroed for savings.
# SPE State-conformity test_suite (lines 521-569): PA/NJ/MA -> total drops to fed.
# ---------------------------------------------------------------------------
class TestStateConformity(unittest.TestCase):
    def test_pa_is_nonconforming(self):
        # SPE line 168: PA -> fed only
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=0,
                        max_sep_ira=10_000),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=9, resident_state="PA"),
            filing_status_code=1,
            strategy_change=10_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_state"], 0.0)
        self.assertEqual(r["savings"]["marginal_rate_total"], 24.0)
        # 10000 * 24% = 2400
        self.assertEqual(r["savings"]["projected_tax_savings"], 2_400)

    def test_nj_and_ma_nonconforming(self):
        # SPE line 168: NJ and MA also nonconforming
        for st in ("NJ", "MA"):
            r = savings(
                person=dict(all_se_income=50_000, sep_ira_contribution=0,
                            max_sep_ira=10_000),
                rates=dict(federal_marginal_rate_pct=24,
                           state_marginal_rate_pct=9, resident_state=st),
                filing_status_code=1,
                strategy_change=10_000,
            )
            self.assertEqual(r["savings"]["marginal_rate_total"], 24.0,
                             f"{st} should be nonconforming")

    def test_conforming_state_keeps_state_rate(self):
        # SPE State-conformity test (line 497-503): CA conforms, state rate kept
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=0,
                        max_sep_ira=10_000),
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=9, resident_state="CA"),
            filing_status_code=1,
            strategy_change=10_000,
        )
        self.assertEqual(r["savings"]["marginal_rate_state"], 9.0)
        self.assertEqual(r["savings"]["marginal_rate_total"], 33.0)


# ---------------------------------------------------------------------------
# Not-applicable produces an error and no savings block — Python estimate_savings
#   guards on appl.applicable (mirrors SPE applicability gate line 100).
# ---------------------------------------------------------------------------
class TestNotApplicableSavings(unittest.TestCase):
    def test_not_applicable_returns_error(self):
        r = savings(
            person=dict(all_se_income=0, wages_paid_by_scorp=0, max_sep_ira=0),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
        )
        self.assertFalse(r["ok"])
        self.assertTrue(any("not applicable" in e.lower() for e in r["errors"]))
        self.assertIsNone(r["savings"])


# ---------------------------------------------------------------------------
# Mutations — SEP-IRA.spe added scope lines 199-204:
#   projection SEP contribution += strategyChange.
#   The static Python tool emits no live-engine mutations (documented in
#   warnings); confirm the contract stays [].
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_no_live_mutations_emitted(self):
        r = savings(
            person=dict(all_se_income=50_000, sep_ira_contribution=500,
                        max_sep_ira=11_182),
            rates=dict(federal_marginal_rate_pct=12),
            filing_status_code=1,
        )
        self.assertEqual(r["mutations"], [])
        self.assertTrue(any("Static SPE-faithful" in w for w in r["warnings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
