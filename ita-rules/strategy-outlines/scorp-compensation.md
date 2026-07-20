# S Corp Compensation Analysis

**SPE folder:** `Scorp Compensation Analysis`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `eINemp` | W-2 employer info |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `namEmp` | W-2 employer info |  |
| `usScorpInp` | Schedule K-1 (1120-S) |  |
| `usWageInp` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgMedwages` | W-2 |  |
| `wgSSwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 21
- **user-data:** 10
- **total extracted:** 31

## Advisor lever (guess)

Not obvious from extracted field leaves — inspect primary .spe

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

