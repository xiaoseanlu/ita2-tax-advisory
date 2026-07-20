# S Corporation Choice of Entity — Strategy Logic Guide

**Source repo:** `tax-strategy-content`  
**Strategy folder:** `IndUS/strategies/Scorp/`  
**ITA card title:** "S Corporation choice of entity"  
**Primary strategy file:** `sCorp-SE-Tax-Savings.spe`

This document consolidates how the ITA S-Corp conversion strategy decides applicability, what the user controls, what gets written to the projection tax model, and how tax savings are computed.

---

## 1. File map

| File | Role |
|------|------|
| `sCorp-SE-Tax-Savings.spe` | **Primary** — find SE businesses, recommend, orchestrate apply / disable |
| `SE_Income.spe` | Secondary Steps 1–3 — zero old SE income + SE tax effects |
| `new_w2.spe` | Secondary Step 4 (+ payroll tax secondaries) — reasonable wage → new W-2 |
| `new_scorp.spe` | Secondary Steps 5–6 — new S-Corp K-1 / ordinary income |
| `strategyCard.json` | Product card, education, requirements |
| `unitTests.spe` | Regression / recommendation / migration tests |
| `strategies/common/setup_business_activities.spe` | Builds Sch C / E / F / K-1 activity lists used by primary |
| `strategies/common/setup_global.spe` | Taxpayer / spouse / indexed amounts |
| `strategies/common/rate_global.spe` | Marginal rate helpers |

Secondary identifiers used at runtime:

| Identifier | SPE | Step |
|------------|-----|------|
| `SE_Income_ZeroOut` | `SE_Income.spe` | 1 — zero original SE activity |
| `SE_Income_TaxSavings` | `SE_Income.spe` | 2 — remove SE tax |
| `SE_Tax_Adj_Impact` | `SE_Income.spe` | 3 — lose ½ SE tax AGI deduction |
| `new_w2` | `new_w2.spe` | 4 — pay reasonable wage (W-2) |
| `payroll_tax_employee` | `new_w2.spe` | Owner wage subject to payroll taxes |
| `payroll_tax_employer` | `new_w2.spe` | Employer payroll tax portion |
| `new_scorp` | `new_scorp.spe` | 5–6 — residual as S-Corp ordinary income |

---

## 2. What the strategy is trying to do

Convert a self-employed business (typically Schedule C; also Schedule F or partnership SE) into an S Corporation structure where:

1. The old SE activity’s income is **zeroed / removed** from the next-year projection.
2. The owner takes a **reasonable wage** (new W-2) — subject to income tax + FICA.
3. Remaining profit flows as **S-Corp ordinary income** (new S-Corp K-1) — **not** subject to SE tax.
4. Net savings ≈ SE tax eliminated − wage income tax − FICA + related deduction effects.

ITA does **not** compute a “correct” reasonable salary. The advisor must enter it (`additional_info` warns about IRS scrutiny).

---

## 3. When it applies / recommends

### Inputs that build the business list

`setup_business_activities.spe` loads activities and computes, among other fields:

- `netIncome` (e.g. Schedule C `itaNetProfitLoss`)
- `netEarnings` ≈ `round(netIncome × netEarningsRatio)` (typically 92.35%)
- `isSEBiz` (Schedule C: subject to SE tax)
- `ownershipPct` (default 100 for Sch C; from K-1 for partnerships)
- `SEtaxSavings` ≈ `min(netEarnings, SS wage base) × SE rate`
- Model path IDs for projection / base / actual

### Applicability (primary global)

```text
Applicable  = business with netEarnings > 0 AND isSEBiz
Recommended = Applicable AND ownershipPct >= 50%
              (top 1 per taxpayer / spouse / joint by netEarnings)
```

From `sCorp-SE-Tax-Savings.spe`:

```text
tpSEApplicableGroups = businesses where (netEarnings > 0) && isSEBiz
recommendedSEforTaxPayer = applicables where ownershipPct >= 50
                           → keep top 1 by netEarnings
```

Same pattern for spouse and joint. Recommendations / applicables are the concat of those groups.

### Product card requirements (`strategyCard.json`)

- Taxpayer/spouse must have a self-employed activity (Sch C, F, or partnership K-1 with SE).
- S-Corp conversion eligibility / reasonable compensation diligence is an advisor concern.
- Impact framing: projected S-Corp net earnings sheltered from SE tax.

