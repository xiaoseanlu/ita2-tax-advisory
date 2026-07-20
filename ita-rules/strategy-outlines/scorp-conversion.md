# S-Corporation entity selection

**SPE folder:** `Scorp`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- positive net income

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `deleteNextYear` | user answer / source doc |  |
| `eINemp` | W-2 employer info |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `fsaContribution` | Benefits statement |  |
| `namEmp` | W-2 employer info |  |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `selfEmployment` | Schedule K-1 (1065) |  |
| `substantiatedEmployeeExp` | Employee-expense records |  |
| `usBusIncInp` | Sole-prop books |  |
| `usEstateTrustInp` | user answer / source doc |  |
| `usFarmIncInp` | Farm records |  |
| `usPShipInp` | Schedule K-1 (1065) |  |
| `usRentRoyInp` | Rental records |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |
| `usWageInp` | W-2 |  |
| `usWageInp408p` | W-2 |  |
| `wages401kContribution` | W-2 |  |
| `wages403bContribution` | W-2 |  |
| `wagesMedicalSavingsAccount` | W-2 |  |
| `wagesadoptionCredit` | W-2 |  |
| `wagesdesignated401kRothContribution` | W-2 |  |
| `wagesdesignated403bRothContribution` | W-2 |  |
| `wagesdesignated457bRothContribution` | W-2 |  |
| `wageshealthSavingsAccount` | W-2 |  |
| `wg408k6` | W-2 |  |
| `wg457b` | W-2 |  |
| `wg501c` | W-2 |  |
| `wgDCB` | W-2 |  |
| `wgFedTxwH` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgMedTxwH` | W-2 |  |
| `wgMedwages` | W-2 |  |
| `wgSSTxwH` | W-2 |  |
| `wgSSwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 23
- **user-data:** 35
- **total extracted:** 58

## Advisor lever (guess)

contribution (wages401kContribution); contribution (wages403bContribution); benefits contribution

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

