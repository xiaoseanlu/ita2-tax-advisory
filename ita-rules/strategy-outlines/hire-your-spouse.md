# Hire your Spouse

**SPE folder:** `Hire Your Spouse`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- active activity (deleteNextYear==0)
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `childDepcarecr` | user answer / source doc |  |
| `depCareExp` | user answer / source doc |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `usBusIncInp` | Sole-prop books |  |
| `usPShipInp` | Schedule K-1 (1065) |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |

## ENGINE fields summary

- **calculated:** 24
- **prior-year:** 1
- **user-data:** 6
- **total extracted:** 31

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

