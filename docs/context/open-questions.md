# ITA 2.0 — Open Questions

These are the questions and decisions that remain unresolved as of the current PRD. Each entry includes what the question is, why it's open, and what it would take to close it.

Last reviewed: May 2026

---

## 1. Shadow Mode Accuracy Threshold: 95% or 98%?

**The question**: Is ≥95% accuracy vs. filed returns the right bar for Shadow Mode graduation, or should it be ≥98%?

**Why it's open**: The 95% threshold was set as an initial target based on engineering feasibility estimates. No formal analysis has been done on what accuracy level is required for client-safe output. In a tax advisory context, a 5% error rate means 1 in 20 tax plans has a meaningful error — that may be too high for a product used in a professional workflow.

**What's at stake**: A higher threshold (98%) delays launch. A lower threshold (95%) launches sooner but may expose clients to more errors than is acceptable. The right answer depends on:
- What error distribution looks like at 95% vs. 98% (are errors random or clustered in certain strategy types?)
- What the cost of a client-facing error is (reputational, financial, regulatory)
- Whether the human review and validation loop can catch errors in production before they cause harm

**What would close it**: A risk analysis from compliance/legal on acceptable error rates, combined with a distribution analysis of where errors occur in the benchmark suite.

**Owner**: TBD — needs legal/compliance + PM alignment.

---

## 2. Skill File Ownership: PM vs. Engineering

**The question**: Who owns skill files? Who can propose updates? Who approves them?

**Why it's open**: Skill files sit at the intersection of tax knowledge (domain) and system behavior (engineering). A PM or tax expert has the knowledge to identify when an output shape is wrong; an engineer has the knowledge to write the guardrail assertion correctly. Neither can do it alone.

**What's at stake**: If skill file updates require engineering review, the update cycle is slow — any tax law change that affects a strategy's output shape requires an engineering ticket. If skill files are PM-owned, PMs need enough technical literacy to write and review guardrail assertions (or a tooling layer is needed to abstract this).

**What would close it**: A RACI for skill file updates, agreed by PM and Engineering leads. This likely requires a tool for PM-facing skill file editing that doesn't require writing raw assertion logic.

**Owner**: PM + Engineering lead alignment needed.

---

## 3. MCP Contract with Lacerte: Timeline and API Surface

**The question**: What will the Lacerte MCP API expose? When will it be available? What is the contract for multi-year projections, state returns, and entity modeling?

**Why it's open**: The MCP integration is a dependency on the Lacerte engineering team. As of the current PRD, the API surface has not been defined and the timeline has not been committed. Without this, ITA 2.0's state and entity use cases (UC-3, UC-9, UC-13 in multi-year/multi-state configurations) are blocked.

**What's at stake**: If the Lacerte MCP contract slips, ITA 2.0 launch scope narrows to 1040 Federal single-year only. That is still valuable — but it limits the use cases that can be delivered in the 2027 milestone.

**What would close it**: A formal API surface agreement with the Lacerte team, including: what endpoints are available, what inputs they accept, what outputs they return, and what the SLA is for the integration.

**Owner**: ITA 2.0 PM + Lacerte Engineering PM — escalation needed to get this on a roadmap.

---

## 4. State Conformity Scope: What Do SALT and Multi-State Filers Get?

**The question**: For clients with significant state tax exposure (e.g., California + New York multi-state filers, SALT-capped high earners), what does ITA 2.0 deliver in v1?

**Why it's open**: The design decision to delegate state computation to Lacerte MCP answers the "how" but doesn't define the "what" for clients. A PTG firm in California has clients for whom state tax is often larger than federal tax. If ITA 2.0 v1 only gives them federal advisory, the product is incomplete for a significant portion of their book.

**What's at stake**: Client segment coverage. If multi-state filers and SALT-capped clients are not served in v1, the advisory penetration metric improvement will be lower than projected. This may be acceptable as a phased approach, but it needs to be a deliberate decision communicated to the field.

