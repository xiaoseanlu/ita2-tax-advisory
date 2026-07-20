# ITA 2.0 — Personas

Five personas. Three are professional tax practitioners (PTG channel); two are within Intuit's assisted and consumer products (QBL/TurboTax channel).

---

## Persona 1: Independent Pro / Non-PTG Accountant

**Who they are**
Independent tax professionals using ProConnect Tax or Lacerte. High expertise, high client volume, price-sensitive. They do not work inside a large firm — they are the firm. Advisory is their primary competitive differentiator against both larger firms and DIY tax software.

**What they need from ITA 2.0**
- Accurate computation they can stand behind with clients — dollar-exact, defensible output
- Strategy analysis across multiple scenarios without manual spreadsheet work
- Fast input: they know their clients deeply and should not have to re-enter data they already have in ProConnect
- Multi-year projections to advise on Roth conversion ladders, depreciation elections, and entity comparisons over time
- Entity modeling (sole prop vs. S-corp vs. C-corp) — this is a core use case for their small business clients

**Pain points with ITA 1.0**
- 415 input fields, many of which don't map to how they think about a client's situation
- No strategy interaction modeling — each strategy evaluated in isolation
- Can't run multi-year projections
- Known AMT errors undermine trust

**Use cases**
UC-1 through UC-13 (all PTG use cases)

Primary use cases: UC-1 (S-Corp election), UC-2 (retirement account selection), UC-3 (Roth conversion), UC-4 (depreciation strategy), UC-9 (entity comparison), UC-12 (QSBS), UC-13 (1031/OZ)

---

## Persona 2: Intuit Expert (QBL / TTL Assisted)

**Who they are**
Intuit-employed tax experts working in QuickBooks Live or TurboTax Live Assisted. They serve a high volume of clients through the Intuit platform — not independent practitioners. They operate within a structured product workflow, not their own toolchain.

**What they need from ITA 2.0**
- Advisory tools that work within the QBL/TTL assisted workflow — not a separate product they switch to
- Natural language intake that replaces rigid form entry
- The ability to update projections mid-conversation as client facts change
- Clean, plain-language output they can read back to a client or share as a summary
- Session persistence — client conversations need to be saved and resumed across appointments

**Pain points with ITA 1.0**
- ITA 1.0 is a PTG product; QBL experts don't have a comparable tool
- Form-based intake doesn't match how a conversation with a client works
- No session continuity

**Use cases**
UC-Q1 (natural language intake), UC-Q2 (context mutation), UC-Q3 (client summary generation), UC-Q4 (session save/retrieve), UC-Q5 (PDF intake)

---

## Persona 3: Intuit Small Business (QBO)

**Who they are**
Small business owners or their accountants using QuickBooks Online. Tax advisory is not their primary job — they are running a business. They engage with tax planning episodically, often triggered by a QBO event (large expense, payroll milestone, end-of-quarter review).

**What they need from ITA 2.0**
- Tax advice that connects to what they already see in QuickBooks — revenue, expenses, payroll
- Simple, actionable answers: "Should I set up an S-corp?" "How much should I put into a SEP-IRA?"
- Entity comparison in plain language
- Retirement contribution optimization based on their actual P&L

**Pain points today**
- Tax advisory requires a separate appointment with an accountant — it's not integrated into their QBO workflow
- Complex inputs they don't understand

**Use cases**
UC-1 (S-Corp election), UC-2 (retirement accounts), UC-9 (entity comparison)
QBL use cases when assisted by an Intuit Expert: UC-Q1, UC-Q3

---

## Persona 4: Intuit TurboTax (Consumer)

**Who they are**
DIY filers using TurboTax. Lower tax complexity on average, high volume. Guided experience; they expect the software to lead them. Advisory needs are simpler: "Am I getting all my deductions?" "Should I contribute more to my 401(k)?"

**What they need from ITA 2.0**
- Light advisory integrated into the filing flow — not a separate product
- Validation and encouragement: "You're on track" or "You may be missing X"
- Simple projection: "If you contributed $X more, your tax bill would decrease by $Y"

**Pain points today**
- TurboTax has under 30 inputs for planning — advisory is shallow
- No multi-year view

**Use cases**
Limited overlap with ITA 2.0 PTG use cases. Most relevant for future phases.
Near-term: UC-Q1 (natural language intake in an assisted context), UC-Q3 (plain language summary)

---

## Persona 5: External (e.g. Robinhood User)

**Who they are**
Users of fintech partners — brokerage platforms, robo-advisors, wealth apps — who have tax-relevant data but no tax advisory product. The canonical example is a Robinhood user who has complex capital gains and tax-lot data but has not engaged a tax professional.

**What they need from ITA 2.0**
- Tax-lot optimization: which lots to sell, when, to minimize capital gains tax
- Year-end harvesting analysis: realized/unrealized gains, wash sale awareness
- Capital gains bracket management: how much room is in the 0% long-term capital gains bracket?
- 1099-B intake and analysis

**Pain points today**
- No advisory product in their workflow at all
- Tax consequences are an afterthought at time of transaction

**Use cases**
Not directly mapped to the 13 PTG use cases in ITA 2.0 v1. This persona is a future-phase integration target. The most relevant ITA 2.0 capability is the LLM engine's natural language input model and the RAG store's capital gains rate data.

---

## Persona-to-Use-Case Matrix

| Use Case | Independent Pro | Intuit Expert | QBO SMB | TurboTax | External |
|---|:---:|:---:|:---:|:---:|:---:|
| UC-1: S-Corp election | X | | X | | |
| UC-2: Retirement account selection | X | | X | | |
| UC-3: Roth conversion ladder | X | | | | |
| UC-4: Depreciation strategy | X | | | | |
| UC-5: Home office deduction | X | | X | | |
| UC-6: Backdoor Roth IRA | X | | | | |
| UC-7: IRMAA cliff avoidance | X | | | | |
| UC-8: Passive activity loss | X | | | | |
| UC-9: Entity comparison | X | | X | | |
| UC-10: NOL carryforward | X | | | | |
| UC-11: Charitable giving | X | | | | |
| UC-12: QSBS exclusion | X | | | | |
| UC-13: 1031 / Opportunity Zone | X | | | | |
| UC-Q1: Natural language intake | | X | X | X | |
| UC-Q2: Context mutation | | X | | | |
| UC-Q3: Client summary | | X | X | X | |
| UC-Q4: Session save/retrieve | | X | | | |
| UC-Q5: PDF intake | | X | | | |
