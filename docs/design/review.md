# Design review and merge log

| | |
|---|---|
| **Date** | 2026-10-17 |
| **Inputs** | `rag-claude.md` (rev 3) and `rag-gpt.md`. Both are removed from the tree and remain in git history at `e1212a1`. |
| **Output** | [design.md](design.md) (current rev 5; original merged baseline rev 4), checked against [requirements.md](../req/requirements.md) |

## 1. Assessment of the inputs

**rag-claude.md** was the stronger domain design. It had a concrete ontology, a working predicate DSL with three-valued logic, a computation feature catalogue, topic maps and a phase plan aligned to the requirement IDs. Its weaknesses:

- It linked to a companion document that does not exist (`astrology-knowledge-and-retrieval.md`, cited as "companion §3/§4.1/§11").
- It sent traces to LangSmith cloud and kept birth data in an unencrypted LangGraph store, which contradicts NFR-6.
- It scheduled licence filtering and PII redaction for phase 8, although both are M requirements in phases 1–2.
- It relaxed the bhava filter when results were thin, which reintroduces the factor confusion RET-3 forbids.
- It recorded a cancelled yoga as plain `not_satisfied`, losing the formation result APP-3 requires.
- It carried about 400 lines of library glue code that will rot with library versions.

**rag-gpt.md** was the stronger engineering-rigour design. It had partial/failed states, coverage checklists, context assembly that never drops an exception, replayable rule decisions, half-open UTC intervals, panchanga formulas and a sound transit solver approach. Its weaknesses:

- Much of it was a generic enterprise RAG template: `tenant_id`, `access_groups: ["employees"]`, a permission-restricted eval set, "outdated sources".
- It proposed Haystack + PostgreSQL + object storage + a transactional outbox + release manifests + revocation overlays for a single-operator local tool.
- It designed chart-image layout adapters.
- It deferred every quantitative target and most technology decisions ("open design inputs").

## 2. Conflicts and the call made

| # | Conflict | rag-claude | rag-gpt | Decision (design §) | Why |
|---|---|---|---|---|---|
| C1 | Framework | LangChain / LangGraph / LangSmith | Haystack (LangGraph "if justified") | LangGraph for orchestration, direct `qdrant-client` for search, `langchain` only for model routing (D1) | Operator's stated stack; the hard parts are framework-independent; a bake-off is a rabbit hole. |
| C2 | Curated knowledge store | YAML in git | PostgreSQL tables | YAML in git (D2) | Thousands of records; review needs diffs; git gives versions and rollback. |
| C3 | Private data | LangGraph store (unencrypted) | PostgreSQL with tenant ACLs | SQLCipher SQLite, key in Keychain (D3, §16.1) | NFR-6 encryption; no tenants (requirements §2.2). |
| C4 | Release consistency | Qdrant alias | Release manifest + outbox + in-flight pinning + deny overlay | Alias resolved once per run; side-by-side rebuild (D5, §5.4) | Same guarantee for a single operator at a fraction of the machinery. |
| C5 | Agent shape | Open agent + fixed workflows + per-method analysts + checker | "One orchestrating agent with bounded tools" | Fixed workflow for chart routes; one LLM call per method; deterministic + LLM checker; agent only as fallback for concept/story (D7, §13) | Free agents skip factors; rag-gpt's own "workflow roles" section converges on the same shape. |
| C6 | Cancellation semantics | Cancelled → `not_satisfied` | Formation kept separate | Formation, qualification and applicability all recorded (§10.3, Appendix A) | APP-3. |
| C7 | Chart input | Birth data | Birth data + images + structured imports in Core | Birth data; structured import phase 7; no images (D12) | Requirements R1. |
| C8 | Calculation engine | pyswisseph; "evaluate PyJHora on top" | "Engine selection open" | Own layer on pyswisseph; PyJHora and JHora exports as test oracles only (D6) | Control of conventions; no runtime licence entanglement. |
| C9 | LLM default | API (Claude Sonnet) default | Local first | Two privacy modes with per-role models; birth data never leaves the machine; reference deployment uses `api` for analyst/synthesizer (D9, §15) | NFR-5 and NFR-6 both hold; NFR-3 is measurable. |
| C10 | Ingestion idempotency | LangChain `index()` + RecordManager | Hashes + publication markers | Deterministic point IDs from printed locators + ingest table (D10, §9.8) | Fewer dependencies; IDs stable across re-indexing (ING-9). |
| C11 | Tracing | LangSmith on | "Controlled sensitive logging" | Run traces in the encrypted DB; external tracing off by default, metadata-only in `api` mode (D11, §18) | NFR-6. |
| C12 | Birth-time uncertainty | Boundary distance | Full-interval propagation | Exact boundary solving for a named fact list; monotonic quantities need no sampling (§7.9) | Requirements R2; exact and cheap. |
| C13 | Sunrise default | Disc centre with refraction | Unspecified | `hindu_rising` (disc centre, no refraction), a profile setting checked against JHora fixtures (§7.1) | Traditional convention, directly supported by Swiss Ephemeris. |
| C14 | Evaluation targets | "At target" per phase | Deferred to an acceptance profile | Targets recorded per phase in `evals/targets/phase-N.yaml` (§19.4) | Requirements §7 phase exit. |
| C15 | Concept route | Open agent | Bounded agent | Deterministic single pass; agent only on insufficient coverage (§4.2, §13.2) | 8 s p95 (NFR-3) and reproducibility. |

