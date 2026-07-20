# Child Tax Credit

**SPE folder:** `Child Tax Credit`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `addPmt1` | user answer / source doc |  |
| `addPmt2` | user answer / source doc |  |
| `addPmt3` | user answer / source doc |  |
| `addPmt4` | user answer / source doc |  |
| `amtPaidWithExt` | user answer / source doc |  |
| `estTaxPmt` | user answer / source doc |  |
| `fidK1ES` | user answer / source doc |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `prYrOverpmtAppl` | user answer / source doc |  |
| `usEstPmtInp` | user answer / source doc |  |
| `vou1AmtPd` | user answer / source doc |  |
| `vou2AmtPd` | user answer / source doc |  |
| `vou3AmtPd` | user answer / source doc |  |
| `vou4AmtPd` | user answer / source doc |  |

## ENGINE fields summary

- **calculated:** 23
- **prior-year:** 2
- **user-data:** 14
- **total extracted:** 39

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