**What would close it**: A clear v1 state scope statement (e.g., "1040 Federal only; state advisory available via Lacerte integration in v1.5"), agreed by PM and communicated in launch materials.

**Owner**: PM — decision, not a dependency.

---

## 5. QBL Surface Integration: Separate Product Team Coordination

**The question**: How does ITA 2.0 integrate with the QuickBooks Live / TurboTax Live product surface? Who owns the integration? What is the coordination model between the QBL product team and the ITA 2.0 team?

**Why it's open**: QBL is a separate product organization. The QBL use cases (UC-Q1 through UC-Q5) require integration with the QBL product surface — not just the ITA 2.0 backend. The coordination model between the two teams has not been defined.

**What's at stake**: Without coordination, QBL use cases will be designed in isolation and may not be implementable on the QBL surface without rework. The natural language intake (UC-Q1) and session save/retrieve (UC-Q4) in particular require QBL product changes that the ITA 2.0 team cannot make unilaterally.

**What would close it**: A shared product brief with the QBL PM team, defining: which use cases are in scope for which product surface, who owns the UX, and what the shared component/API boundary is.

**Owner**: ITA 2.0 PM + QBL PM — joint planning session needed.

---

## 6. Benchmark Suite Composition: Ownership and Privacy Review

**The question**: Who owns the 1040 benchmark profiles? How are they created? What is the legal/privacy review process for using real or synthetic tax return data in testing?

**Why it's open**: The benchmark suite is the single most important artifact for proving Shadow Mode accuracy. It needs to be diverse (all filing statuses, income types, strategies), realistic, and legally compliant. Using real client returns without consent is not permissible. Synthetic profiles need to be realistic enough to test actual edge cases.

**What's at stake**: If the benchmark suite is thin or unrepresentative, the 95% accuracy threshold means less. A benchmark that only covers simple W-2 returns does not prove accuracy on QSBS, IRMAA, AMT, or passive activity loss scenarios.

**What would close it**: A benchmark suite design doc defining: profile count, filing status distribution, income type distribution, strategy coverage, synthetic data generation process, and legal/privacy sign-off.

**Owner**: PM (design), Engineering (synthetic data generation), Legal (privacy review).

---

## 7. Human Approval Gate for Skill File Updates: SLA and Reviewer Identity

**The question**: When the validation loop generates a candidate skill file update, how long does approval take? Who is the reviewer?

**Why it's open**: The human approval gate is a deliberate safety design — automatic updates to skill files are not allowed. But the gate is only useful if it doesn't create an indefinite bottleneck. A tax law change that affects strategy output shapes needs to be reflected in skill files before the next filing season.

**What's at stake**: If the SLA is undefined, a skill file update triggered by a tax law change in December could still be in review in January — during peak filing season. If the reviewer identity is undefined, there is no one to escalate to when a review is blocked.

**What would close it**: A documented approval process: who reviews (PM, tax expert, or both), what the SLA is (e.g., 5 business days for non-urgent, 24 hours for tax-law-triggered), and what the escalation path is if the reviewer is unavailable.

**Owner**: PM + Tax Expert lead — operational design needed.

---

## Summary Table

| # | Question | Blocker or Risk? | Owner |
|---|---|---|---|
| 1 | Shadow Mode threshold: 95% vs. 98%? | Risk — may delay or change launch conditions | PM + Legal/Compliance |
| 2 | Skill file ownership: PM vs. Engineering | Risk — update velocity and quality | PM + Engineering lead |
| 3 | Lacerte MCP API surface and timeline | Blocker for state/entity use cases | ITA PM + Lacerte PM |
| 4 | State conformity scope for SALT/multi-state filers | Risk — client segment coverage in v1 | PM (decision) |
| 5 | QBL surface integration coordination model | Blocker for QBL use cases | ITA PM + QBL PM |
| 6 | Benchmark suite ownership and privacy review | Blocker for Shadow Mode launch | PM + Engineering + Legal |
| 7 | Skill file approval gate SLA and reviewer identity | Risk — tax law change velocity | PM + Tax Expert lead |
