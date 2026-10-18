# Requirements review and merge log

| | |
|---|---|
| **Date** | 2026-10-17 |
| **Inputs** | `rag-cl.md` (rev 1) and `rag-gpt.md` (proposed baseline). Both are removed from the tree; they remain in git history at `e1212a1`. |
| **Output** | [requirements.md](requirements.md) (current rev 3; original merged baseline rev 2) |

## 1. Approach

The two documents described the same product but disagreed on scope, format and rigour.

- **rag-cl.md** was concrete: fine-grained domain requirements, priorities, phases and numeric targets. The rag-claude design cites its IDs inline. Weak spots: technology and agent architecture written as requirements; a few rabbit holes (prana-level dashas, arcsecond accuracy); no acceptance criteria per requirement.
- **rag-gpt.md** was rigorous about provenance, uncertainty, failure states and acceptance evidence. Weak spots: it pushed much hard scope into "Core" (chart images, multi-user authorization, deletion-after-restore, response languages) and deferred every numeric target to a future "acceptance profile", which made phase exit undecidable.

**Merge rule used:** the domain content and IDs come from rag-cl (so the design's inline citations stay valid); the acceptance evidence, failure/partial states, provenance and uncertainty rigour come from rag-gpt. Where the two conflict, I chose the narrower, testable option for v1 and moved the rest to Expansion or Optional rather than deleting it.

## 2. Conflicts and the call made

| # | Conflict | rag-cl | rag-gpt | Decision | Why |
|---|---|---|---|---|---|
| C1 | Scoping scheme | Priority M/S/C + phase 1–7 | Core / Expansion / Optional, phases left to design | Kept M/S/C + phase; **tiers derived from them** (Core = M in phases 1–6; Expansion = phase 7; Optional = C) | One scheme, no double bookkeeping, and the design's delivery plan already uses phases. |
| C2 | Chart import from images | INP-7, C, phase 7 | INP-003, Core | Structured import = S, phase 7. **Image extraction = Optional** | See rabbit hole R1. Birth data is the Core path. |
| C3 | Vimshottari depth | Through prana (5 levels) | At least pratyantardasha | Pratyantardasha = M; sookshma = S; prana not required | See R3. |
| C4 | Numeric targets | 1″ positions, 1-day dashas, p95 latency | No numbers; "acceptance profile" set before production | **Concrete targets now** (NFR-1, NFR-3), agreed per phase | Phase exits must be decidable. A deferred acceptance profile is R9. |
| C5 | Positional accuracy | 1 arc-second | Unspecified | Planets 10″, Lagna 30″, dasha boundaries 2 days; discrete facts exact except near boundaries | 1″ against a closed-source reference chases ΔT and implementation differences. 10″ in the Moon is ~1.5 days on a 20-year Venus period, so the dasha tolerance is consistent. |
| C6 | Privacy / security model | Local, encrypted, deletable | Multi-user authorization, in-flight revocation, backup tombstones, concurrent publication/rollback | **v1 = local, single-operator deployment** (§2.2). Kept encryption, isolation from the index, log redaction, deletion and prompt-injection defences | See R5. rag-gpt's model is for a hosted multi-tenant service that nothing else in either doc assumes. |
| C7 | API LLM vs fully local | LLM may be an API | Egress-denied run must pass, including generation | Both: fully local mode must work end to end; API mode is opt-in, and raw birth data is **never** sent to an API (NFR-5, NFR-6) | Keeps the configurable-LLM requirement without leaking personal data. |
| C8 | Response language | S, phase 6 (Hindi, Marathi) | Core input | English in Core; Hindi/Marathi S, phase 7 (OUT-7) | Multilingual generation needs its own eval set; it is not on the critical path. |
| C9 | Remedies | S, phase 6 | Expansion | Expansion (phase 7), **on request only** (SAFE-2) | Highest safety exposure, lowest value to the core objective. Also closes rag-cl open question 4. |
| C10 | Contemporary Indian | Phase 6–7; design puts it in phase 7 | Core | Core-S, phase 6, limited to 1–2 named authors (ING-8) | Satisfies rag-gpt's Core intent without opening an unbounded "modern" corpus. |
| C11 | Technology stack | Listed in requirements (LangGraph, Qdrant, Docling, BGE-M3…) | Explicitly not requirements | Moved to design. Only Swiss Ephemeris stays as a constraint (licence implications) | Product choices are design decisions. |
| C12 | Agent architecture | AGT-1 fixed node list; AGT-4 open agent vs fixed workflow | Not specified | Kept the constraints (deterministic tools, per-method analysis, bundle contract); dropped the node list and AGT-4 to design | Requirements should not fix the graph shape. |
| C13 | Lunar calendar default | Open question | Not addressed | **Amanta** default, purnimanta per profile | Amanta is used in Maharashtra and the south; trivially configurable. |
| C14 | Western profile in v1 | Open question | Optional | Optional; not planned | Closes rag-cl open question 2. |
| C15 | Document ownership | Links to rag-claude design, rag-gpt as companion | Declares the two sets independent, IDs not aliases | One baseline supersedes both; ID mapping in §4 | Two live requirement baselines was the root problem. |

## 3. Rabbit holes removed or bounded

| # | Rabbit hole | Where | Risk | Resolution |
|---|---|---|---|---|
| R1 | Extracting charts from North/South/East Indian chart **images** | rag-gpt INP-003 (Core) | A computer-vision project on its own; images usually lack degrees, so every downstream fact becomes `unknown` anyway. | Optional (INP-7). Structured import is Expansion. |
| R2 | Uncertainty propagated over the **full plausible input interval for every fact** | rag-gpt CAL-008 | Unbounded: every derived quantity needs interval analysis. | CALC-7 scoped to a named list of discrete, time-sensitive facts, solved by boundary crossing (cheap and exact). |
| R3 | **Prana** (5th-level) dashas | rag-cl DAS-1 | Periods of minutes, meaningless under any real birth-time uncertainty, and multiplies fixtures. | Stop at pratyantardasha (M), sookshma (S). |
| R4 | **Arcsecond parity** with Jagannatha Hora | rag-cl NFR-1 | Chasing ΔT, nutation and ayanamsa implementation differences in a closed-source reference. | Tolerances that are tight enough for every discrete fact (C5). |
| R5 | **Multi-tenant security**: authorization leaks, mid-request revocation, backup tombstone re-application, concurrent publication and rollback | rag-gpt SEC-001…004, OPS-002, EVAL-004 | A hosted-SaaS hardening programme inside a local research tool. | Out of scope for v1 (§2.2). Reconsider if the product becomes hosted. |
| R6 | **Fixed stars** (catalog IDs, epoch, proper motion) | rag-gpt §5 inventory | A separate astronomical subsystem little used in the Core methods. | Out of scope (§2.3). |
| R7 | **Non-Gregorian birth-date input** ("original calendar") and unbounded date ranges | rag-gpt INP-002, EVAL-002 | Calendar conversion and pre-1900 Indian time zones are research problems in themselves. | Original decision: Gregorian 1900–2100 only. **Superseded on 2026-10-18:** no fixed year/country restriction; library-backed or verified calendar conversion and feature-specific capability checks (§2.2, INP-1/2). |
| R8 | **"All yogas"** and LLM rule extraction across every listed text | rag-cl KNW-5, rag-gpt §7 | Hundreds of yogas × variants × expert review = a review backlog that never ends. | Curated 20–30 yogas (KNW-5); a named Core source set (ING-8); everything else enters with a phase-7 bundle. |
| R9 | **Deferred "acceptance profile"** whose unset targets block release | rag-gpt OPS-005, EVAL-004, §9 | No phase can ever exit; quality targets are argued at the end. | Targets set at the start of each phase (§7 phase exit). |
| R10 | **Broad acquisition list** (Saravali, Phaladeepika, Samhitas, other Nadis, Lal Kitab editions, course notes, …) | rag-gpt §7 | Turns source acquisition into the project. | Core source set only (ING-8); other families wait for their bundle. The candidate list is in git history. |
| R11 | **Every Shodashvarga with every construction variant** | rag-cl VAR-2, rag-gpt CAL-005 | Variants multiply fixtures with little Core use. | One declared construction per varga (VAR-2); variants only when a rule needs them (VAR-4). |
| R12 | Kalachakra dasha, Lal Kitab, avasthas, Sarvatobhadra | rag-cl DAS-3, SCH-LK-1, STR-3, TRN-7 | Notoriously disputed or niche specifications. | C (Optional). |
| R13 | "Placidus everywhere" | rag-cl CALC-3 / SCH-KP-1 | Placidus is undefined above the polar circles; the edge case was in the EVAL list but had no defined behaviour. | Returns `unsupported` (§2.2); whole-sign still works. |

## 4. Other defects fixed

| Defect | Fix |
|---|---|
| rag-cl KNW-3 deferred its attribute list to design §7 (a requirement depending on the design). | Attributes listed inline. |
| rag-cl AGT-3 pointed to "companion doc §11", which does not exist (rag-gpt design has unnumbered sections). | Bundle contract written inline in AGT-3. |
| rag-cl RET-4 "identical top-k" was untestable with dense retrieval alone. | Now requires alias normalization to entity IDs before search. |
| CALC-6 and SCH-WES-1 duplicated each other; PAN-5 and rag-gpt DOM-002 likewise. | Merged into SCH-WES-1 and KNW-12. |
| Unknown birth time had no defined behaviour. | INP-3: Lagna facts `unknown`, Moon-based reading proceeds. |
| No partial/failed result states in rag-cl. | OUT-8, RET-11, RET-12 from rag-gpt. |
| `sensitive` facts could still evaluate to `satisfied`/`not_satisfied`. | APP-2: sensitive facts yield `unknown`. |
| No user interface or deployment boundary was stated anywhere. | §2.2. |
| rag-cl NFR-3 latency had no reference hardware (impossible to meet with some local LLMs). | Tied to the reference deployment in the design, S, revisable at phase exit. |
| Health/longevity guidance did not cover unsolicited death-timing. | SAFE-1 extended. |
| Remedy contraindications existed only in the content model. | Kept in KNW-8 and SAFE-2. |

## 5. ID mapping

### 5.1 rag-cl.md → requirements.md

Unchanged unless listed. UC numbers changed: UC-7 → UC-9, UC-8 → UC-10, UC-9 → UC-11, UC-10 → UC-12, UC-11 → UC-13, UC-12 → UC-8; new UC-7 (contemporary interpretation). CALC-6 → SCH-WES-1. PAN-5 → KNW-12. AGT-4 → design. New IDs: INP-9, VAR-4, KNW-12, ING-8, ING-9, QRY-6, RET-11, RET-12, OUT-8, NFR-10, EVAL-9, EVAL-10, SAFE-5.

### 5.2 rag-gpt.md → requirements.md

| rag-gpt | Merged |
|---|---|
| INP-001 | INP-4, QRY-5 |
| INP-002 | INP-1, INP-2, INP-3 (original-calendar exclusion superseded on 2026-10-18; see R7 and current INP-1) |
| INP-003, INP-004 | INP-7 (images Optional, R1) |
| INP-005 | INP-9, QRY-3 |
| INP-006 | QRY-6, AGT-5 |
| INP-007 | INP-8 |
| CAL-001 | CALC-9, AGT-1 |
| CAL-002 | CALC-3 |
| CAL-003 | CALC-1, CALC-2, REL-1 |
| CAL-004 | PAN-1, PAN-2 |
| CAL-005 | VAR-1, VAR-2, VAR-4 |
| CAL-006 | DAS-1, DAS-2 |
| CAL-007 | TRN-2 |
| CAL-008 | CALC-7, DAS-4 (bounded, R2) |
| CAL-009 | CALC-5, STR-*, DAS-3, SCH-* (fixed stars dropped, R6) |
| DOM-001 | KNW-1…4 |
| DOM-002 | KNW-12 |
| DOM-003 | §2.1, QRY-1 |
| DOM-004 | SCH-BNN-3, RET-8 |
| DOM-005 | KNW-6, QRY-4 |
| DOM-006 | KNW-7 |
| DOM-007 | KNW-9 |
| SRC-001, SRC-007 | KNW-10 |
| SRC-002 | ING-9 |
| SRC-003 | ING-1 |
| SRC-004 | ING-3 |
| SRC-005 | ING-5 |
| SRC-006 | ING-6 |
| RULE-001 | KNW-5, ING-5 |
| RULE-002 | APP-2 |
| RULE-003 | APP-3 |
| RULE-004 | APP-5 |
| RULE-005 | ING-5 |
| RET-001 | RET-1, RET-2 |
| RET-002 | INP-9, QRY-4 |
| RET-003 | RET-6, RET-7 |
| RET-004 | RET-8 |
| RET-005, RET-006 | RET-11 |
| RET-007 | RET-12 |
| RET-008 | AGT-3 |
| OUT-001, OUT-002 | AGT-3 |
| OUT-003 | OUT-8 |
| OUT-004 | OUT-1, OUT-3, OUT-4 |
| OUT-005 | OUT-3 |
| SEC-001, SEC-004 | NFR-6 (multi-user parts dropped, R5) |
| SEC-002 | ING-7, RET-2 (in-flight revocation dropped, R5) |
| SEC-003 | AGT-6 |
| SEC-005, OPS-001 | NFR-5, NFR-6 |
| OPS-002 | NFR-2 (concurrent publication/rollback dropped, R5) |
| OPS-003 | NFR-8, APP-5 |
| OPS-004 | NFR-10 |
| OPS-005 | NFR-1, NFR-3, phase exit (R9) |
| EVAL-001, EVAL-005 | EVAL-10 |
| EVAL-002 | EVAL-1, EVAL-2 |
| EVAL-003 | EVAL-3 |
| EVAL-004 | Phase exit (§7) |
| EVAL-006 | EVAL-8 |
| §9 end-to-end scenarios | EVAL-9 |
| §5 knowledge inventory | KNW-1…12, §2 |
| §6 method bundles | §2.1, SCH-* |
| §7 acquisition candidates | ING-8 (Core set); the rest is in git history (R10) |

## 6. Design follow-ups

Resolved by the merged design ([design.md](../design/design.md), log in [design/review.md](../design/review.md)): licence filtering and PII redaction moved to phases 1–2; modern Indian in phase 6; stack, workflow shape and high-latitude behaviour live in the design; the two designs are merged into one that cites these IDs and traces all of them (design §22).

Design review changed one requirement: **KNW-5** spans phases 3–6, with rule-card review ordered by topic (design §10.7).

## Input-scope revision — 2026-10-18

At the user's request, removed the fixed birth-year range, country preference in place lookup, blanket historical-year prompt, and categorical non-Gregorian input exclusion. Accept worldwide names/coordinates and original calendar labels; use maintained conversion libraries or documented converted inputs. Do not build bespoke geographic, historical-time or calendar research systems as a prerequisite. Keep invalid-input checks, explicit assumptions, and actual per-feature engine/data/domain limits. Unsupported calculations do not block unrelated knowledge retrieval. No changes to the selected astrological methods or their release phases.
