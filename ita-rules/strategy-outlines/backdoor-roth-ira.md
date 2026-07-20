# Backdoor Roth IRA

**SPE folder:** `Backdoor Roth IRA`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `nonDeductibleIRA` | user answer / source doc | Form 8606 nondeductible IRA basis — user-tracked. |

## ENGINE fields summary

- **calculated:** 20
- **undeterminable-template:** 1
- **user-data:** 3
- **total extracted:** 24

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

