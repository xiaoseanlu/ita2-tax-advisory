# Capital gain timing

**SPE folder:** `Capital Gain Timing`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `cap1231Gn` | 1099-B / broker |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `netLTCapGnLoss` | 1099-B / broker |  |

## ENGINE fields summary

- **calculated:** 28
- **user-data:** 3
- **total extracted:** 31

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

