# Tax Strategy Conditions & Minimal Input Analysis

This document lists the specific conditions within each ITA strategy and evaluates whether a minimal input set is sufficient to evaluate them.

**Canonical JSON:** See `strategy-evaluation-input.json` for the full input schema, strategy conditions, and input-to-strategy mapping. Pass `strategy_input_summary` + `form_1040_calculated_lines` (output summary) for strategy evaluation.

## Proposed Minimal Input Set

| Input | Description | TP/Spouse Split |
|-------|-------------|-----------------|
| **Schedule C net income** | Net profit/loss from sole proprietorship (single number or per-activity) | Optional |
| **Schedule E rental income** | Net rental income/loss | Optional |
| **Schedule E pass-through income** | K-1 income from S-Corps, Partnerships (could be separate line items) | Yes, if meaningful |
| **Wage income** | W-2 wages | **Yes – taxpayer vs spouse** |

## Strategy-by-Strategy Conditions

### Entity (4 strategies)

| ID | Title | Key Conditions | Covered by Minimal Set? |
|----|-------|----------------|------------------------|
| **ita_001** | Real Estate Professional | 50%+ personal services in RE; 750+ hours in RE; material participation | **NO** – Needs hours/time allocation, not income |
| **ita_002** | S-Corp Election | Schedule C net $60K+; domestic corp; reasonable comp | **YES** – Schedule C net suffices |
| **ita_003** | S-Corp Reasonable Comp | S-Corp shareholder; W-2 before distributions | **Partial** – Pass-through (S-Corp) + W-2 from same biz indicates S-Corp; detailed comp analysis needs more |
| **ita_004** | Pass-Through Entity Selection | Compare LLC/partnership/S-Corp; SE tax, liability | **YES** – Schedule C vs pass-through vs wages gives comparison |

---

### Business (18 strategies)

| ID | Title | Key Conditions | Covered by Minimal Set? |
|----|-------|----------------|------------------------|
| **ita_006** | Employee Accountable Reimbursement | Employee biz expenses; receipts | **Partial** – Wages imply employee; can't know expenses |
| **ita_007** | Employer Accountable Plan | Written plan; eligible biz expenses | **Partial** – Schedule C or pass-through = business |
| **ita_009** | Home Office Deduction | Exclusive, regular biz use; principal place | **YES** – Schedule C net = business |
| **ita_010** | Business Travel Optimization | Primary purpose business; business days | **Partial** – Schedule C = business; can't evaluate travel |
| **ita_016** | MERP | Small biz; §105 plan; owner/spouse | **YES** – Schedule C or pass-through |
| **ita_017** | §1031 Like-Kind Exchange | Real property; business or investment | **Partial** – Schedule E = real estate; need sale intent |
| **ita_018** | Augusta Rule (14-Day Rental) | Rent personal residence ≤14 days | **NO** – Need rental days, FMV, business purpose |
| **ita_020** | Hiring Children | Legitimate work; family business | **Partial** – Schedule C = biz; **need dependents/children** |
| **ita_021** | Hiring Spouse | Bona fide services; reasonable comp | **YES** – Schedule C + spouse indicator (wages TP vs spouse) |
| **ita_024** | Installment Sale | Capital gain; payment in later year | **NO** – Need capital gains |
| **ita_025** | Bonus Depreciation | Equipment/vehicles; 20yr or less; placed in service | **NO** – Need equipment/asset purchases |
| **ita_026** | Section 179 | Tangible property; placed in service; $1.22M limit | **NO** – Need equipment/asset purchases |
| **ita_027** | Cost Segregation | Commercial/rental RE; $500K+ cost | **Partial** – Schedule E = rental; need **property cost** |
| **ita_028** | QBI Deduction (§199A) | Schedule C/K-1/rental; taxable income under threshold | **YES** – All income types in set |
| **ita_029** | QBI Phase-Out Planning | Taxable income near phase-out | **YES** – With income sum + filing status can estimate |
| **ita_030** | Startup Cost Amortization | Costs before biz begins | **NO** – Need startup costs |
| **ita_031** | Startup Expense Deduction | $5K immediate; investigation, creation | **NO** – Need startup costs |

---

### Retirement (12 strategies)

| ID | Title | Key Conditions | Covered by Minimal Set? |
|----|-------|----------------|------------------------|
| **ita_033** | 401(k) Age 60+ Catch-Up | W-2 employee; age 60+ | **Partial** – Wages = W-2; **need age** |
| **ita_034** | 401(k) Employee Deferral | W-2 employee; $23.5K limit | **YES** – Wages with TP/spouse |
| **ita_035** | 401(k) Employer Match | W-2; maximize match | **YES** |
| **ita_036** | 403(b) Deferral | School, 501(c)(3), church employer | **Partial** – W-2; can't know employer type |
| **ita_037** | 403(b) Employer Match | Nonprofit employer | **Partial** – Same |
| **ita_039** | Backdoor Roth IRA | Income above phase-out | **Partial** – Income sum possible; need MAGI for phase-out |
| **ita_040** | Mega Backdoor Roth | Plan allows after-tax; in-service conversion | **Partial** – W-2; can't know plan |
| **ita_041** | Direct Roth IRA | Earned income; under phase-out | **Partial** – Have earned income |
| **ita_042** | Roth Conversion | Traditional/SEP/SIMPLE IRA | **NO** – Need IRA balances |
| **ita_043** | SEP-IRA | Self-employed; 25% comp or $70K | **YES** – Schedule C net = self-employment |
| **ita_044** | Solo 401(k) | Self-employed; no employees (except spouse) | **YES** – Schedule C; no employees often inferred |
| **ita_045** | Traditional IRA | Earned income; deductibility | **YES** – Wages + Schedule C |

---

### Credits (3 strategies)

| ID | Title | Key Conditions | Covered by Minimal Set? |
|----|-------|----------------|------------------------|
| **ita_046** | R&D Tax Credit | Four-part test; QREs; wages, supplies | **NO** – Need R&D expenses, project details |
| **ita_047** | Child Tax Credit | Child under 17; dependent; MAGI phase-out | **NO** – **Need dependents/children** |
| **ita_048** | Residential Energy Credits | Heat pumps, insulation, windows | **NO** – Need home improvements |

---

### Charitable (3 strategies)

| ID | Title | Key Conditions | Covered by Minimal Set? |
|----|-------|----------------|------------------------|
| **ita_049** | Donate Appreciated Securities | Held 12+ months; FMV deduction | **NO** – Need investment holdings |
| **ita_050** | Donor-Advised Fund | Cash/securities to DAF | **Partial** – High income may warrant; no security info |
| **ita_051** | IRA QCD | Age 70.5+; $105K/person | **NO** – Need age, IRA |

---

### Individual (9 strategies)

| ID | Title | Key Conditions | Covered by Minimal Set? |
|----|-------|----------------|------------------------|
| **ita_005** | HSA + FSA Coordination | HDHP; cannot have both | **NO** – Need health plan type |
| **ita_008** | Bunching Itemized | Itemized near standard; SALT, charitable | **NO** – **Need itemized components** (SALT, mortgage, charitable) |
| **ita_011** | Student Loan §127 | Employer plan | **Partial** – W-2; can't know plan |
| **ita_012** | Dependent Care FSA | Employer cafeteria; $5K | **Partial** – W-2 |
| **ita_013** | Health Care FSA | §125 plan; $3,200 max | **Partial** – W-2 |
| **ita_014** | Pre-Tax Health Premiums | Section 125 or self-employed | **Partial** – Both in set |
| **ita_015** | HSA Maximization | HDHP; max contribution | **NO** – Need health plan |
| **ita_019** | Capital Gain Timing | LTCG; bracket management | **NO** – **Need capital gains** |
| **ita_022** | Tax Loss Harvesting (LTCG) | LT losses; offset gains | **NO** – **Need capital gains/losses** |
| **ita_023** | Tax Loss Harvesting (STCG) | ST losses; before 12 months | **NO** – **Need capital gains/losses** |

---

## Summary: Is the Minimal Set Sufficient?

### Fully evaluable with minimal set only (≈17 strategies)

- **Entity:** ita_002, ita_004
- **Business:** ita_009, ita_016, ita_021, ita_028, ita_029
- **Retirement:** ita_034, ita_035, ita_043, ita_044, ita_045

### Partially evaluable (≈12 strategies)

- **Entity:** ita_003
- **Business:** ita_006, ita_007, ita_010, ita_017, ita_020, ita_027
- **Retirement:** ita_033, ita_036, ita_037, ita_039, ita_040, ita_041
- **Charitable:** ita_050
- **Individual:** ita_011, ita_012, ita_013, ita_014

### Not evaluable without additional inputs (≈18 strategies)

- **Entity:** ita_001 (hours)
- **Business:** ita_018, ita_024, ita_025, ita_026, ita_030, ita_031
- **Retirement:** ita_042
- **Credits:** ita_046, ita_047, ita_048
- **Charitable:** ita_049, ita_051
- **Individual:** ita_005, ita_008, ita_015, ita_019, ita_022, ita_023

---

## Gaps for Full Strategy Coverage

| Gap | Strategies Affected | Possible addition |
|-----|---------------------|-------------------|
| **Dependents/children** | ita_047 (CTC), ita_020 (Hiring Kids) | `dependents[]` with age/qualifying_child_under_17 |
| **Capital gains/losses** | ita_019, ita_022, ita_023, ita_024, ita_049 | `short_term_capital_gain_loss`, `long_term_capital_gains` |
| **Age** | ita_033, ita_051 | `age_65_or_older` or `birth_year` |
| **Itemized deduction components** | ita_008 (Bunching) | `state_and_local_taxes`, `mortgage_interest`, `charitable_contributions` |
| **Equipment/asset purchases** | ita_025, ita_026 | `depreciable_assets[]` (basis, recovery period, placed_in_service) |
| **Taxable income / AGI** | QBI phase-out, IRA phase-outs | **Derivable** from income + filing status + standard deduction (estimate) |
| **Rental days / Augusta Rule** | ita_018 | `rental_days` if personal residence rented to business |

---

## Recommendation

**The minimal set (Schedule C net, Schedule E rental, Schedule E pass-through, Wages with TP/spouse) is sufficient for ~17 strategies and partially sufficient for ~12 more.**

For a **core business/entity/retirement focus**, it works well:
- S-Corp election, entity selection
- Home office, MERP, Hiring Spouse, QBI, QBI phase-out
- 401k deferral/match, SEP-IRA, Solo 401k, Traditional IRA

To cover **most strategies**, add:
1. **Dependents** (count + qualifying_child_under_17) implies CTC, Hiring Children
2. **Capital gains/losses** implies Capital gain timing, loss harvesting, charitable securities, installment sale
3. **Filing status** (if not implied by spouse)
4. **Age** (65+, 70.5) implies Catch-up, IRA QCD
5. **Itemized components** (SALT, mortgage, charitable) implies Bunching
6. **Depreciable assets** (basis, recovery period, placed in service) implies Section 179, Bonus Depreciation
7. **Rental days** (if applicable) implies Augusta Rule

The smallest high-impact extension would be: **dependents + capital gains/losses**, which unlocks credits and several individual strategies.
