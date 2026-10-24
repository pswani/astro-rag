# Jyotish Agentic RAG — Memory Requirements

| | |
|---|---|
| **Status** | Draft (rev 4, reviewed) |
| **Date** | 2026-10-17 |
| **Extends** | [requirements.md](requirements.md) (rev 2). Refines AGT-5, AGT-6, QRY-6, NFR-2, NFR-6 |
| **Deployment** | As baseline §2.2: local, single operator, several stored persons (self, family, clients); API and CLI |

This document says **what the application must remember, for how long, and under which rules**. Storage products, schemas and the agent graph are design decisions. Priorities (M/S/C), phases and tiers follow the baseline.

## 1. Terms

| Term | Meaning |
|---|---|
| **Operator** | The one person running the system (baseline §2.2). |
| **Person** | Someone whose birth data is stored: the operator's **self** record, family members, clients. |
| **Native** | The person a question is about. |
| **Session** | A conversation thread identified by a session ID supplied by the API/CLI caller. A request with no session ID is stateless. |
| **Reading** | One answered question: its scope, evidence bundle (AGT-3), status and optional generated answer. |

## 2. Principles

| # | Principle | Why it matters here |
|---|---|---|
| P1 | **Memory is context, never evidence.** Nothing recalled from memory is cited as a chart fact or a source. Facts are recomputed or fetched by key; interpretations come only from rule cards and passages. Earlier answer text may help interpret a follow-up, nothing more. | A remembered reading or note treated as evidence breaks OUT-1/OUT-2 and lets past answers reinforce themselves. |
| P2 | **Structured, not free-form.** The memory of record is typed records with IDs, not LLM-written summaries. | Summaries drop qualifiers and exceptions (RET-11) and drift over time. |
| P3 | **Explicit durable writes.** Persons, birth data, preferences and notes change only through an operator action or an operator-confirmed proposal. | Birth data is never silently changed (baseline §2.3); injected text must not write memory (AGT-6). |
| P4 | **Person-scoped.** Every personal record belongs to one person and is reachable only while that person is in scope. | One store holds several people's charts. |
| P5 | **Versioned.** Every stored derived item records what it was derived from. | Corrections and version upgrades must not leak stale facts (NFR-2). |
| P6 | **Visible and deletable.** The operator can see everything remembered about a person and delete it. | NFR-6. |

## 3. Memory types

| ID | Store | Holds | Lifetime | Written by | Authoritative for |
|---|---|---|---|---|---|
| M1 | **Person registry** | Persons, relations, versioned birth records, method inputs (INP-8), consent basis | Until deleted | Operator, or a confirmed proposal | Who a person is; when and where they were born |
| M2 | **Chart cache** | Computed facts, dasha trees, event searches (CALC-8) | Rebuildable, evictable | Calculation tools | Nothing. Always reproducible from M1 and a profile |
| M3 | **Session context** | Typed slots: native, method, profile, topic, as-of date, window, current location, chart scope, bundle IDs | Session, with idle expiry | Planner | What follow-ups and "that period" mean |
| M4 | **Run state** | Dependency plan, coverage checklist, budget counters, tool results, partial bundle | One question; a suspended run lives until answered, discarded or expired | Agent tools | Progress of the current question |
| M5 | **Reading history** | One reading record per answered question | Until deleted (retention configurable) | System, when a run completes | What was said, and on what basis |
| M6 | **Preferences** | Operator defaults and per-person overrides | Until changed | Operator | Settings the question does not state |
| M7 | **Native notes** | Dated, typed life events entered by the operator | Until deleted | Operator | Nothing astrological. Scoping and dates only |
| M8 | **Feedback** | Operator flags on facts, rules, citations or answers | Until resolved | Operator | Input to the review queues only |

M2 is already governed by CALC-8 and CALC-9; this document adds only its deletion (MEM-X-4) and staleness (MEM-X-6) duties.

**Outside this document:** the corpus, ontology and rule cards (KNW, ING) are the system's long-term domain knowledge and have their own expert-review workflow. Traces and logs (NFR-8) are observability; the agent never reads them as memory.

## 4. Use cases

