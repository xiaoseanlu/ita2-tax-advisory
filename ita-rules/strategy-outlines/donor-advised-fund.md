# Donor Advised Fund To Time Contributions

**SPE folder:** `Donor Advised Fund To Time Contributions`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `cash50Lim` | Schedule A |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `totalAvailCharCont` | Schedule A |  |

## ENGINE fields summary

- **calculated:** 18
- **user-data:** 3
- **total extracted:** 21

## Advisor lever (guess)

charitable amount

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

