# Flex Spending Account

**SPE folder:** `FSA Contribution`

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
| `fsaContribution` | Benefits statement |  |
| `namEmp` | W-2 employer info |  |
| `usWageInp` | W-2 |  |
| `wageshealthSavingsAccount` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgMedTxwH` | W-2 |  |
| `wgMedwages` | W-2 |  |
| `wgSSTxwH` | W-2 |  |
| `wgSSwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 20
- **prior-year:** 1
- **user-data:** 14
- **total extracted:** 35

## Advisor lever (guess)

benefits contribution

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