---

## 4. The one user-controlled lever

**Editable input = reasonable wage.**

| Surface | Parameter | Meaning |
|---------|-----------|---------|
| Wage popup / additional info | `wagePopup` | Advisor-entered reasonable salary |
| Secondary `new_w2` | `STRATEGY_CHANGE` (editable) | Same wage; this is the real write driver for W-2 |
| Primary | `netIncomeAllocatedToWages` | Copied from `new_w2.STRATEGY_CHANGE` or `wagePopup` |

On the **primary** card, `STRATEGY_CHANGE` is **not** the wage. On apply, primary sets:

```text
primary.STRATEGY_CHANGE = −netIncome
```

That means: “zero out the original SE activity’s income.” The wage lives on `new_w2`.

```text
netIncomeAllocatedToWages =
    new_w2.STRATEGY_CHANGE   if present
    else wagePopup
```

---

## 5. End-to-end flow

```text
SE business (Sch C / F / Partnership)
  netEarnings > 0, often ownership ≥ 50% for recommendation
        │
        ▼
Advisor enters reasonable wage
        │
        ├─ Step 1  SE_Income_ZeroOut
        │            STRATEGY_CHANGE = −netIncome on original activity
        │
        ├─ Step 2  SE_Income_TaxSavings
        │            Remove SE tax on projection adjustments
        │
        ├─ Step 3  SE_Tax_Adj_Impact
        │            Lose ½ SE tax AGI deduction
        │
        ├─ Step 4  new_w2
        │            Create W-2; wgFedwages = wage
        │            (+ payroll_tax_employee / employer secondaries)
        │
        └─ Steps 5–6  new_scorp
                     Create S-Corp K-1
                     ordinary = netIncome − wages − employer FICA/2

Primary also marks original activity: deleteNextYear = 1

Net PROJECTED_TAX_SAVINGS (primary rollup)
  = SE income tax back-out
  + SE tax saved
  − lost ½ SE deduction benefit
  − wage income tax cost
  − FICA on wages
  − tax on S-Corp ordinary income
  + tax benefit of deducting employer FICA half
```

---

## 6. Primary apply logic (`sCorp-SE-Tax-Savings.spe` → `added:`)

### Resolve schedule path

Maps `SOURCE` to ITA income containers:

| SOURCE | Path under `$.projection.return.income.usIncSum.` |
|--------|-----------------------------------------------------|
| Schedule C (default) | `usBusIncSum.usBusIncInp` |
| Schedule F | `usFarmIncSum.usFarmIncInp` |
| Schedule E | `usRentRoyInp` |
| Partnership | `usPassthrSum.usPShipInp` |
| SCorp | `usPassthrSum.usScorpInp` |

Target:

```text
$.projection.return.income.usIncSum.<schedule>[?(@.prefix == <activity.prefix>)]
```

### Mark original activity

```text
output update that activity
generalInformation.deleteNextYear = 1
```

### Wage + primary STRATEGY_CHANGE

```text
wage = new_w2.STRATEGY_CHANGE or wagePopup
netIncomeAllocatedToWages = wage
primary.STRATEGY_CHANGE = −netIncome
PROJECTED_AMOUNT = 0
```

### FICA / SS Subject calculations (high level)

Using indexed rates (`marginalRateSocialSecurity`, `marginalRateMedicare`, `maxSSwage`, `netEarningRatio`) and already-taxed SS / SE income for taxpayer or spouse:

```text
SE tax reduction ≈ SS tax saved on SE earnings leaving + Medicare on SE earnings leaving
Wages FICA       ≈ SS (capped) + Medicare on reasonable wage
Employer half    ≈ WagesFICA / 2

S-Corp distribution base =
    netIncome − netIncomeAllocatedToWages

ScorpDistributionMinusFICA =
    distribution − WagesFICAEmployerHalf
```

### Primary tax savings rollup

```text
secondarySavingsTotal =
    SEIncomeBackOutTaxSavings      // netIncome × total marginal rate
  + SETaxReductionSETax            // SE tax dollars eliminated
  − secSeTaxDeductionLost          // (½ SE tax) × federal rate
  − wagesIncomeTaxCosts            // wages × total marginal rate
  − WagesFICA                      // full FICA on wages
  − secNewSCorpIncomeTaxCosts     // S-Corp ordinary × total marginal rate
  + secNewSCorpFICATaxSavings      // employer FICA/2 × total marginal rate

PROJECTED_TAX_SAVINGS = secondarySavingsTotal
CASH_OUTLAY = 0 (+ any totalCashOutlayAdjustments)
```

