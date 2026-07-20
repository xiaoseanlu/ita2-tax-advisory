# Residential Energy Credit

**SPE folder:** `Residential Energy Credit`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `realEstTax` | Schedule A |  |
| `resEnergyInput` | user answer / source doc | Residential energy credit qualifying expenditure. |
| `taxYear` | user answer / source doc | Context/input value, not an engine computation. |

## ENGINE fields summary

- **calculated:** 20
- **prior-year:** 1
- **user-data:** 4
- **total extracted:** 25

## Advisor lever (guess)

energy expenditure

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

