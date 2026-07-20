# Pass-through-Entity-Tax

**SPE folder:** `PTET`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `primaryResidentFullStateName` | user answer / source doc | Entered/selected home state (full name). |
| `primaryResidentState` | user answer / source doc | Entered/selected home state. |
| `selfEmployment` | Schedule K-1 (1065) |  |
| `usBusIncInp` | Sole-prop books |  |
| `usEstateTrustInp` | user answer / source doc |  |
| `usFarmIncInp` | Farm records |  |
| `usPShipInp` | Schedule K-1 (1065) |  |
| `usRentRoyInp` | Rental records |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |

## ENGINE fields summary

- **calculated:** 23
- **user-data:** 10
- **total extracted:** 33

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

