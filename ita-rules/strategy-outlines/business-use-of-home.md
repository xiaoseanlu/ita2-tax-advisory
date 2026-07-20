# Business Use of Home

**SPE folder:** `business use of home`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `sETaxAdjCalc` | user answer / source doc |  |
| `selfEmployment` | Schedule K-1 (1065) |  |
| `usBusIncInp` | Sole-prop books |  |
| `usEstateTrustInp` | user answer / source doc |  |
| `usFarmIncInp` | Farm records |  |
| `usPShipInp` | Schedule K-1 (1065) |  |
| `usRentRoyInp` | Rental records |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |

## ENGINE fields summary

- **calculated:** 24
- **undeterminable-template:** 3
- **user-data:** 9
- **total extracted:** 36

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

