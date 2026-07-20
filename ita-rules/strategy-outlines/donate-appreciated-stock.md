# Donating Appreciated Stock

**SPE folder:** `Donating Appreciated Stock to Charity`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- active activity (deleteNextYear==0)

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `defaultSection` | user answer / source doc |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `lTCapGnloss` | 1099-B / broker |  |
| `nonCash20CapGn` | Schedule A |  |

## ENGINE fields summary

- **calculated:** 20
- **prior-year:** 1
- **user-data:** 4
- **total extracted:** 25

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

