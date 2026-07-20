# Accountable Reimbursement Plan as Employee

**SPE folder:** `Accountable Reimbursement Plan as Employee`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- active activity (deleteNextYear==0)
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `MARGINAL_RATE_FICA` | user answer / source doc |  |
| `deleteNextYear` | user answer / source doc |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `namEmp` | W-2 employer info |  |
| `usWageInp` | W-2 |  |
| `wages401kContribution` | W-2 |  |
| `wages403bContribution` | W-2 |  |
| `wagesAccountableReimbursement` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgMedTxwH` | W-2 |  |
| `wgMedwages` | W-2 |  |
| `wgSSTxwH` | W-2 |  |
| `wgSSwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 17
- **prior-year:** 3
- **user-data:** 15
- **total extracted:** 35

## Advisor lever (guess)

contribution (wages401kContribution); contribution (wages403bContribution)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

