# IRA QCD

**SPE folder:** `IRA QCD`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- active activity (deleteNextYear==0)
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `distCode1` | 1099-R |  |
| `distCode2` | 1099-R |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `iraSepSimple` | IRA statement / Form 5498 |  |
| `nameOfPensPayer` | 1099-R |  |
| `pensionTpSp` | 1099-R |  |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `usPensInp` | user answer / source doc |  |

## ENGINE fields summary

- **calculated:** 22
- **prior-year:** 1
- **user-data:** 8
- **total extracted:** 31

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

