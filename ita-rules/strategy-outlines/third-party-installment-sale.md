# Third party installment sale

**SPE folder:** `Third Party Installment Sale`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `netCapGnLoss` | 1099-B / broker |  |

## ENGINE fields summary

- **calculated:** 27
- **undeterminable-template:** 1
- **user-data:** 2
- **total extracted:** 30

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

