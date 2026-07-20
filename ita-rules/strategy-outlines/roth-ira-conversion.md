# Roth IRA conversion

**SPE folder:** `Roth IRA Conversion`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `distCode1` | 1099-R |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `nameOfPensPayer` | 1099-R |  |
| `pensionTpSp` | 1099-R |  |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `usPensInp` | user answer / source doc |  |

## ENGINE fields summary

- **calculated:** 18
- **undeterminable-template:** 1
- **user-data:** 6
- **total extracted:** 25

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

