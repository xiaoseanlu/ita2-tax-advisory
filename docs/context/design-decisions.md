# ITA 2.0 — Design Decisions

This document records the key design decisions made in ITA 2.0 and the reasoning behind each. It is intended to prevent relitigating settled decisions and to give new team members the context to understand why the architecture looks the way it does.

---

## Decision 1: Shadow Mode vs. Hard Cutover

**Decision**: ITA 2.0 runs in Shadow Mode alongside ITA 1.0 until it reaches ≥95% accuracy on the benchmark suite vs. actual filed returns. Only then does it become the primary engine.

**What was rejected**: A hard cutover at a fixed date, or a feature-flag-based cutover by use case.

**Why Shadow Mode**

The LLM engine has no accuracy track record at launch. Shadow Mode creates that track record without exposing clients to unvalidated output. The comparison — LLM output vs. ITA 1.0 output vs. filed return — generates the signal needed to improve the engine and proves accuracy to stakeholders before the switchover.

Shadow Mode also enables a more honest conversation about readiness. "We have 94.2% accuracy on 847 benchmark profiles" is a defensible launch condition. "We turned it on and it seems to work" is not.

**The tradeoff**

Running two engines simultaneously doubles the computation cost and operational complexity during the Shadow Mode period. This is the accepted cost of a conservative accuracy ramp.

**Remaining question**: Is 95% the right threshold, or should it be 98%? See [`open-questions.md`](./open-questions.md).

---

## Decision 2: Skill Files vs. Pure LLM

**Decision**: Per-strategy skill files define return signatures and output guardrails. The LLM engine's output is validated against these before it is returned to the caller.

**What was rejected**: Relying entirely on the LLM's internal reasoning to produce consistent outputs, without external validation.

**Why skill files**

LLMs can produce outputs that are internally plausible but mechanically wrong for a specific strategy. The classic failure: an S-Corp election that reduces the advisor's recommended salary below IRS reasonable compensation minimums, or a Roth conversion that is reported as reducing AGI in the conversion year (it doesn't — it increases it).

Skill files catch these failures at the output boundary. They do not constrain the LLM's reasoning about whether a strategy applies or what it saves — they validate that if the LLM says a strategy applies, the computed output is consistent with how that strategy mechanically works.

**Why human-gated updates**

Skill files are the primary defense against systematic errors. If they are updated automatically, a validation loop error could corrupt the guardrails that are supposed to catch errors. Human review of skill file updates is a deliberate safety design.

**The tradeoff**

Human review creates a bottleneck. A skill file update triggered by a tax law change (e.g., bonus depreciation phase-down) requires reviewer availability before it can be deployed. The SLA for this review is an open question.

---

## Decision 3: RAG vs. Baked-In Tax Knowledge

**Decision**: Tax rates, limits, thresholds, and phase-out ranges are stored in a retrieval store and fetched at inference time. The LLM does not need to memorize these values.

**What was rejected**: Fine-tuning the model on tax facts, or including tax rates in the system prompt.

**Why RAG**

Tax law changes annually. If rates and limits are baked into the model (via fine-tuning or static prompt content), the model is wrong the moment tax law changes — and fine-tuning to correct it requires a full training run.

With RAG, a tax year update is a data update. The retrieval store is updated; the model stays the same. The LLM retrieves the 2025 HSA contribution limit at inference time rather than generating it from training data.

**Why not fine-tuning**

Fine-tuning encodes knowledge into weights. It is expensive to update and hard to audit. With RAG, every retrieval is logged — you can verify exactly what rate or limit the LLM used in a given computation. This auditability is important for a regulated product.

**Why not static system prompt**

A system prompt containing all current tax rates and limits would be extremely long and would need to be updated every tax year via a code deploy. RAG is more maintainable and allows the retrieval scope to be extended (e.g., adding state rates, adding ERISA limits) without changes to the system prompt structure.

**The tradeoff**

RAG adds latency (retrieval step before generation) and operational complexity (retrieval store must be maintained and kept current). Both are acceptable given the auditability and maintainability benefits.

