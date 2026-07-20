# SEP-IRA

**SPE folder:** `SEP-IRA`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- active activity (deleteNextYear==0)
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `deleteNextYear` | user answer / source doc |  |
| `eINemp` | W-2 employer info |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `sepsimpleQualifiedPlansTaxpayer` | user answer / source doc |  |
| `sepsimpleQualifiedPlansspouse` | user answer / source doc |  |
| `solo401kContribution` | user answer / source doc | Actual solo 401(k) contribution — entered. |
| `spsEPContr` | Self-employed plan records |  |
| `tpSEPContr` | Self-employed plan records |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |
| `usWageInp` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 22
- **undeterminable-template:** 2
- **user-data:** 14
- **total extracted:** 38

## Advisor lever (guess)

contribution (solo401kContribution)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

