# Tax loss harvesting (long-term)

**SPE folder:** `Tax Loss Harvesting - LT`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `lTCapGnloss` | 1099-B / broker |  |
| `netLTCapGnLoss` | 1099-B / broker |  |

## ENGINE fields summary

- **calculated:** 18
- **user-data:** 3
- **total extracted:** 21

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