Primary also allocates a new S-Corp prefix (`NEW_SCORP_PREFIX`) for secondaries to attach to.

### Disable

```text
deleteNextYear = 0
PROJECTED_AMOUNT = 0
```

(Removes the “park this activity next year” flag.)

---

## 7. Secondary: zero SE income (`SE_Income.spe`)

### `SE_Income_ZeroOut` (Step 1)

```text
STRATEGY_CHANGE = −primary.netIncome   (non-editable)
Description: "Sch C income is shifted to a newly formed S Corp, bringing Sch C income to 0."
```

Model path = same specific schedule/prefix as the primary activity.

On add, it also participates in SE income bookkeeping (strategy-change baselines on taxpayer/spouse SE items) so later SE-tax secondaries stay consistent.

### `SE_Income_TaxSavings` (Step 2)

```text
STRATEGY_CHANGE related to −netEarnings (SE earnings removed)
Model path: $.projection.return.adjustments.usAdjSum.defaultSection.sETaxAdjCalc
Description: taxpayer no longer has SE income → doesn't pay SE tax
```

May include additional Medicare interactions when income vs. threshold requires it.

### `SE_Tax_Adj_Impact` (Step 3)

```text
STRATEGY_CHANGE = −(½ SE tax) effect on AGI deduction
Model path: same sETaxAdjCalc area
Description: lose the SE income tax deduction because SE tax went away
```

---

## 8. Secondary: reasonable wage → W-2 (`new_w2.spe`)

### `new_w2` (Step 4) — the cleanest “input → write” path

```text
STRATEGY_CHANGE = reasonable wage (editable)
PROJECTED_AMOUNT = BASELINE (0) + STRATEGY_CHANGE

Write new W-2:
  $.projection.return.income.usIncSum.usWageSum.usWageInp[?(@.prefix == newPrefix)]

  federal.wgFedwages = STRATEGY_CHANGE
  federal.wgSSwages  = min(STRATEGY_CHANGE, maxSSwage)
  federal.wgMedwages = STRATEGY_CHANGE
  (withholding / Box 12 codes zeroed)
  other.wgSCorp2PctShrhldr = 1
```

Description: *"The owner is paid a reasonable wage, which is subject to income tax."*

Disable zeros wages on that prefix / marks employer as new / deleteNextYear as appropriate.

### `payroll_tax_employee`

Documents that the Step 4 wage is subject to payroll taxes. `STRATEGY_CHANGE` mirrors reasonable wages; tax savings presentation is tied to that wage.

### `payroll_tax_employer`

```text
employerPayrollPortion scaled by ownershipPct when relevant
STRATEGY_CHANGE = −employerPayrollPortion
May write against the new S-Corp path for employer-side payroll expense impact
```

---

## 9. Secondary: residual profit → S-Corp (`new_scorp.spe`)

### `new_scorp` (Steps 5–6)

Creates / updates:

```text
$.projection.return.income.usIncSum.usPassthrSum.usScorpInp[?(@.prefix == newPrefix)]
```

Core income override:

```text
iTAScorpNetincLoss =
    netIncome − netIncomeAllocatedToWages − WagesFICAEmployerHalf
```

```text
STRATEGY_CHANGE = netIncome − netIncomeAllocatedToWages
PROJECTED_AMOUNT = same (distribution before some FICA detail)
TaxSavings presentation ≈ −STRATEGY_CHANGE × total marginal rate
```

Description: *"Whatever income is not allocated to reasonable wages is allocated to ordinary income."*

Ownership percentage is read from the primary activity when present; defaults toward 100% for sole props.

---

## 10. Model paths cheat sheet

