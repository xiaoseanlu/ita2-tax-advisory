# Hire Your Kids

**SPE folder:** `Hire Your Kids`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- active activity (deleteNextYear==0)
- positive net income
- filing status check

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `usBusIncInp` | Sole-prop books |  |
| `usPShipInp` | Schedule K-1 (1065) |  |

## ENGINE fields summary

- **calculated:** 21
- **user-data:** 3
- **total extracted:** 24

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

