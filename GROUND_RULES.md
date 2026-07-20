# project-air Ground Rules

## Tax Year and Projections

1. **2024 Returns → Base-2026 by default**  
   When a 2024 return is created, we automatically create a 2026 projection by default. It is named **Base-2026**. The Base-2026 scenario uses the same facts as the 2024 return, with the tax year adjusted to 2026.

2. **Strategies apply only to 2026 projections**  
   All strategies (S-Corp Conversion, Bonus Depreciation, etc.) can only be applied to scenarios that are 2026 projections. The Insights button is disabled for 2024 returns and other non-2026 scenarios.

3. **Tax year in scenario schema**  
   Each scenario includes `tax_year`:
   - Parsed from the scenario text (e.g. "Tax year 2024", "2024")
   - Or from the calculated data model (`data_model.tax_situation.tax_year`) after Calculate Tax
   - Used to determine whether strategies are applicable and to drive Base-2026 creation

## Scenario Schema

```javascript
{
  id: string,
  text: string,
  createdAt: string (ISO),
  tax_year?: number,        // 2024 | 2025 | 2026
  displayName?: string,     // e.g. "Base-2026"
  projectionOf?: string,     // scenario id this projection is derived from
  // ... result, data_model, etc.
}
```

## Flow Summary

| Action | Result |
|--------|--------|
| Create new scenario with Tax year 2024 | Scenario saved + Base-2026 created automatically |
| Create new scenario with Tax year 2026 | Scenario saved only (no extra projection) |
| Insights on 2024 scenario | Disabled; message: "Strategies only apply to 2026 projections" |
| Insights on 2026 scenario | Enabled (after Calculate Tax) |
| Add strategy to plan | Allowed only for 2026 scenarios |
