# Bunching Itemized Deductions

**SPE folder:** `Bunching Itemized Deductions`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `cash50Lim` | Schedule A |  |
| `defaultSection` | user answer / source doc |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `itemDedAll` | Schedule A |  |
| `medExp` | Schedule A |  |
| `mtgeIntPts` | Schedule A |  |
| `realEstTax` | Schedule A |  |
| `totAllContr` | Schedule A |  |
| `totAllowMedExp` | Schedule A |  |
| `usItemDedSumAGI75` | Schedule A |  |
| `usTaxesLimitation` | Schedule A |  |
| `usTaxesTotalStateandLocal` | Schedule A |  |

## ENGINE fields summary

- **calculated:** 18
- **user-data:** 12
- **total extracted:** 30

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