## 3. Defects found in review and fixed

Found while merging, and in three review passes over the merged draft.

| # | Defect | Fix |
|---|---|---|
| F1 | Dangling "companion doc" references (rag-claude) | Content written in place (§7.4, §14) |
| F2 | Personal data in cloud traces and an unencrypted session store | §16.1, §18, D11; checkpointer risk recorded (§23) |
| F3 | Licence filtering and PII redaction scheduled late (rag-claude phase 8) | Phases 1–2 (§20) |
| F4 | Filter relaxation crossed factor boundaries | Defining vs secondary filters; `insufficient` instead (§12.3) |
| F5 | Enterprise-template fields (`tenant_id`, `access_groups`) | Removed |
| F6 | Free-text questions could leak birth details to an API planner | Local PII scrubber + payload guard (§6.4, §15.2) |
| F7 | Plain-hash chart IDs are reversible by brute force (small input space) | HMAC with the private key (§5.3) |
| F8 | Draft design cited a specific BPHS verse locator from memory | Replaced by `<edition:locator>` placeholders; CI requires real sources (§8) |
| F9 | Normative sketch did not evaluate linked cancellation cards and never updated its cycle set | Rewritten and exercised on cycle, unknown, cancelled and Kleene cases (Appendix A) |
| F10 | Contrary search filtered passages on `polarity`, a field passages do not have | Polarity taken from rule cards; passages via links (§12.5) |
| F11 | `reference_frame = lagna` filter would exclude classical verses that never state a frame | Tagger default: houses without a reference point are Lagna-based (§9.6) |
| F12 | DST gap vs fold detection was order-dependent and would misreport gaps as folds | Round-trip check first, then fold comparison (§6.2) |
| F13 | Local `num_ctx` (16k) smaller than the per-method context budget (24k) | Budgets per mode; `num_ctx` 32k; start-up check (§12.8, §15.3) |
| F14 | Concept route latency (agent loop + planner) exceeded the 8 s p95 target | Deterministic first pass (§4.2, §15.4) |
| F15 | Fact cache described as keyed on the knowledge release | Facts don't depend on sources; bundles carry the release (§5.4) |
| F16 | No behaviour for polar day/night sunrise, villages missing from the gazetteer, or a minute-precision default | §7.4, §6.2, §6.3 |
| F17 | Historical Indian time standards (Bombay and Calcutta time) not handled; IANA does not model them | Original pre-1956 prompt superseded on 2026-10-18: resolve documented/library time standards and clarify only specific uncertainty (§6.2). |
| F18 | TRN-1 (transit positions at the as-of date) had no design element | §7.8 |
| F19 | Rule-card review effort was never estimated (~1,100–1,400 cards, 90–120 reviewer-hours) | Topic-ordered review; `partial` instead of drafts (§10.7); requirement KNW-5 phases aligned to 3–6 |
| F20 | API VLM fallback could send licensed scans off-machine | Only when the register entry permits external processing (§9.3) |
| F21 | Sizing assumed 1M chunks; the Core corpus is ~20k | §23 |

