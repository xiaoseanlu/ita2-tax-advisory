# Medical Expense Reimbursement Plan

**SPE folder:** `Medical Expense Reimbursement Plan`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `selfEmployment` | Schedule K-1 (1065) |  |
| `usBusIncInp` | Sole-prop books |  |
| `usEstateTrustInp` | user answer / source doc |  |
| `usFarmIncInp` | Farm records |  |
| `usPShipInp` | Schedule K-1 (1065) |  |
| `usRentRoyInp` | Rental records |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |

## ENGINE fields summary

- **calculated:** 19
- **user-data:** 8
- **total extracted:** 27

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

