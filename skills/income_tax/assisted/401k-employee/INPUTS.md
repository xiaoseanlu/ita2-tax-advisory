# 401(k) Employee Contribution — inputs by Skill part

Core Skill is **two Tool calls**. Neither requires an LLM for the math.

Source SPE: `401k Employee Contribution/employee-401k-contribution.spe` +
`common/shared401KLimit_*.spe`.

---

## Part 1 — `assess_401k_employee_applicability`

### Required

| Field | Type | Meaning |
|-------|------|---------|
| `w2.wg_fed_wages` | number | Box 1 wages |
| `w2.wages_401k_contribution` | number | Box 12-D baseline |
| `w2.wg_tp_sp` | int | `0` taxpayer / `1` spouse |
| `filing_status_code` | int | Spouse needs `2` or `5` |
| `retirement.max_401k_contribution_allowed` | number | **Engine** `max401kContributionAllowed` |

### Recommended

| Field | Meaning |
|-------|---------|
| `w2.delete_next_year` | Must be `0` |
| `w2.wages_403b_contribution` / `w2.wg_457b` | Recommend gates (must be 0) |
| `w2.nam_emp` / `w2.prefix` | Display / model path |
| `retirement.combined_401k_limit` | Combined §415 cap |
| `retirement.total_401k` / `total_roth_401k` / `total_403b` / `total_roth_403b` / `baseline_solo401k` | Baseline offsets |
| `retirement.employee_limit_absorbed` / `combined_limit_absorbed` | Cross-strategy absorption |

### Example (SPE unit-test style)

```json
{
  "w2": {
    "wg_tp_sp": 0,
    "nam_emp": "Acme Corp",
    "prefix": 1,
    "wg_fed_wages": 200000,
    "wages_401k_contribution": 0,
    "wages_403b_contribution": 0,
    "wg_457b": 0
  },
  "filing_status_code": 1,
  "retirement": {
    "max_401k_contribution_allowed": 22500,
    "combined_401k_limit": 69000,
    "total_401k": 0
  }
}
```

→ `strategy_change_default = 22500`, `recommended = true`.

---

## Part 2 — `estimate_401k_employee_savings`

Same as Part 1, plus:

| Field | Meaning |
|-------|---------|
| `rates.federal_marginal_rate_pct` | Engine marginal |
| `rates.state_marginal_rate_pct` / `nyc_marginal_rate_pct` | State / NYC |
| `rates.resident_state` | `PA` zeros state/NYC for savings |
| `strategy_change` | Optional advisor override |

### SPE savings anchor

`strategy_change=22500`, `MARGINAL_RATE_TOTAL=33` → savings **7425**, cash outlay **15075**.
