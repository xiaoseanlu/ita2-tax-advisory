# Mega Backdoor Roth

**SPE folder:** `Mega Backdoor Roth`

## Applicable gates (heuristic from .spe)

- applicability
- recommendation
- married filing status
- active activity (deleteNextYear==0)

## USER INPUTS (live user-data fields)

| Field | Likely source | Notes |
|-------|---------------|-------|
| `deleteNextYear` | user answer / source doc |  |
| `filingStatus` | user answer / source doc | Taxpayer selection (single/MFJ/MFS/HOH/QW). |
| `namEmp` | W-2 employer info |  |
| `usWageInp` | W-2 |  |
| `wages401kContribution` | W-2 |  |
| `wages403bContribution` | W-2 |  |
| `wg457b` | W-2 |  |
| `wgFedwages` | W-2 |  |
| `wgTpSp` | W-2 |  |

## ENGINE fields summary

- **calculated:** 23
- **prior-year:** 3
- **user-data:** 9
- **total extracted:** 35

## Advisor lever (guess)

contribution (wages401kContribution); contribution (wages403bContribution)

## Savings formula note

Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe

