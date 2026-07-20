#!/usr/bin/env python3
"""
SPE-fidelity tests for the Mega Backdoor Roth tool.

Every assertion below is traced to a specific line/rule in the SPE source:

  SPE primary:  tax-strategy-content/IndUS/strategies/
                  Mega Backdoor Roth/megaBackdoor.spe
  SPE include:  tax-strategy-content/IndUS/strategies/common/setup_global.spe
                  (marriedMAGI = filingStatus in {2, 5})
  Python tool:  skills/income_tax/assisted/mega-backdoor-roth/tools/mega_backdoor.py

The purpose of the tool is two-fold — applicability and savings estimate — so the
suite covers BOTH: every condition / threshold / clamp from the SPE, plus the
after-tax room formula and the (always-zero) savings + cash-outlay math.

Run:  python3 -m unittest ita-rules/tests/test_mega_backdoor_roth.py -v
  or:  python3 ita-rules/tests/test_mega_backdoor_roth.py
"""
from __future__ import annotations

import unittest

from spe_loader import load_tool

mega = load_tool(
    "skills/income_tax/assisted/mega-backdoor-roth/tools/mega_backdoor.py",
    "mega_backdoor",
)


def assess(**payload):
    return mega.assess_from_dict(payload)


def savings(**payload):
    return mega.savings_from_dict(payload)


# ---------------------------------------------------------------------------
# Applicability pool — megaBackdoor.spe line 22
#   w2sApplicability = w2.general.deleteNextYear == 0 && w2.federal.wgFedwages > 0
# The APPLICABLE set (w2sTaxPayer / w2sSpouse, lines 25-26) is derived from this
# pool ONLY — it carries NO marriedMAGI gate and NO phase-out gate. So applicable
# is purely: active W-2 with wages.
# ---------------------------------------------------------------------------
class TestApplicabilityPool(unittest.TestCase):
    def base_w2(self, **over):
        w2 = dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000)
        w2.update(over)
        return w2

    def test_delete_next_year_excludes_w2(self):
        # line 22: deleteNextYear must be 0
        r = assess(
            w2=self.base_w2(delete_next_year=1),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_zero_wages_excludes_w2(self):
        # line 22: wgFedwages must be > 0
        r = assess(
            w2=self.base_w2(wg_fed_wages=0),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
        )
        self.assertFalse(r["applicable"])
        self.assertFalse(r["recommended"])

    def test_positive_wages_included_is_applicable(self):
        # line 22 satisfied -> applicable true regardless of recommend gates
        r = assess(
            w2=self.base_w2(),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
        )
        self.assertTrue(r["applicable"])


# ---------------------------------------------------------------------------
# Applicable set is NOT married-gated — megaBackdoor.spe line 26
#   w2sSpouse = applicability applicableGroupsForApplicability.isSpouse.true {1==1}
# Unlike RECOMMEND (line 51 marriedMAGI), a spouse W-2 with wages is applicable
# even when filing single. (Prior audit note flagged this spouse-applicable gate.)
# ---------------------------------------------------------------------------
class TestSpouseApplicableNoMarriedGate(unittest.TestCase):
    def test_spouse_applicable_when_single(self):
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=250_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
            filing_status_code=1,  # single
        )
        self.assertTrue(r["applicable"])  # applicable NOT gated on marriage
        self.assertEqual(r["taxpayer_spouse_or_joint"], "spouse")