| ID | Use case | Example | Stores | Expected behaviour |
|---|---|---|---|---|
| MUC-1 | Save and reuse a person | "My mother: 4 May 1958, 05:10, Nashik. Her career?" A week later: "My mother's 10th house?" | M1 | Answered at once; saving is proposed and done on confirmation; the later question needs no re-entry. |
| MUC-2 | Follow-up | After a career reading: "And my D10?" | M3, M2 | Same native, topic, method and profile; chart scope becomes D10; cached facts reused. |
| MUC-3 | Switch native or method | "What about my wife's?" / "And using BNN?" | M3 | Topic kept; native or method replaced; plan rebuilt; the answer lists what was inherited. |
| MUC-4 | Answer a clarification | System: "Aurangabad, Maharashtra or Bihar?" Operator: "Maharashtra." | M4 | The suspended run resumes; questions already answered are not asked again. |
| MUC-5 | Correct birth data | "The time was 10:42, not 10:30." | M1, M2, M5 | New birth-record version; facts recomputed; earlier readings marked as based on the superseded version. |
| MUC-6 | Recall a reading | "What did you say about my career in March?" | M5 | The stored reading is returned with its as-of date and versions. It is not regenerated. |
| MUC-7 | What has changed | "What's different since my last reading?" | M5, M2 | A fresh reading plus a list of differences in time-varying facts (dasha chain, transit states) and in versions. Old text is not edited. |
| MUC-8 | Set a preference | "Always show Devanagari." "Read Ravi with the KP ayanamsa." | M6 | Saved on confirmation; answers say which level supplied each setting. |
| MUC-9 | Past-event timing | "What was running when I changed jobs?" (job change noted as June 2019) | M7, M2 | The note supplies the date; dasha and transits are computed for that date. |
| MUC-10 | Flag an error | "Saturn isn't in the 9th." | M8, M5 | Flag stored against the reading and its versions; facts unchanged until reviewed. |
| MUC-11 | Inspect or forget a person | "What do you have on Ravi?" / "Delete Ravi." | All | Complete listing; after confirmation, everything about Ravi is deleted and the deletion is reported. |

### 4.1 Memory needs of the baseline use cases

| Baseline UC | Memory needed |
|---|---|
| UC-1 concept, UC-6 story, UC-7 contemporary | M3 (topic, method) and M6 (script). **No person memory**: INP-9 forbids asking for birth data. |
| UC-2 natal, UC-4 method-specific, UC-5 comparison | M1, M2, M3, M4, M5 |
| UC-3 timing | As UC-2, plus the as-of date and window rules of MEM-SES-2 |
| UC-8 follow-up | M3 is the core of it |
| UC-10 compatibility (Exp.) | Two natives in session scope; consent basis recorded for the second (INP-6) |
| UC-12 prashna (Exp.) | Question moment and place stored on the reading (M5), not on the person |
| UC-13 annual (Exp.) | One annual chart per person per year, in M2 |
| UC-11 muhurta (Exp.) | Current location and window in M3; candidate intervals on the reading (M5) |
| UC-9 remedy (Exp.) | Nothing beyond M3 and M5; never offered from memory unrequested (SAFE-2) |

## 5. Requirements

