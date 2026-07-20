# Augusta Rule - tax-free rental income

**SPE folder:** `Augusta Rule-Rental Income (Tax Free)`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `mortgageInterestFromOtherSchedules` | Schedule A |  |
| `mtgeIntPts` | Schedule A |  |
| `realEstTax` | Schedule A |  |
| `totIntPd` | Schedule A |  |
| `usItemDedInp` | Schedule A |  |

## ENGINE fields summary

- **calculated:** 17
- **user-data:** 6
- **total extracted:** 23

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