## 4. Rabbit holes removed

Design §21 lists them with what replaces each. The main ones:

| Rabbit hole | Source |
|---|---|
| Framework bake-off (LlamaIndex / Haystack / LangChain / LangGraph) | rag-gpt |
| PostgreSQL + object store + outbox + release manifests + revocation overlays + backup tombstones | rag-gpt |
| Chart-image layout adapters | rag-gpt |
| HTTP API with idempotency keys and stored-run endpoints | rag-gpt |
| GraphRAG / graph database | both, as options |
| JPL Horizons cross-validation | rag-gpt |
| Multi-vector LLM summaries of number tables | rag-claude |
| ~400 lines of version-sensitive library code in the design | rag-claude |
| Sub-sub-sub dasha levels (SD/PrD) | rag-claude |
| Bulk rule extraction without a review budget | both |

## 5. Memory requirements

[memory.md](../req/memory.md) (rev 4) appeared while this merge was in progress. It is covered by a new design §17, which replaces the old "LangGraph store" paragraph:

- M1–M8 mapped to concrete stores (encrypted SQLite tables and LangGraph checkpoints).
- Deterministic person-reference resolution.
- A `SessionSlots` model with a pure, tested `carry_forward` function.
- `needs_input` suspension via LangGraph `interrupt()`, with a deterministic test of whether the next message answers it.
- Reading records that no retrieval route or bundle field can reach.
- Enumerated preferences with refusal rules.
- Proposal-and-confirm writes.
- Deletion that unlinks traces.
- Pseudonyms in `api` mode.

A first version of §17 was written against memory.md rev 2. It was revised for rev 4: consent required only for compatibility, unsaved persons kept for the session, MEM-PER-7, a current-location slot, chart scope kept on the same topic, no health notes, and trace unlinking instead of deletion.

## 6. Requirements coverage

All 192 requirement IDs (149 in requirements.md, 43 in memory.md) are mapped in design §22 to a design section and a verification. The check is mechanical: a script extracts every ID from both requirement documents and confirms it appears in the §22 table, either directly or within a range. C-priority items are mapped explicitly as "not planned".

Interpretations worth a reviewer's eye:

- **NFR-8** ("run the evaluation suite on every change"): the deterministic layers run on every change; LLM-graded layers run before merge to `main`, for cost reasons (§19.4).
- **NFR-3:** the targets apply to `api` mode on the reference deployment; `local` mode latency is measured but not gated (§4.3).
- **OUT-1** ("cite a chart fact and a passage"): applied to chart claims; concept and story answers cite sources only (§14.4).

One requirement was changed as a result of design review: **KNW-5** now spans phases 3–6, with topic-ordered review (F19).

## Input-scope revision — 2026-10-18

At the user's request, removed the fixed birth-year range, country preference in place lookup, blanket historical-year prompt, and categorical non-Gregorian input exclusion. Accept worldwide names/coordinates and original calendar labels; use maintained conversion libraries or documented converted inputs. Do not build bespoke geographic, historical-time or calendar research systems as a prerequisite. Keep invalid-input checks, explicit assumptions, and actual per-feature engine/data/domain limits. Unsupported calculations do not block unrelated knowledge retrieval. No changes to the selected astrological methods or their release phases.
