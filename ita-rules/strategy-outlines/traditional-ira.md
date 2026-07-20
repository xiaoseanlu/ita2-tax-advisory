# Traditional IRA

**SPE folder:** `Traditional IRA`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `rothCont` | user answer / source doc | Actual Roth contribution elected by taxpayer. |
| `spIRAContr` | IRA statement / Form 5498 |  |
| `tpIRAContr` | IRA statement / Form 5498 |  |

## ENGINE fields summary

- **calculated:** 22
- **undeterminable-template:** 1
- **user-data:** 6
- **total extracted:** 29

## Advisor lever (guess)

contribution (rothCont)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