### 5.1 Person registry (MEM-PER)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-PER-1 | Store each person with: a person ID; a label (a name or a relation; a real name is not required); the relation to the self record, if any; the birth record (INP-1–3 fields, with resolved location ID, tz-database version, precision, provenance and uncertainty interval); and optional method inputs (INP-8). Name, caste, religion and gender are never required. | M | 3 | A person saved in one session is used in a later session without re-entry. |
| MEM-PER-2 | Resolve each person reference ("my mother", "Ravi", "her") to exactly one person ID, or ask. "I/my" means the session's native, which defaults to the self record; if there is none, ask. Never guess between candidates; never create a person implicitly. | M | 3 | Two-Ravis fixture asks; an unknown "my sister" asks for details instead of inventing a record. |
| MEM-PER-3 | For a relative, distinguish **their own chart** ("my mother's chart") from **the relative read from the native's chart** ("my chart about my mother": bhavat-bhavam, QRY-2). If the wording does not settle it and both are possible, ask. If the relative has no stored chart, offer the house-based reading or ask for birth data. The answer states which was used. | M | 3 | Fixtures for the three cases: own chart, house-based, unclear. |
| MEM-PER-4 | Birth data given in a session is usable at once for that session. It is saved to M1 only after the operator confirms (a confirmation prompt, or an explicit save flag in the API/CLI). Unsaved data is discarded when the session ends. | M | 3 | Unconfirmed details are absent from M1 after the session ends. |
| MEM-PER-5 | A correction creates a new birth-record version, with timestamp and reason; the previous version is kept. Facts derived from the old version are not reused; readings based on it are marked superseded. | M | 3 | 10:30 → 10:42 fixture: chart recomputed; old reading labelled "birth record v1, superseded". |
| MEM-PER-6 | Record a consent basis for persons other than self (operator-attested). It is required before a person is used as the second chart in compatibility (INP-6). | S | 7 | Compatibility without a consent basis returns `needs_input`. |
| MEM-PER-7 | Warn about a likely duplicate (same date and place, time within the uncertainty interval) before saving. | S | 3 | Duplicate fixture asks. |

### 5.2 Session context (MEM-SES)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-SES-1 | A session holds typed slots: native (two natives for compatibility), method(s), calculation profile, topic(s), explicit as-of date, time window, current location (INP-4), chart scope (varga, reference point) and the IDs of the evidence bundles it produced. Follow-ups are planned from these slots, not by replaying the transcript, so planning input does not grow with session length. | M | 3 | 30-turn fixture: turn 30 is planned correctly from the slots alone. |
| MEM-SES-2 | Apply the carry-forward rules below. | M | 3 | One follow-up fixture per row. |
| MEM-SES-3 | Every answer lists the values it inherited from the session, as it lists defaults (INP-5, OUT-4). | M | 3 | The "And using BNN?" answer shows the inherited native and topic. |
| MEM-SES-4 | References to earlier turns ("that Saturn period", "the yoga you mentioned") resolve to IDs in the session's bundles (period, rule card, fact). The referenced item is then re-fetched by ID; earlier answer prose is not reused as evidence. An unresolvable reference is asked about. | M | 3 | "That period" resolves to the period ID from the previous bundle. |
| MEM-SES-5 | Sessions expire after a configurable idle time and can be reset explicitly. Expiry and reset remove M3, suspended M4 and unsaved persons only. | S | 3 | Reset fixture: the next question inherits nothing. |

**Carry-forward rules (MEM-SES-2).** Inherited values are always listed in the answer (MEM-SES-3), so a wrong inheritance is visible and easy to correct.

| Slot | On a follow-up | Replaced or dropped when |
|---|---|---|
| Native | Kept | Another person is named |
| Method(s), profile | Kept | Named in the question |
| Topic | Kept | A new topic is asked |
| As-of date | **"Now" is re-resolved for every question** (QRY-5). An explicit as-of date is kept. | Changed or cleared |
| Time window | Kept | Changed or cleared |
| Current location (INP-4) | Kept | Changed; never saved to M1 without confirmation |
| Chart scope (varga, reference point) | Kept on the same topic | The topic changes |

### 5.3 Run state (MEM-RUN)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-RUN-1 | Within one question, the dependency plan, coverage checklist, budget counters (RET-11), tool results and the partial evidence bundle are held as typed state outside the LLM context. The LLM receives references and excerpts. Trimming the LLM context never removes gaps, qualifiers or exceptions from the run state. | M | 3 | Forced context-trim fixture still reports every gap in the bundle. |
| MEM-RUN-2 | A run that returns `needs_input` (OUT-8) is suspended with its plan and completed tool results. The `needs_input` response names the input it needs. If the next message supplies that input, the run resumes and reuses completed results whose inputs are unchanged; otherwise the suspended run is discarded. A session has at most one suspended run. | M | 3 | Ambiguous-place fixture completes after one answer, with no repeated question; an unrelated question discards the suspended run. |
| MEM-RUN-3 | Run state is discarded when the run ends, apart from what the reading record keeps. A crashed run is re-run, not resumed. | M | 3 | A completed run leaves no run-state records. |

