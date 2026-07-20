#!/usr/bin/env python3
"""
SPE-fidelity tests for the Roth IRA Conversion tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  Roth IRA Conversion/Roth_IRA_Conversion.spe
  SPE common:   tax-strategy-content/IndUS/strategies/common/
                  update_parameters.spe   (PROJECTED_TAX_SAVINGS / CASH_OUTLAY)
                  rate_calculations.spe    (MARGINAL_RATE_TOTAL, PA non-conform)
  Python tool:  skills/income_tax/assisted/roth-ira-conversion/tools/
                  roth_conversion.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: the applicability/recommend gates plus BOTH estimate modes
(tax_cost / growth), the negative-savings sign convention, the future-value
formula, the pension-input mutation fields, and the clamps.

Roth conversion is unusual: converting a pre-tax IRA to Roth generates a tax COST
now (negative savings) in exchange for future tax-free growth. Hence two modes:
  - tax_cost  (ConvertedAmount secondary): savings is NEGATIVE.
  - growth    (GrowthSavings secondary):   models future value; cash outlay = 0.

Run:  python3 -m unittest test_roth_ira_conversion -v
  or:  python3 test_roth_ira_conversion.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

rc = load_tool(
    "skills/income_tax/assisted/roth-ira-conversion/tools/roth_conversion.py",
    "roth_conversion",
)


def assess(**payload):
    return rc.assess_from_dict(payload)


def savings(**payload):
    return rc.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Applicability gate — Roth_IRA_Conversion.spe lines 17-18
#   applicableTaxpayer = applicability(...isSpouse.false) { true }
#   applicableSpouse   = applicability(...isSpouse.true)  { filingStatus == 2 }
# ---------------------------------------------------------------------------
class TestApplicabilityGate(unittest.TestCase):
    def test_taxpayer_always_applicable(self):
        # SPE line 17: taxpayer gate is unconditionally {true}
        r = assess(person=dict(taxpayer_spouse_or_joint="taxpayer"))
        self.assertTrue(r["applicable"])

    def test_spouse_requires_filing_status_2(self):
        # SPE line 18: spouse applicable only when filingStatus == 2
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse"),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])

    def test_spouse_applicable_when_married(self):
        # SPE line 18: filingStatus == 2 opens the spouse gate
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse"),
            filing_status_code=2,
        )
        self.assertTrue(r["applicable"])

    def test_unknown_owner_not_applicable(self):
        # SPE only groups isSpouse false/true; anything else has no bucket.
        r = assess(person=dict(taxpayer_spouse_or_joint="dog"))
        self.assertFalse(r["applicable"])


# ---------------------------------------------------------------------------
# Recommend gate — Roth_IRA_Conversion.spe lines 20-21
#   recommendedFor{TaxPayer,Spouse} = applicability(...) {
#       iraContribution>0 || total401k>0 || total457b>0 || total403b>0 }
#   (recommend also requires the person be in the applicable set)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def test_ira_contribution_recommends(self):
        # SPE line 20: iraContribution > 0
        r = assess(person=dict(taxpayer_spouse_or_joint="taxpayer",
                               ira_contribution=50_000))
        self.assertTrue(r["recommended"])

    def test_401k_contribution_recommends(self):
        # SPE line 20: total401kContribution > 0
        r = assess(person=dict(taxpayer_spouse_or_joint="taxpayer",
                               total_401k_contribution=1))
        self.assertTrue(r["recommended"])

    def test_403b_contribution_recommends(self):
        # SPE line 20: total403bContribution > 0
        r = assess(person=dict(taxpayer_spouse_or_joint="taxpayer",
                               total_403b_contribution=1))
        self.assertTrue(r["recommended"])

    def test_457b_contribution_recommends(self):
        # SPE line 20: total457bContribution > 0
        r = assess(person=dict(taxpayer_spouse_or_joint="taxpayer",
                               total_457b_contribution=1))
        self.assertTrue(r["recommended"])

    def test_no_assets_blocks_recommend(self):
        # SPE line 20: all four buckets == 0 -> not recommended (still applicable)
        r = assess(person=dict(taxpayer_spouse_or_joint="taxpayer"))
        self.assertTrue(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_recommend_requires_applicable(self):
        # SPE lines 20-21 filter the *applicable* set; a non-applicable spouse
        # (single filing) can never be recommended even with assets.
        r = assess(
            person=dict(taxpayer_spouse_or_joint="spouse", ira_contribution=50_000),
            filing_status_code=1,
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])


# ---------------------------------------------------------------------------
# tax_cost mode — negative savings sign convention.
#   PROJECTED_TAX_SAVINGS = decimalfmt{ MARGINAL_RATE_TOTAL/100 * strategyChange }
#       common/update_parameters.spe line 17
#   PROJECTED_TAX_SAVINGS = decimalfmt{ PROJECTED_TAX_SAVINGS * -1 } '#'
#       Roth_IRA_Conversion.spe line 222   -> NEGATIVE
#   CASH_OUTLAY = PROJECTED_TAX_SAVINGS   Roth_IRA_Conversion.spe line 202
# Smoke anchor: ira 50000, fed 37, strategy_change 2000 -> savings -740, cash -740
# ---------------------------------------------------------------------------
class TestTaxCostMode(unittest.TestCase):
    def test_smoke_anchor_negative_savings(self):
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer",
                        ira_contribution=50_000),
            filing_status_code=1,
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
            strategy_change=2_000,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        # -round(2000 * 37 / 100) = -740
        self.assertEqual(r["savings"]["projected_tax_savings"], -740)
        # CASH_OUTLAY == PROJECTED_TAX_SAVINGS (line 202) -> -740
        self.assertEqual(r["savings"]["cash_outlay"], -740)

    def test_total_rate_sums_fed_state_nyc(self):
        # rate_calculations.spe: total = fed + state + NYC
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=24,
                       state_marginal_rate_pct=8, nyc_marginal_rate_pct=4),
            strategy_change=10_000,
        )
        # -round(10000 * 36 / 100) = -3600
        self.assertEqual(r["savings"]["projected_tax_savings"], -3_600)

    def test_rounding_is_half_up_whole_dollars(self):
        # decimalfmt '#': 1000 * 12.345% = 123.45 -> 123 (then negated)
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=12.345),
            strategy_change=1_000,
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], -123)

    def test_cash_outlay_adjustment_added(self):
        # Roth_IRA_Conversion.spe line 204: CASH_OUTLAY += totalCashOutlayAdjustments
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
            strategy_change=2_000,
            total_cash_outlay_adjustments=100,
        )
        # base cash -740 + 100
        self.assertEqual(r["savings"]["cash_outlay"], -640)

    def test_default_strategy_change_zero(self):
        # SPE primary line 45 STRATEGY_CHANGE default 0 -> savings 0 when omitted
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
        )
        self.assertEqual(r["strategy_change"], 0.0)
        self.assertEqual(r["savings"]["projected_tax_savings"], 0)


# ---------------------------------------------------------------------------
# tax_cost state conformity — Roth_IRA_Conversion.spe lines 214-217
#   PA -> nonConformingState -> PARTIAL_STATE_FACTOR 0 ; rate_calculations zeros
#   state & NYC (fed only).
# ---------------------------------------------------------------------------
class TestPANonConforming(unittest.TestCase):
    def test_pa_zeros_state_and_nyc(self):
        # SPE line 214: resState == 'PA' -> state/NYC excluded -> fed only
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37,
                       state_marginal_rate_pct=12, nyc_marginal_rate_pct=4,
                       resident_state="PA"),
            strategy_change=2_000,
        )
        # PA: only fed 37% applies -> -round(2000 * 37 / 100) = -740
        self.assertEqual(r["savings"]["projected_tax_savings"], -740)

    def test_non_pa_state_conforms(self):
        # Non-PA -> state/NYC preserved.
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37,
                       state_marginal_rate_pct=12, resident_state="CA"),
            strategy_change=2_000,
        )
        # fed+state = 49% -> -round(2000 * 49 / 100) = -980
        self.assertEqual(r["savings"]["projected_tax_savings"], -980)


# ---------------------------------------------------------------------------
# tax_cost NJ partial conformity — Roth_IRA_Conversion.spe lines 228-237
#   fedTaxSaving      = round(RATE_FED * STRATEGY_CHANGE / 100)
#   stateTaxableAmount= round(STRATEGY_CHANGE * NJPensionExclusionPercentage)
#   stateTaxSaving    = round(RATE_STATE * stateTaxableAmount / 100)
#   PROJECTED         = (fedTaxSaving + stateTaxSaving) * -1
# ---------------------------------------------------------------------------
class TestNJPartialConformity(unittest.TestCase):
    def test_nj_pension_exclusion_factor_applied(self):
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37, state_marginal_rate_pct=10,
                       resident_state="NJ", nj_pension_exclusion_factor=0.5),
            strategy_change=10_000,
        )
        # fed  = round(37 * 10000 / 100) = 3700
        # stAmt= round(10000 * 0.5) = 5000
        # state= round(10 * 5000 / 100) = 500
        # projected = -(3700 + 500) = -4200
        self.assertEqual(r["savings"]["projected_tax_savings"], -4_200)


# ---------------------------------------------------------------------------
# growth mode — GrowthSavings future-value formula.
#   FV = amount * pow(1 + rate/100, Years)   additional_info line 445
#   Years = RetirementAge - CurrentAge       additional_info line 444
#   PROJECTED_TAX_SAVINGS = round( MARGINAL_RATE_TOTAL/100 * STRATEGY_CHANGE )
#       where STRATEGY_CHANGE = FV, MARGINAL_RATE_TOTAL = retirement rate
#       Roth_IRA_Conversion.spe line 319/340
#   CASH_OUTLAY = 0   Roth_IRA_Conversion.spe line 320
# Smoke anchor: amount 10000, r 7%, years 20, retirement 25% ->
#   round(10000 * 1.07^20 * 0.25) = 9674, cash 0
# ---------------------------------------------------------------------------
class TestGrowthMode(unittest.TestCase):
    def test_smoke_anchor_future_value(self):
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="growth",
            growth=dict(amount=10_000, growth_rate_pct=7, years=20,
                        retirement_rate_pct=25),
        )
        self.assertTrue(r["ok"], r.get("errors"))
        expected = round(10_000 * (1.07 ** 20) * 0.25)
        self.assertEqual(r["savings"]["projected_tax_savings"], expected)
        self.assertEqual(expected, 9_674)

    def test_growth_cash_outlay_zero(self):
        # SPE line 320: CASH_OUTLAY = 0 in growth mode
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="growth",
            growth=dict(amount=10_000, growth_rate_pct=7, years=20,
                        retirement_rate_pct=25),
        )
        self.assertEqual(r["savings"]["cash_outlay"], 0.0)

    def test_future_value_is_strategy_change(self):
        # FV becomes STRATEGY_CHANGE (output_3 maps ReturnFromRothIRA->STRATEGY_CHANGE)
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="growth",
            growth=dict(amount=10_000, growth_rate_pct=7, years=20,
                        retirement_rate_pct=25),
        )
        fv = 10_000 * (1.07 ** 20)
        self.assertAlmostEqual(r["savings"]["strategy_change"], fv, places=4)
        self.assertAlmostEqual(r["savings"]["future_value"], fv, places=4)

    def test_zero_years_is_amount_itself(self):
        # Years 0 -> pow(...,0) = 1 -> FV == amount
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="growth",
            growth=dict(amount=5_000, growth_rate_pct=7, years=0,
                        retirement_rate_pct=25),
        )
        self.assertEqual(r["savings"]["projected_tax_savings"], round(5_000 * 0.25))


# ---------------------------------------------------------------------------
# Mutation fields — ConvertedAmount added scope, Roth_IRA_Conversion.spe 250-257
#   new usPensInp[prefix == max+1] with:
#     general.pensionTpSp   = taxPayerSpouseFlag (T->0, S->1)   line 253
#     general.nameOfPensPayer = 'New pension payer <prefix>'    line 254
#     other.deleteNextYear  = 0                                 line 255
#     general.distCode1     = 2                                 line 256
#     taxable.pensTxblAmt   = strategyChange                    line 257
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_tax_cost_creates_pension_input(self):
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
            strategy_change=2_000,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["mutations"]), 1)
        mut = r["mutations"][0]
        f = mut["fields"]
        # taxable.pensTxblAmt = strategyChange (SPE line 257)
        self.assertEqual(f["taxable.pensTxblAmt"], 2_000)
        # general.distCode1 = 2 (SPE line 256)
        self.assertEqual(f["general.distCode1"], 2)
        # other.deleteNextYear = 0 (SPE line 255)
        self.assertEqual(f["other.deleteNextYear"], 0)
        # taxpayer -> pensionTpSp 0 (SPE lines 170, 253)
        self.assertEqual(f["general.pensionTpSp"], 0)
        # secondary identifier is ConvertedAmount (SPE line 108)
        self.assertEqual(mut["secondary_id"], "ConvertedAmount")
        # target path is the usPensInp collection (SPE line 250)
        self.assertIn(
            "projection.return.income.usIncSum.usRetPlnDistrSum.usPensInp",
            mut["path"],
        )

    def test_spouse_pension_tp_sp_flag_is_1(self):
        # SPE line 170: label 'S' -> 1
        r = savings(
            person=dict(taxpayer_spouse_or_joint="spouse", ira_contribution=1),
            filing_status_code=2,
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
            strategy_change=2_000,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["mutations"][0]["fields"]["general.pensionTpSp"], 1)

    def test_zero_strategy_change_no_mutation(self):
        # No conversion amount -> no new pension distribution row created.
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
        )
        self.assertEqual(r["mutations"], [])

    def test_growth_mode_no_mutation(self):
        # GrowthSavings secondary does not write a usPensInp distribution.
        r = savings(
            person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
            estimate_mode="growth",
            growth=dict(amount=10_000, growth_rate_pct=7, years=20,
                        retirement_rate_pct=25),
        )
        self.assertEqual(r["mutations"], [])


# ---------------------------------------------------------------------------
# Applicability clamp on estimate — a non-applicable person yields ok=False
# (SPE only produces ConvertedAmount/GrowthSavings for the applicable set).
# ---------------------------------------------------------------------------
class TestEstimateGuards(unittest.TestCase):
    def test_non_applicable_spouse_errors(self):
        r = savings(
            person=dict(taxpayer_spouse_or_joint="spouse", ira_contribution=50_000),
            filing_status_code=1,  # single -> spouse not applicable
            estimate_mode="tax_cost",
            rates=dict(federal_marginal_rate_pct=37),
            strategy_change=2_000,
        )
        self.assertFalse(r["ok"])
        self.assertIsNone(r["savings"])
        self.assertEqual(r["mutations"], [])

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            savings(
                person=dict(taxpayer_spouse_or_joint="taxpayer", ira_contribution=1),
                estimate_mode="bogus",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
