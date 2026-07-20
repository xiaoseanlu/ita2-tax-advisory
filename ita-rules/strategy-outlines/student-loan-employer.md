# Student loan payments made by employer

**SPE folder:** `Student loan payments made by employer`

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
| `studentLoanInterestPaid` | user answer / source doc | Interest paid (e.g. Form 1098-E). |
| `taxPayer` | user answer / source doc |  |
| `usWageInp` | W-2 |  |
| `wages403bContribution` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgMedTxwH` | W-2 |  |
| `wgMedwages` | W-2 |  |
| `wgSSTxwH` | W-2 |  |
| `wgSSwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 18
- **user-data:** 16
- **total extracted:** 34

## Advisor lever (guess)

contribution (wages403bContribution)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

