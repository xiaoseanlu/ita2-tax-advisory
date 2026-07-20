# S-Corp conversion — inputs by Skill part

Core Skill is **two Tool calls**. Neither requires an LLM.

---

## Owner of the Schedule C (critical)

### `activity.taxpayer_spouse_or_joint`

| Value | Meaning |
|-------|---------|
| `taxpayer` | Schedule C (or SE activity) belongs to the primary taxpayer |
| `spouse` | Belongs to the spouse |
| `joint` | Joint SE activity (SPE joint path) |

**Why it matters for savings:** Social Security tax is **per person**. If that owner already has large **W-2 wages**, they may already be at (or near) the SS wage base. Converting Sch C → S-Corp then saves little or no **12.4% SS** on the SE earnings being removed—Medicare may still apply. Pass wages already subject to SS for **that same person** as `rates.income_already_taxed_by_ss`.

**Negative / zero net income:** If `net_income` ≤ 0 (or derived `net_earnings` ≤ 0), Part 1 treats the activity as **not applicable**—there is little or no SE tax to shed. Do not expect material savings from conversion in that case.

---

## Part 1 — `assess_scorp_applicability`

### Required

| Field | Type | Meaning |
|-------|------|---------|
| `activity.activity_id` | string | Stable business id |
| `activity.source` | enum | `Schedule C` \| `Schedule F` \| `Partnership` \| `Schedule E` \| `SCorp` |
| `activity.name` | string | Display name |
| `activity.net_income` | number | SE activity net profit (**≤ 0 → not applicable**) |
| `activity.is_se_biz` | boolean | Subject to SE tax |
| `activity.taxpayer_spouse_or_joint` | enum | `taxpayer` \| `spouse` \| `joint` — **who owns this Sch C / SE activity** |

### Recommended

| Field | Default | Meaning |
|-------|---------|---------|
| `activity.ownership_pct` | `100` | Recommend gate (≥ 50) |
| `activity.prefix` | `1` | Instance id |
| `rates.net_earnings_ratio` | `0.9235` | SE factor |
| `activity.net_earnings` | derived | Prefer engine value when known |

### Not required for Part 1

- `reasonable_wage`
- Marginal rates
- W-2 / SS wage-base fields (those matter in Part 2)

### Example

```json
{
  "activity": {
    "activity_id": "schc-1",
    "source": "Schedule C",
    "name": "Consulting LLC",
    "net_income": 120000,
    "is_se_biz": true,
    "ownership_pct": 100,
    "taxpayer_spouse_or_joint": "taxpayer"
  }
}
```

---

## Part 2 — `estimate_scorp_savings`

### Required (in addition to Part 1 activity fields)

| Field | Type | Meaning |
|-------|------|---------|
| `reasonable_wage` | number ≥ 0 | Advisor-confirmed reasonable compensation |
| `activity.taxpayer_spouse_or_joint` | enum | Same as Part 1 — selects whose SS base is used |

### Required for accurate SS / FICA limits (strongly recommended)

| Field | Type | Meaning |
|-------|------|---------|
| `rates.income_already_taxed_by_ss` | number | **That owner’s** W-2 wages already counting toward the SS wage base (`incomeTaxedBySocSec`). |
| `rates.ss_wage_base` | number | Social Security wage base for the tax year (`maxSSwage`) |
| `rates.starting_se_income` | number | **That owner’s** `allSEIncome` (pre `netEarningRatio`) — **all** Sch C / F / partnership SE, not only the converted activity. SPE stacks this with W-2 SS wages to compute `changeInSSIncome` when this activity’s `netEarnings` are removed. |

If `starting_se_income` is omitted, the Tool defaults to this activity’s `net_income` only and will **overstate** SS savings when the owner has other SE businesses.

### Recommended

| Field | Default | Meaning |
|-------|---------|---------|
| `rates.federal_marginal_rate_pct` | `24` | Federal marginal % points |
| `rates.state_marginal_rate_pct` | `0` | State marginal % |
| `rates.nyc_marginal_rate_pct` | `0` | NYC when applicable |
| `rates.net_earnings_ratio` | `0.9235` | SE factor |
| `tax_year` | — | e.g. 2026 |
| `filing_status` | — | MFJ / Single / … |

### Optional

| Field | Meaning |
|-------|---------|
| `rates.ss_rate` / `rates.med_rate` | Employee-only defaults **0.062 / 0.0145** (SPE multiplies each by 2 for EE+ER) |
| `rates.starting_se_income` | Engine all-SE income for that person (advanced) |
| `scenario_id` | project-air scenario id |

### Example (taxpayer Sch C; already has $160k W-2 → little SS headroom)

```json
{
  "activity": {
    "activity_id": "schc-1",
    "source": "Schedule C",
    "name": "Consulting LLC",
    "net_income": 120000,
    "is_se_biz": true,
    "ownership_pct": 100,
    "prefix": 1,
    "taxpayer_spouse_or_joint": "taxpayer"
  },
  "reasonable_wage": 70000,
  "rates": {
    "federal_marginal_rate_pct": 24,
    "state_marginal_rate_pct": 5,
    "ss_wage_base": 176100,
    "income_already_taxed_by_ss": 160000
  },
  "tax_year": 2026,
  "filing_status": "Married Filing Jointly"
}
```

### Example (spouse owns Sch C — use **spouse** W-2 toward SS)

```json
{
  "activity": {
    "activity_id": "schc-spouse-1",
    "source": "Schedule C",
    "name": "Design Studio",
    "net_income": 90000,
    "is_se_biz": true,
    "taxpayer_spouse_or_joint": "spouse"
  },
  "reasonable_wage": 55000,
  "rates": {
    "federal_marginal_rate_pct": 22,
    "ss_wage_base": 176100,
    "income_already_taxed_by_ss": 45000
  }
}
```

---

## What is *not* a Tool input

| Item | Owner |
|------|--------|
| Choosing the wage dollar amount | **Advisor** (required confirm before Part 2) |
| Form 2553 / legal eligibility | Advisor / checklist |
| Prose explanation of JSON | UI or optional LLM |

---

## LLM?

**Core path: no.** Optional only for free-text extraction or narrating Tool output—never for applicability or savings math.