# ---------------------------------------------------------------------------
# Recommend gate — megaBackdoor.spe lines 30, 35-36, 51-52
#   line 30: recommend pool adds (modifiedAGI > rothPhaseOut)
#   lines 35-36 (taxpayer): 401k >= priorYearTxpMax OR 403b >= OR 457b >=
#   lines 51-52 (spouse):   marriedMAGI && (same maxed-deferral test)
# ---------------------------------------------------------------------------
class TestRecommendGate(unittest.TestCase):
    def rec_w2(self, **over):
        w2 = dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000,
                  wages_401k_contribution=23_000)
        w2.update(over)
        return w2

    def base_ret(self, **over):
        r = dict(max_solo_401k_allowed=69_000,
                 current_year_max_401k_allowed=23_000,
                 prior_year_max_401k=23_000,
                 modified_agi=300_000, roth_phase_out=161_000)
        r.update(over)
        return r

    def test_taxpayer_all_gates_met_recommends(self):
        # phased out + 401k deferral (23000) >= prior max (23000) -> recommend
        r = assess(w2=self.rec_w2(), retirement=self.base_ret(),
                   filing_status_code=1)
        self.assertTrue(r["recommended"])

    def test_not_phased_out_blocks_recommend(self):
        # line 30: modifiedAGI must exceed rothPhaseOut
        r = assess(w2=self.rec_w2(),
                   retirement=self.base_ret(modified_agi=100_000),
                   filing_status_code=1)
        self.assertFalse(r["recommended"])
        self.assertTrue(any("not above roth_phase_out" in x for x in r["reasons"]))

    def test_deferral_below_prior_max_blocks_recommend(self):
        # lines 35-36: deferral must reach priorYearTxpMax
        r = assess(w2=self.rec_w2(wages_401k_contribution=10_000),
                   retirement=self.base_ret(),
                   filing_status_code=1)
        self.assertFalse(r["recommended"])
        self.assertTrue(any("has not reached prior_year_max" in x for x in r["reasons"]))

    def test_403b_deferral_satisfies_maxed(self):
        # line 36: 403b >= prior max also satisfies the maxed test
        r = assess(
            w2=self.rec_w2(wages_401k_contribution=0, wages_403b_contribution=23_000),
            retirement=self.base_ret(),
            filing_status_code=1,
        )
        self.assertTrue(r["recommended"])

    def test_457b_deferral_satisfies_maxed(self):
        # line 36: wg457b >= prior max also satisfies the maxed test
        r = assess(
            w2=self.rec_w2(wages_401k_contribution=0, wg_457b=23_000),
            retirement=self.base_ret(),
            filing_status_code=1,
        )
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# Spouse recommend requires married filing — megaBackdoor.spe line 51
#   applicableSpouse = ... {(marriedMAGI) && (deferral maxed)}
#   setup_global.spe line 5: marriedMAGI = filingStatus in {2, 5}
# ---------------------------------------------------------------------------
class TestSpouseMarriedRecommendGate(unittest.TestCase):
    def spouse_case(self, filing):
        return assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=250_000,
                    wages_401k_contribution=23_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000,
                            prior_year_max_401k=23_000,
                            modified_agi=300_000, roth_phase_out=161_000),
            filing_status_code=filing,
        )

    def test_spouse_single_not_recommended(self):
        # line 51 marriedMAGI false for single (1) -> no spouse recommend
        r = self.spouse_case(1)
        self.assertFalse(r["recommended"])
        self.assertTrue(any("requires married filing" in x for x in r["reasons"]))

    def test_spouse_mfj_recommended(self):
        # filing 2 (MFJ) -> marriedMAGI true -> recommend opens
        r = self.spouse_case(2)
        self.assertTrue(r["recommended"])

    def test_spouse_filing_5_also_married(self):
        # setup_global line 5: marriedMAGI = {2, 5}
        r = self.spouse_case(5)
        self.assertTrue(r["recommended"])


# ---------------------------------------------------------------------------
# Room / limit formula (megaMaxAllowed) — megaBackdoor.spe lines 86-89
#   totalMaxAllowed = maxSolo401kContributionAllowed  (base)
#   employeeMax401kContribution = currentYearMax401kContributionAllowed
#   megaMaxAllowed = totalMaxAllowed - employeeMax401kContribution
#   strategyChange = megaMaxAllowed
# ---------------------------------------------------------------------------
class TestRoomFormula(unittest.TestCase):
    def test_combined_minus_deferral(self):
        # 69000 - 23000 = 46000 (the smoke anchor room)
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000,
                    wages_401k_contribution=23_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
        )
        self.assertEqual(r["mega_max_allowed"], 46_000)
        self.assertEqual(r["strategy_change_default"], 46_000)

    def test_different_limit_and_deferral(self):
        # 66000 - 20500 = 45500
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000),
            retirement=dict(max_solo_401k_allowed=66_000,
                            current_year_max_401k_allowed=20_500),
        )
        self.assertEqual(r["mega_max_allowed"], 45_500)

    def test_room_clamped_at_zero(self):
        # SPE line 87 has no max(...,0); the tool clamps defensively so a deferral
        # ceiling above the combined limit yields 0 room, never negative.
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=70_000),
        )
        self.assertEqual(r["mega_max_allowed"], 0.0)


# ---------------------------------------------------------------------------
# Savings math — megaBackdoor.spe lines 108-109, 129
#   PROJECTED_TAX_SAVINGS = 0 (always, after-tax contribution)
#   CASH_OUTLAY = strategyChange - PROJECTED_TAX_SAVINGS = strategyChange
#   added scope line 129: CASH_OUTLAY += totalCashOutlayAdjustments
# Smoke anchor (scripts/test_retirement_spe_tools.py): single, wages 250000,
#   401k 23000, solo max 69000, current max 23000 -> savings 0, cash 46000,
#   strategy_change 46000.
# ---------------------------------------------------------------------------
class TestSavingsMath(unittest.TestCase):
    def anchor(self, **over):
        payload = dict(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000,
                    wages_401k_contribution=23_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000,
                            prior_year_max_401k=23_000,
                            modified_agi=300_000, roth_phase_out=161_000),
            filing_status_code=1,
        )
        payload.update(over)
        return savings(**payload)

    def test_smoke_anchor(self):
        # line 108: savings 0 ; line 109: cash = strategy_change = 46000
        r = self.anchor()
        self.assertTrue(r["ok"], r.get("errors"))
        self.assertEqual(r["savings"]["projected_tax_savings"], 0.0)
        self.assertEqual(r["savings"]["cash_outlay"], 46_000)
        self.assertEqual(r["savings"]["strategy_change"], 46_000)
        self.assertEqual(r["savings"]["baseline_amount"], 0.0)
        self.assertEqual(r["savings"]["projected_amount"], 46_000)

    def test_savings_always_zero_even_when_explicit_change(self):
        # line 108: PROJECTED_TAX_SAVINGS is a literal 0 irrespective of amounts
        r = self.anchor(strategy_change=30_000)
        self.assertEqual(r["savings"]["projected_tax_savings"], 0.0)
        self.assertEqual(r["savings"]["cash_outlay"], 30_000)

    def test_cash_outlay_adjustment_added(self):
        # added scope line 129: CASH_OUTLAY += totalCashOutlayAdjustments
        r = self.anchor(total_cash_outlay_adjustments=1_000)
        self.assertEqual(r["savings"]["cash_outlay"], 47_000)

    def test_explicit_strategy_change_overrides_default(self):
        r = self.anchor(strategy_change=10_000)
        self.assertEqual(r["savings"]["strategy_change"], 10_000)
        self.assertEqual(r["savings"]["projected_amount"], 10_000)


# ---------------------------------------------------------------------------
# Phase-out fields surfaced — megaBackdoor.spe lines 18-19
#   modifiedAGI and rothPhaseOut are echoed in the applicability result so the
#   recommend gate (line 30) is auditable.
# ---------------------------------------------------------------------------
class TestPhaseOutFields(unittest.TestCase):
    def test_fields_echoed(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000,
                            modified_agi=300_000, roth_phase_out=161_000),
        )
        self.assertEqual(r["modified_agi"], 300_000)
        self.assertEqual(r["roth_phase_out"], 161_000)


# ---------------------------------------------------------------------------
# Not-applicable path — estimate_savings on a pool-excluded W-2 returns ok=False.
#   megaBackdoor.spe: applicability filter (line 22) gates the whole strategy.
# ---------------------------------------------------------------------------
class TestNotApplicablePath(unittest.TestCase):
    def test_zero_wages_not_ok(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=0),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
            filing_status_code=1,
        )
        self.assertFalse(r["ok"])
        self.assertIsNone(r["savings"])
        self.assertTrue(any("not applicable" in e for e in r["errors"]))


# ---------------------------------------------------------------------------
# Mutations — megaBackdoor.spe has no projection field write for savings (the
# after-tax contribution lands on a Roth bucket, not a modeled node). The tool
# exposes an empty mutations list; guard that contract.
# ---------------------------------------------------------------------------
class TestMutations(unittest.TestCase):
    def test_no_mutations_emitted(self):
        r = savings(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000,
                    wages_401k_contribution=23_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
            filing_status_code=1,
        )
        self.assertEqual(r["mutations"], [])


# ---------------------------------------------------------------------------
# Owner selection — megaBackdoor.spe line 81 taxPayerSpouseOrJointLabel from
#   activity.general.wgTpSp (0 -> taxpayer/(T), 1 -> spouse/(S)).
# ---------------------------------------------------------------------------
class TestOwnerSelection(unittest.TestCase):
    def test_taxpayer_owner(self):
        r = assess(
            w2=dict(wg_tp_sp=0, prefix=1, wg_fed_wages=250_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
        )
        self.assertEqual(r["taxpayer_spouse_or_joint"], "taxpayer")

    def test_spouse_owner(self):
        r = assess(
            w2=dict(wg_tp_sp=1, prefix=2, wg_fed_wages=250_000),
            retirement=dict(max_solo_401k_allowed=69_000,
                            current_year_max_401k_allowed=23_000),
        )
        self.assertEqual(r["taxpayer_spouse_or_joint"], "spouse")


if __name__ == "__main__":
    unittest.main(verbosity=2)