---

## Decision 4: Lacerte MCP vs. Building State/Entity Engines Natively

**Decision**: Multi-year projections, state returns, and entity modeling (S-corp, C-corp, partnership) are delegated to Lacerte via MCP integration. ITA 2.0 does not build these computation engines.

**What was rejected**: Building state conformity rules and entity return computation into ITA 2.0 natively.

**Why delegation**

Lacerte is ProConnect's professional tax preparation engine. It already has:
- Full state return computation for all 50 states + DC
- S-corp, C-corp, and partnership entity return computation
- Multi-year carryforward and projection capabilities

Building these natively in ITA 2.0 would mean:
- Duplicating Lacerte's state computation (which is already maintained by a dedicated team)
- Creating a parallel codebase that drifts from Lacerte on state conformity changes
- Solving a problem that is already solved

MCP integration surfaces Lacerte's existing output in the ITA 2.0 context. The advisory layer is in ITA 2.0; the computation layer is in Lacerte.

**The tradeoff**

ITA 2.0's scope is constrained by what Lacerte exposes via MCP. If Lacerte's MCP API doesn't support a particular computation (e.g., a specific state's non-conformity treatment), ITA 2.0 can't surface it. The MCP contract with Lacerte is an open question with timeline uncertainty.

**The principle**

ITA 2.0 stops duplicating what Lacerte already does. The value ITA 2.0 adds is the advisory layer — natural language input, strategy analysis, interaction modeling — not the underlying tax computation that Lacerte already performs.

---

## Decision 5: Validation Feedback Loop Design

**Decision**: The validation loop compares LLM engine output against actual filed returns (the ATE — Actual Tax Engine benchmark), not against ITA 1.0 output. Deltas generate candidate skill file updates that require human approval before deployment.

**What was rejected**:
1. Using ITA 1.0 as the accuracy benchmark
2. Automatic skill file updates without human review

**Why filed returns, not ITA 1.0**

ITA 1.0 has known errors (AMT, strategy isolation). Benchmarking the LLM engine against a known-incorrect baseline would propagate those errors. The ground truth is the actual ProConnect Tax filed return — what a tax professional computed and filed. That is the accuracy target.

**Why human approval on skill file updates**

The validation loop generates candidates — it identifies that the LLM's output on a certain strategy type differs systematically from filed returns. A human (PM or tax expert) reviews:
1. Is the delta a real LLM error, or is it a benchmark profile edge case?
2. Does the proposed skill file update correctly describe the expected output?
3. Are there downstream effects of the update on other strategies?

Automatic updates would allow a systematic loop error to corrupt the guardrails that are supposed to prevent errors. The human gate is the check on the check.

**Why ATE (Actual Tax Engine) as the benchmark name**

"ATE" = Actual Tax Engine. It refers to the actual ProConnect Tax computation on a real or synthetic-but-valid 1040 filing. It is distinct from the DSL engine output, which is an approximation. The distinction matters: the target is professional-grade filed return accuracy, not parity with the DSL.

---

## Decision 6: 1040 Federal First, Not Full Scope

**Decision**: ITA 2.0 v1 scope is 1040 Federal. State returns, entity returns, and multi-year projections are in scope only via Lacerte MCP integration — not as native computation.

**What was rejected**: Attempting to achieve dollar-exact accuracy on state returns and entity returns in parallel with 1040 Federal.

**Why 1040 Federal first**

Dollar-exact accuracy is the bar. States and entities make the accuracy problem orders of magnitude harder:
- 50 state tax codes with non-uniform federal conformity
- Entity returns with multi-step K-1 computation paths
- State + entity combinations that multiply the test matrix

Attempting to achieve accuracy across all of these simultaneously would delay launch indefinitely and make the benchmark suite unmanageable.

1040 Federal is the largest and most valuable use case. It is where the most advisory value is generated. It is also where LLM accuracy is demonstrably achievable within the project timeline.

State and entity complexity is real — it is delegated, not ignored.