### 5.4 Reading history (MEM-RDG)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-RDG-1 | Store one reading record per answered question: native and birth-record version, resolved scope, as-of date, evidence bundle (AGT-3), status, generated answer (if any) and all versions (NFR-2). It is the replay record for APP-5. | M | 3 | A stored reading replays to the same applicability decisions. |
| MEM-RDG-2 | **Prior readings are never evidence.** They are not cited, not reachable through any RET route, and not part of a new reading's evidence bundle. Readings from earlier sessions are not loaded into a new reading's context at all, except for recall and what-changed questions (MEM-RDG-3, MEM-RDG-4). Within a session, earlier answer text may be used only to interpret the question (P1). | M | 3 | A new career bundle contains no reference to earlier readings; a later-session reading is generated without them in context. |
| MEM-RDG-3 | Recall: list and return stored readings by native, topic, method and date, each with its as-of date and versions. | S | 4 | MUC-6 fixture returns the March record unchanged. |
| MEM-RDG-4 | What changed: produce a fresh reading and list how its time-varying facts (dasha chain, named transit states, events) and versions differ from the prior reading's. | S | 4 | A fixture crossing an antardasha boundary reports the change. |

### 5.5 Preferences (MEM-PRF)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-PRF-1 | Operator defaults for method(s), calculation profile, Sanskrit script (OUT-7) and answer length. Set explicitly; never inferred from behaviour. | M | 3 | A changed default is applied and stated in the next answer. |
| MEM-PRF-2 | Per-person overrides for method and profile. Precedence: the question > session slot > person override > operator default > system default. The answer names the level that supplied each setting. | S | 3 | Precedence fixture covers each level. |
| MEM-PRF-3 | No preference can relax SAFE-1–5, method isolation (RET-8) or profile honesty (CALC-3). Such a preference is refused, with the reason. | M | 3 | "Always predict the age of death" is refused. |

### 5.6 Native notes (MEM-CTX)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-CTX-1 | The operator may record dated notes about a native, typed from a fixed list (marriage, child, job change, relocation, education, other) and labelled operator-reported. Health and medical events are not a note type in v1 (SAFE-1, NFR-6). | S | 4 | A health-type note is rejected. |
| MEM-CTX-2 | Notes may scope a question and supply dates for past-event timing (MUC-9). They are **never** evidence for rule applicability, never used to adjust a birth time (baseline §2.3), and never treated as outcome validation (KNW-9, EVAL-8). The answer says when a note was used. | S | 4 | Fixture: adding a note changes no applicability state. |

### 5.7 Feedback (MEM-FBK)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-FBK-1 | The operator can flag a fact, rule, citation or answer, with a comment. The flag is stored with the reading and its versions and routed to calculation review or rule-card review (ING-5). It never changes facts, rule cards or the index directly. | S | 3 | After a flag, the next answer's facts are unchanged. |

### 5.8 Cross-cutting (MEM-X)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| MEM-X-1 | Personal memory (M1, M3–M8) lives in the encrypted private store (NFR-6), never in the knowledge index or ingestion inputs. | M | 3 | An index scan finds no person IDs or birth data. |
| MEM-X-2 | Memory reads are limited to persons in the current request or session. Retrieved passages and imported files cannot cause any memory read or write (AGT-6). | M | 3 | Injection fixture neither reads another person nor saves a record. |
| MEM-X-3 | The LLM reads and changes memory only through typed, validated tools. Durable writes (M1, M6, M7) need confirmation; deletion needs an explicit command or confirmation. | M | 3 | An unconfirmed write proposal leaves the store unchanged. |
| MEM-X-4 | Deleting a person removes every birth-record version, M2 entry, reading, note, flag and session reference, unlinks trace references, and reports what was removed (NFR-6). | M | 3 | After deletion, a search of every store finds no record of the person. |
| MEM-X-5 | The operator can list everything stored about a person. | M | 3 | The listing matches the deletion report for the same person. |
| MEM-X-6 | A stored item is reused only if its recorded versions (birth record, profile, engine, rule set, ontology, corpus) match the current ones; otherwise it is recomputed or marked superseded. | M | 3 | After a rule-set upgrade, old applicability results are not reused. |
| MEM-X-7 | In API-LLM mode, persons are sent as pseudonymous labels with relation types only. Names and raw birth data never leave the machine. Notes are sent only under the same explicit opt-in as chart facts (NFR-6). | M | 3 | Egress capture contains no names or birth data, and no notes without opt-in. |

