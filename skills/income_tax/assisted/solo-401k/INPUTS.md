# Solo 401(k) — inputs by Skill part

Core Skill is **two Tool calls**. Neither requires an LLM.

Source SPE: `Solo 401k Contribution/Solo401k.spe` + `common/shared401KLimit_*.spe`.

---

## Part 1 — `assess_solo401k_applicability`

### Required

| Field | Type | Meaning |
|-------|------|---------|
| `person.taxpayer_spouse_or_joint` | enum | `taxpayer` \| `spouse` |
| `person.filing_status_code` | int | SPE codes; spouse needs `2` or `5` |
| `person.all_se_income` | number | `allSEIncome` |
| `person.earned_income` | number | `earnedIncome` |
| `person.biz_exists_without_wages` | boolean | SPE Gate B (no wages Sch C/F/pship, or S-Corp+W-2) |
| `retirement.max_solo401k_contribution_allowed` | number | **Engine** `maxSolo401kContributionAllowed` |

### Recommended

| Field | Meaning |
|-------|---------|
| `person.sep_ira` | Blocks recommend if > 0 and no existing solo deferral |
| `person.solo_elective_deferral` | Projection `tpSEElectDef` / `spsEElectDef` |
| `person.solo401k_contribution` / `solo401k_catchup` | ITA summary baseline |
| `retirement.total_401k` / `total_roth_401k` / `total_403b` / `total_roth_403b` / `baseline_solo401k` | Shared limit offsets |
| `retirement.combined_401k_limit` | Combined annual cap |
| `retirement.employee_limit_absorbed` / `combined_limit_absorbed` | Cross-strategy absorption |

### Example (spouse, unit-test style)

```json
{
  "person": {
    "taxpayer_spouse_or_joint": "spouse",
    "filing_status_code": 2,
    "all_se_income": 100000,
    "earned_income": 100000,
    "sep_ira": 0,
    "biz_exists_without_wages": true
  },
  "retirement": {
    "max_solo401k_contribution_allowed": 27000,
    "combined_401k_limit": 69000
  }
}
```

---

## Part 2 — `estimate_solo401k_savings`

### Required (in addition to Part 1)

| Field | Type | Meaning |
|-------|------|---------|
| `rates.federal_marginal_rate_pct` | number | From return summary |
| `strategy_change` | number \| omit | Advisor override; omit → SPE default = headroom |

### Recommended

| Field | Meaning |
|-------|---------|
| `rates.state_marginal_rate_pct` / `nyc_marginal_rate_pct` | Added into total (zeroed if PA) |
| `rates.resident_state` | `PA` → non-conforming for added-scope savings |

### Example

```json
{
  "person": {
    "taxpayer_spouse_or_joint": "spouse",
    "filing_status_code": 2,
    "all_se_income": 100000,
    "earned_income": 100000,
    "biz_exists_without_wages": true,
    "solo401k_contribution": 0,
    "solo401k_catchup": 0
  },
  "retirement": {
    "max_solo401k_contribution_allowed": 27000,
    "combined_401k_limit": 69000
  },
  "rates": {
    "federal_marginal_rate_pct": 37,
    "state_marginal_rate_pct": 12.3,
    "resident_state": "CA"
  }
}
```

Expected: `strategy_change` 27000 → savings **13311**, cash outlay **13689**.