| What | Path pattern |
|------|----------------|
| Original Schedule C activity | `$.projection.return.income.usIncSum.usBusIncSum.usBusIncInp[?(@.prefix == N)]` |
| Original Schedule F | `…usFarmIncSum.usFarmIncInp[?(@.prefix == N)]` |
| Original partnership | `…usPassthrSum.usPShipInp[?(@.prefix == N)]` |
| New W-2 | `…usWageSum.usWageInp[?(@.prefix == newW2Prefix)]` |
| New S-Corp | `…usPassthrSum.usScorpInp[?(@.prefix == newScorpPrefix)]` |
| SE tax adjustment | `$.projection.return.adjustments.usAdjSum.defaultSection.sETaxAdjCalc` |

Wage leaf that matters most:

```text
usWageInp[].federal.wgFedwages
```

S-Corp income leaf that matters most:

```text
usScorpInp[].netIncomeLossOverride.iTAScorpNetincLoss
```

---

## 11. vs Bunching Itemized Deductions

| | Bunching | S-Corp conversion |
|--|----------|-------------------|
| User lever | Extra charity (`STRATEGY_CHANGE`) | Reasonable wage (`new_w2.STRATEGY_CHANGE`) |
| Primary STRATEGY_CHANGE | Charity delta | `−netIncome` (zero old activity) |
| Writes | **One field:** `cash50Lim` | **Bundle:** W-2 + S-Corp + zero SE + SE adj |
| Savings driver | Itemized above standard × rate | SE tax out vs wage/FICA/income tax tradeoff |
| Complexity | Single write, multi-threshold math | Multi-secondary orchestration |

---

## 12. Implications for project-air / agent tools

**Implemented:** Skill + Tool under  
`skills/income_tax/assisted/scorp-conversion/`  
(see `INPUTS.md`, `tools/scorp_conversion.py`, `scripts/run_agent.py`).

If modeling “Apply S-Corp” as a tool (similar to Apply Bunching):

**Minimum inputs**

- Which business activity (schedule + prefix), or detectable SE Sch C
- Reasonable wage (advisor/user-entered; do not invent)
- Filing status / ownership when relevant
- Tax year / projection scenario

**Minimum projection mutations**

1. Zero / deprecate original SE activity income (`deleteNextYear` or equivalent netIncome write)
2. Add W-2 wages = reasonable wage
3. Add S-Corp ordinary = netIncome − wage (− employer FICA half if matching ITA)
4. Adjust SE tax / ½ SE deduction if the engine exposes those as writable; otherwise rely on recalculate

**Do not expect** a single `STRATEGY_CHANGE` on the primary card to equal the wage — that amount lives on the `new_w2` secondary in production ITA.

A faithful LLM demo can approximate:

```text
Sch C net → 0
W-2 wages → W
S-Corp K-1 → max(SchC_net − W, 0)   # optionally reduce by employer FICA/2
Recalculate tax (genai_tax_core)
```

…and narrate SE-tax savings separately if the tax engine does not automatically drop SE tax when Sch C is zeroed.

---

## 13. How to re-inspect in this repo

```bash
# Strategy input outline (project-air helper)
cd ita-rules
python3 outline_strategy_inputs.py Scorp --show-includes --user-only

# Source of truth
open ~/Documents/GitHub/tax-strategy-content/IndUS/strategies/Scorp/sCorp-SE-Tax-Savings.spe
```

---

## 14. Source line anchors (for quick navigation)

| Concept | File | Approx. area |
|---------|------|----------------|
| Applicability / recommend | `sCorp-SE-Tax-Savings.spe` | `global:` lines ~9–36 |
| Primary recommendation params | `sCorp-SE-Tax-Savings.spe` | `recommendation:` ~38–152 |
| Primary apply + savings rollup | `sCorp-SE-Tax-Savings.spe` | `added:` ~154–284 |
| Mark deleteNextYear | `sCorp-SE-Tax-Savings.spe` | `added:` ~181–182 |
| Wage popup → allocated wages | `sCorp-SE-Tax-Savings.spe` | `added:` ~184–187 |
| W-2 write `wgFedwages` | `new_w2.spe` | `added:` ~103–136 |
| S-Corp `iTAScorpNetincLoss` write | `new_scorp.spe` | `added:` ~181–218 |
| Zero SE / SE tax / adj | `SE_Income.spe` | secondary blocks throughout |
| Business activity construction | `common/setup_business_activities.spe` | Schedule C block ~10–53 |

---

*Generated from `tax-strategy-content` IndUS Scorp SPE sources for use in Project AIR / ITA 2.0 alignment. Static source interpretation — not a runtime engine trace.*