## 6. Not needed (rejected)

| Rejected need | Why |
|---|---|
| Vector or "remember everything" memory over transcripts | Typed slots and reading records cover every use case. Similarity recall is non-deterministic and can mix people. |
| LLM-summarized sessions as the memory of record | Lossy: drops qualifiers and exceptions (P2). |
| Inferring personal traits (gender, caste, religion, beliefs, mood) | Conflicts with INP-8 and NFR-6, and nothing needs it. |
| Companion-style memory of worries or emotional state to tailor tone | Sensitive data with no use case; risks fear-based framing (SAFE-1, SAFE-3). |
| Learning rules or interpretations from conversations | Bypasses expert review (ING-5). Feedback goes to review instead (MEM-FBK-1). |
| Tracking prediction outcomes to "learn" accuracy | EVAL-8 is C; operator-entered outcomes are selective and unvalidated. |
| Rectifying birth time from life events | Out of scope (baseline §2.3). |
| Multi-user memory, sharing, cross-device sync | v1 is single-operator (baseline §2.2). |
| Durable resume of crashed runs | Deterministic tools plus M2 make re-runs cheap; only `needs_input` suspension is needed. |
| Cross-person pattern mining (family charts) | No use case; privacy risk. |

## 7. Changes to the baseline

| Baseline ID | Change |
|---|---|
| AGT-5 | Superseded by MEM-PER-1–5 and MEM-SES-1. |
| QRY-6 | Acceptance uses the MEM-SES-2 carry-forward table. |
| NFR-2 | Met per answer by MEM-RDG-1. |
| NFR-6 | Deletion scope per MEM-X-4; egress per MEM-X-7. |
| AGT-6 | Acceptance adds MEM-X-2. |
| Design [design.md](../design/design.md) §11.6 | Expand session state to the M1–M8 split. |

## 8. Open questions

> Tracked in [open-questions.md](open-questions.md) (C2, C3).

| # | Question | Blocks |
|---|---|---|
| 1 | Default retention for reading history, and the default session idle time. | Phase 3 |
| 2 | Does a standing preference to include remedies count as "on request" under SAFE-2? (Proposed: no; each question must ask.) | Phase 7 |

Decided in this revision: health events are not a note type in v1; unsaved persons last for the session; the self record is optional.

## 9. Review log

| Round | Main defects found | Fix |
|---|---|---|
| 1 (rev 1) | No acceptance criteria; no principles; no carry-forward rules; no write policy; no injection or egress coverage; bhavat-bhavam ambiguity missing; rejected needs had no reasons; no traceability. | Rev 2: principles P1–P6, store table with authority and writer, acceptance per requirement, carry-forward table, MEM-X, baseline change list. |
| 2 (rev 2) | Unsaved birth data lived for one question only, breaking follow-ups; "readings are never evidence" conflicted with reference resolution; notes unusable in API mode; consent made mandatory for every relative, beyond INP-6; terms undefined; open question left undecided. | Rev 3: session-scoped unsaved persons (MEM-PER-4); resolve to IDs and re-fetch (MEM-SES-4); notes follow the chart-fact opt-in (MEM-X-7); consent S, phase 7 (MEM-PER-6); §1 terms; health notes excluded. |
| 3 (rev 3) | P1 vs MEM-RDG-2 wording; no rule for telling an answer from a new question (MEM-RUN-2); time window dropped on native change without reason; current location (INP-4) had no slot. | Rev 4: within-session text for interpretation only; `needs_input` names the input it expects; window kept until changed; location slot added. |
| 4 (rev 4) | Wording only: a repeated sentence in MEM-RUN-2; MEM-PER-5 implied readings are reused; MEM-CTX-1 and MEM-RUN-3 had no acceptance test. | Fixed in place. |
| 5 (rev 4) | No further defects. Remaining items are owner decisions (§8). | — |
