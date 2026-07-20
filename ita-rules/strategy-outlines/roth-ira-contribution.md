# Roth IRA contribution

**SPE folder:** `Roth IRA Contribution`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |

## ENGINE fields summary

- **calculated:** 24
- **user-data:** 1
- **total extracted:** 25

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

