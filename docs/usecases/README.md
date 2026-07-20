# Tax advisory chat — use cases & design

Persistent chat (planned: **OpenAI Responses API**) on top of the existing flow: tax situation, first calculation output, applied strategies, early savings, advanced (calculator) savings, and navigation between chat and the strategies UI.

**In scope in this document:** UC-1 through UC-7.  
**Deferred:** UC-8 (contradiction / trust), UC-9 (support / export), UC-10 (returning session / multi-device). We will add those later.

Update the **Implemented** column as features ship (`No` → `Yes` or a short note).

---

## Use cases

| UC | Name | Actor | Flow | Expect | Memory / state | Implemented |
|----|------|--------|------|--------|----------------|-------------|
| **UC-1** | Explainer after a run | Customer after first calculation | User asks e.g. “Why is my NIIT this high?” or “Walk me through the brackets you used.” | Answer uses **current scenario + last calculation text + reference rules**; no strategy change. | Store that this explanation happened; optional short “user cares about NIIT” (or similar) if you add personalization later. | No |
| **UC-2** | Strategy discovery in chat | Customer | User asks e.g. “What can reduce my taxes if I max 401(k)?” | Assistant reasons from **scenario + applied strategies + savings summaries**; may suggest opening the strategies UI or applying a known strategy. | Conversation thread; optional durable structured intent (e.g. interest in retirement deferrals). | No |
| **UC-3** | Apply strategy from chat | Customer | User says e.g. “Apply the S-Corp strategy” or “Turn on Section 179 for that equipment.” | Backend validates intent → **same mutations as the UI** (apply strategy, re-run pipeline) → chat shows **updated** early/advanced savings and calculation context. | Persist “strategy X applied at T” in **session state**, not only in chat prose. | No |
| **UC-4** | Apply strategy from UI, continue in chat | Customer | User toggles a strategy in the UI, sees new savings, returns to chat: “Was that worth it?” | Chat sees the **new baseline** (post-UI change) without the user pasting numbers. | Single source of truth: **application state** drives what is injected into the model context each turn. | No |
| **UC-5** | Correct the scenario via chat | Customer | User says e.g. “Actually my wages are $195k, not $200k.” | System updates **tax situation** (or asks confirmation), may trigger **recalc**; chat and UI reflect the update. | **Scenario version** increments; prior assistant statements about old figures are superseded via instructions + fresh snapshot. | **Partial:** Assistant drawer + inline card editor update scenario text; `scenario_version` increments when text changes; user runs **Calculate Tax** to recalc. Natural-language correction via Responses API is not wired yet. |
| **UC-6** | Add to memory explicitly | Power user / any customer | User says e.g. “Remember that I’m planning to sell the rental in 2027” or “Save this: my CPA wants conservative estimates.” | That content is stored as **durable user memory** (not only buried in the transcript) and included where appropriate in later turns. | Distinct bucket: **user-authored long-term notes** vs raw transcript. | **Yes:** `POST /api/memory`; Assistant panel **Remember** button; items stored in `chat_memory_store` (per `scenario_id`). |
| **UC-7** | Remove from memory explicitly | Customer correcting mistakes | User says e.g. “Forget the rental sale note” or “Remove anything about 401(k) from what you remember.” | Targeted delete or list-and-confirm removal; future replies **must not** use removed facts. | **Addressable memory items** (stable ids), not one opaque blob. | **Yes:** `DELETE /api/memory?scenario_id=&memory_id=`; **Remove** per row in Assistant panel. |

---

## Deferred use cases (not in initial implementation pass)

| UC | Name | Summary |
|----|------|---------|
| **UC-8** | Contradiction and trust | User or UI contradicts earlier chat; assistant follows **authoritative app state** and may acknowledge correction. |
| **UC-9** | Support / handoff | Export or summarize for a CPA; privacy-aware. |
| **UC-10** | Session lifecycle | Return days later; reload chat + memory; merge policy when server state changed elsewhere. |

---

## Design considerations

### A. Three layers of memory

| Layer | What it is | Why |
|--------|------------|-----|
| **Session / app state** | Tax situation, calc outputs, strategies, savings widgets | Ground truth; inject a fresh snapshot into the model each request. |
| **Conversation** | Chat turns (Responses API thread and/or your own store) | UX continuity; may be trimmed or summarized for length. |
| **Durable user memory** | Explicit add/remove notes (UC-6 / UC-7) | Must be **itemized** (id, text, created_at) so removal and audits work. |

Avoid collapsing these into a single unstructured string—add/remove memory becomes unreliable.

### B. OpenAI Responses API

- Use the **Responses API** for turn-by-turn chat and (later) tools such as “apply_strategy.”
- **Do not** treat the API as the sole holder of tax-domain truth: the backend should **assemble each request** from a compact **state snapshot** + optional **memory items** + **recent transcript** (or a conversation id, depending on how you persist).
- Decide early: **where** conversation persistence lives (fully on OpenAI vs **your DB**). Many products store messages in **Postgres** (or similar) and pass a **window + summary** into Responses for control, portability, and compliance.

### C. Prompt / context assembly

Each request can include:

1. **System / developer instructions** — role, compliance, and a rule that **the structured snapshot below overrides prior chat** when they conflict.
2. **Structured snapshot** — scenario id/version, applied strategy ids, last calculation summary, early vs advanced savings as **data**, not only prose.
3. **User memory list** — durable notes (with internal ids; optionally show labels to the user when listing for removal).
4. **Recent messages** or a **rolling summary** of older thread if context limits are tight.

### D. Add vs remove memory

- **Add:** append a new memory row; optional **deduplication** (embeddings or a small LLM pass) to limit near-duplicate notes.
- **Remove:** delete by **id**; if the user’s wording is vague (“forget the rental”), use **clarification** (“I have: (1) … (2) … which one?”) or **soft-delete** with audit.

### E. UI and chat parity

- Actions in **chat** should call the **same backend services** as the **strategies UI** (one pipeline).
- After UI changes, emit an internal **state_updated** event (or rely on the next request) so the **snapshot** for chat always matches the latest UI without a full reload.

### F. Safety and product

- Tax advice disclaimers; **minimize** storing sensitive identifiers in chat memory when possible.
- **PII** handling in logs and analytics (redaction).

### G. Observability

- Log **snapshot version** and **memory item ids** included per request to debug “why did it say that?”

---

## Implementation notes

- **UC-5 / UC-6 / UC-7 (current):**
  - **`chat_memory_store.py`** — in-process memory list per `scenario_id` (resets on server restart; same pattern as `plan_store`).
  - **REST:** `GET /api/memory?scenario_id=`, `POST /api/memory` `{ scenario_id, text }`, `DELETE /api/memory?scenario_id=&memory_id=`.
  - **UI:** Header **Assistant** opens a drawer: scenario text (UC-5), memory list + add/remove (UC-6 / UC-7).
  - **Scenario version:** `scenario_version` on each scenario object increments when description text changes (card inline edit, modal save, Assistant **Apply**); prior LLM results are cleared until **Calculate Tax** runs again.
- **OpenAI Responses API:** keys, conversation id strategy, and tool definitions — next; inject `GET /api/memory` items + scenario snapshot into prompts when chat ships.
- **Persistence:** For production, replace in-memory stores with DB-backed `chat_sessions`, `chat_messages`, `user_memory_items` linked to plan/session ids.

---

## Changelog

| Date | Change |
|------|--------|
| (initial) | UC-1–UC-7, design considerations, deferred UC-8–UC-10 |
| — | UC-5 partial + UC-6 + UC-7: `chat_memory_store`, `/api/memory`, Assistant drawer, `scenario_version` |
