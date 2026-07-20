# 401(k) Employer Contribution

**SPE folder:** `401k Employer Contribution`

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
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `namEmp` | W-2 employer info |  |
| `solo401kContribution` | user answer / source doc | Actual solo 401(k) contribution — entered. |
| `taxYear` | user answer / source doc | Context/input value, not an engine computation. |
| `usWageInp` | W-2 |  |
| `wages401kContribution` | W-2 |  |
| `wages403bContribution` | W-2 |  |
| `wg457b` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 39
- **prior-year:** 1
- **user-data:** 13
- **total extracted:** 53

## Advisor lever (guess)

contribution (wages401kContribution); contribution (wages403bContribution); contribution (solo401kContribution)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

