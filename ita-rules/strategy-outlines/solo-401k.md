# Solo 401(k)

**SPE folder:** `Solo 401k Contribution`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- active activity (deleteNextYear==0)
- no SEP-IRA conflict
- contribution headroom
- positive SE income
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `eINemp` | W-2 employer info |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `sepIRA` | user answer / source doc | Actual SEP-IRA contribution — preparer/taxpayer entry. |
| `solo401kContribution` | user answer / source doc | Actual solo 401(k) contribution — entered. |
| `spsEElectDef` | Self-employed plan records |  |
| `taxYear` | user answer / source doc | Context/input value, not an engine computation. |
| `tpSEElectDef` | Self-employed plan records |  |
| `usBusIncInp` | Sole-prop books |  |
| `usFarmIncInp` | Farm records |  |
| `usPShipInp` | Schedule K-1 (1065) |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |
| `usWageInp` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 43
- **prior-year:** 1
- **undeterminable-template:** 1
- **user-data:** 16
- **total extracted:** 61

## Advisor lever (guess)

contribution (solo401kContribution); contribution (sepIRA)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

