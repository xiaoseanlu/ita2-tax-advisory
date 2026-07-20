# Tax loss harvesting (short-term)

**SPE folder:** `Tax Loss Harvesting - ST`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `netSTCapGnLoss` | 1099-B / broker |  |
| `sTCapGnLoss` | 1099-B / broker |  |

## ENGINE fields summary

- **calculated:** 17
- **user-data:** 3
- **total extracted:** 20

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

