# HSA Contribution

**SPE folder:** `HSA Contribution`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `familyCoverageHSA` | user answer / source doc | HSA coverage type (family) — plan fact. |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `iTAHSATypeOfCoverageSpouse` | user answer / source doc |  |
| `iTAHSATypeOfCoverageTaxpayer` | user answer / source doc |  |
| `selfOnlyCoverageHSA` | user answer / source doc | HSA coverage type (self-only) — plan fact. |
| `usWageInp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 21
- **undeterminable-template:** 1
- **user-data:** 6
- **total extracted:** 28

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

