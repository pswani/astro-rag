# Requirements for the Indian astrology agentic RAG application

Date: 2026-10-17  
Status: Proposed requirements baseline derived from the user's question-and-birth-chart use case. No implementation or source-validation completion is implied.  
Design: [rag-gpt.md](../design/rag-gpt.md).

## 1. Purpose and document ownership

Given a question and birth details or a supplied birth chart, the application shall calculate or validate the relevant chart facts, retrieve knowledge for the selected astrological methods, evaluate which rules apply, and supply an agentic AI system with a cited evidence bundle. It shall also answer educational, source-comparison and narrative questions without requiring a personal chart.

This document owns **what is required and how acceptance is demonstrated**. The design owns architecture, schemas, algorithms, technology choices, tuning and delivery sequencing. Frameworks, database products, model names, exact retrieval counts and chunk sizes are not product requirements. The separate `rag-cl.md` requirements and `rag-claude.md` design remain independent companion documents; their identifiers and phase numbers are not aliases for this baseline.

“All relevant knowledge” means covering the declared question dependencies, selected methods, prerequisites, exceptions and contrary evidence within resource limits. The system shall expose gaps and truncation; it shall not claim exhaustive knowledge merely because a top-k search completed.

## 2. Scope, terms and priorities

- **Core:** required for the first release that claims to satisfy the question-plus-chart objective. Engineering milestones may precede it; educational search alone does not complete it.
- **Expansion:** part of the target coverage, delivered through separately validated method/use-case bundles. An unavailable bundle must be reported as unsupported, never emulated by another school.
- **Optional:** a separately selectable extension, not required to complete the Indian astrology baseline.

Core coverage includes one declared Parashari profile, one source-reviewed BNN profile, and attributed contemporary Indian interpretations. “Vedic” is an umbrella label rather than a single executable rule set. BNN means Bhrigu Nandi Nadi associated with R. G. Rao; other Nadi lineages remain distinct. “Modern” means contemporary Indian interpretation in the baseline; Western/psychological techniques are optional and separate.

A **method profile** identifies a school/lineage and reviewed interpretation conventions. A **calculation profile** identifies numerical conventions. They are linked but need not be identical. A **chart fact** is an imported or computed observation with provenance. A **rule** is a source-attributed conditional interpretation. **Applicability** is `satisfied`, `not_satisfied` or `unknown`. An **evidence bundle** is the structured handoff to a downstream agent, independently usable without generated prose.

## 3. Use cases

| ID | User need | Scope | Acceptance scenario |
|---|---|---|---|
| UC-01 | Learn a concept or compare source definitions, e.g. tithi or Navamsha | Core | Cited definitions; no birth details requested unnecessarily |
| UC-02 | Ask a natal question using birth data or a supplied chart | Core | Relevant chart facts plus applicable source-backed rules |
| UC-03 | Ask about mahadasha/subperiods or a future interval | Core | Actual active/overlapping periods and relevant transit evidence |
| UC-04 | Request a BNN reading or compare BNN with Parashari | Core | Independently attributed bundles; differences preserved |
| UC-05 | Ask for a contemporary Indian interpretation | Core | Named author/commentator and explicit modern mappings |
| UC-06 | Explore Puranic stories, symbolism and variants | Core | Source episode and later associations separately attributed |
| UC-07 | Continue a chart conversation, e.g. “and my D10?” | Core | Authorized chart reused; topic/time/method changes re-evaluated |
| UC-08 | Ask about traditionally prescribed practices/remedies | Expansion | Original prescription and attribution; no invented efficacy |
| UC-09 | Compare two charts under a selected compatibility system | Expansion | Both charts validated; matching variants and exceptions retained |
| UC-10 | Select a muhurta for an activity/place/window | Expansion | Candidate intervals evaluated against declared constraints |
| UC-11 | Ask a prashna/horary question | Expansion | Question-moment inputs and specific method used |
| UC-12 | Examine annual charts or additional Indian schools | Expansion | Validated method-specific calculations and evidence |

## 4. Functional requirements

### 4.1 Inputs and chart handling

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| INP-001 | Accept question text, selected methods, response language, as-of timestamp, user time zone and optional target interval/location; resolve relative dates explicitly. | Core | “Next year” and “now” resolve reproducibly in fixtures. |
| INP-002 | Accept birth date, original calendar, local time, place/coordinates, birth-time precision, provenance and uncertainty; use historical offsets and surface date/location/DST ambiguities. | Core | Ambiguous and nonexistent civil times do not silently produce a chart. |
| INP-003 | Accept structured chart facts and chart images; preserve original artifact, declared settings, extraction confidence and known/unknown fields. Register North, South and East Indian layout support explicitly. | Core | Representative layouts are extracted or explicitly flagged for correction; missing degrees remain unknown. |
| INP-004 | Reconcile supplied charts with calculated facts when birth data exist; retain both versions and explain mismatched settings or values. | Core | Conflict fixture yields provenance and a visible resolution or unresolved state. |
| INP-005 | Make missing inputs question-dependent; permit education and supported date-only/chart-only answers without fabricating unavailable facts. | Core | An image without degrees cannot yield invented precise dasha or transit contacts. |
| INP-006 | Maintain authorized conversation state and chart references; re-plan after changes to time, method, chart or topic. | Core | Follow-up uses the intended chart and invalidates affected assumptions. |
| INP-007 | Do not require identity, caste, religion or gender for astronomy calculations. Any method-specific personal input must be justified and explicit. | Core | Basic chart calculation works without those fields. |

### 4.2 Calculation and uncertainty

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| CAL-001 | Use deterministic tools for positions, chart transformations, periods and event times. Record inputs, units, coordinate/time conventions, engine/data versions and result provenance. | Core | Same pinned inputs/settings reproduce results within declared numeric tolerances. |
| CAL-002 | Version calculation profiles covering zodiac, ayanamsa, origin/frame/corrections, nodes, house method, varga/dasha variants, year basis, sunrise and calendar conventions. Never silently use a different profile. | Core | Comparison retains distinct profile IDs; unsupported settings return explicit status. |
| CAL-003 | Supply relevant natal graha/luminary/node positions, sign/degree, nakshatra/pada, ascendant, house/lordship and supported condition/relationship facts. Keep school-dependent definitions explicit. | Core | Expert-reviewed fixtures verify values and reference points. |
| CAL-004 | Compute the five panchanga limbs with their actual transition intervals and declared day/sunrise convention; distinguish calendar calculation from observance rules. | Core | Boundary fixtures include adjacent instants and repeated/skipped calendar-day cases. |
| CAL-005 | Support D1, D9 and D10 where needed by the initial question profiles; identify each varga algorithm and expand through the registered divisions. | Core; additional divisions Expansion | Variant fixtures preserve distinct outputs; unsupported divisions remain unavailable. |
| CAL-006 | Compute Vimshottari birth balance, period hierarchy at least through pratyantardasha, active chains and all intervals overlapping the requested window; retain year-length convention. | Core | Boundary, parent/child and interval-overlap fixtures pass. |
| CAL-007 | Calculate relevant ingress/contact/station/retrograde events, retaining repeated crossings and applicable frame/location definitions. | Core | Retrograde-loop fixture returns all relevant events, not just a daily sample. |
| CAL-008 | Propagate uncertainty across the full plausible input interval; identify stable, sensitive and unknown facts and period boundaries. Never silently rectify a birth time. | Core | A boundary-crossing fixture cannot be labeled stable based only on endpoint samples. |
| CAL-009 | Add strengths, other dashas, upagrahas/special points, additional vargas, fixed-star calculations and specialized method calculations only with validated specifications and eligibility rules. | Expansion | Every advertised capability has fixtures, conventions and source scope. |

### 4.3 Domain and method coverage

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| DOM-001 | Maintain the knowledge coverage inventory in section 5, with explicit definitions, aliases, numerical boundaries where relevant and attributed interpretation variants. | Core registry; staged content | Each category has an owner/status and supported questions; absent content is visible. |
| DOM-002 | Keep signs, houses, nakshatra sectors, individual stars, nitya yoga/chart yoga and compatibility nadi/Nadi traditions distinct. | Core | Ambiguous-term fixtures resolve or request context without merging entities. |
| DOM-003 | Maintain the method bundles in section 6 and a capability declaration per bundle: supported topics, calculations, rules, sources and known gaps. | Core registry; staged activation | Unsupported requests are disclosed before method-specific conclusions. |
| DOM-004 | Preserve school, lineage, commentator and variant attribution. Separate Rao's BNN from later additions; label modern profession/topic mappings and declared hybrid techniques. | Core | Cross-method fixture cannot apply another school's rule silently. |
| DOM-005 | Map each topic and method to the required facts, rule families, exceptions and time dependencies; allow retrieval to discover additional prerequisites. | Core | Career query demonstrates a dependency checklist and targeted expansion. |
| DOM-006 | Represent Puranic episodes, variants, symbolic associations, practices and predictive assertions as distinct linked claims. | Core narrative; practices Expansion | Story evidence alone cannot justify an uncited personal prediction. |
| DOM-007 | Keep case examples, originally made predictions and independently reported outcomes distinct; preserve unavailable or uncertain outcomes. | Core case model | A worked example is not labeled a verified outcome without outcome evidence. |

### 4.4 Acquisition, ingestion and provenance

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| SRC-001 | Register exact work/edition, attributed author, editor/translator, language/script, catalog identifiers, rights/access status, source URI, coverage, extraction quality and reviewer before publication. | Core | A retrieved passage resolves to its exact registered edition. |
| SRC-002 | Preserve originals and stable page/verse/chapter/timestamp locators; distinguish printed pages from file indices and preserve verified translation/commentary alignment. | Core | Locator still resolves after reindexing and edition replacement. |
| SRC-003 | Ingest Markdown, text/HTML, native and scanned PDF, Office documents and image/table material through declared format support; retain structure and mark extraction failures. | Core | Representative corpus demonstrates page order, table headers and numeric fidelity. |
| SRC-004 | Preserve meaningful evidence units and links among rule, prerequisite, exception, table, chart diagram and explanation. | Core | Relevant exception remains reachable when its rule is retrieved. |
| SRC-005 | Separate machine-proposed assertions, generated summaries and teaching analogies from reviewed evidence; require method-competent review before executable rule publication. | Core | Query agent cannot promote a draft or cite generated text as original evidence. |
| SRC-006 | Make ingestion incremental/idempotent; propagate updates/deletions to passages, rules, narrative links, indexes and caches; prevent mixed published source versions. | Core | Unchanged re-ingestion duplicates nothing; withdrawn evidence disappears from new queries. |
| SRC-007 | Maintain an acquisition register and a topic/method/source coverage matrix, distinguishing candidate, acquired, parsed, reviewed and published material. | Core | Every advertised topic has reviewed evidence coverage or a declared gap. |

### 4.5 Rule applicability

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| RULE-001 | Store rule prerequisites, chart/reference scope, typed conditions, interpretation modality, qualifiers, exceptions, contradictions and supporting passages. | Core | Each executable rule resolves to reviewed source evidence and a version. |
| RULE-002 | Evaluate supported predicates with three-valued logic; missing facts, unsupported calculations and unstable inputs cannot become false or satisfied by default. | Core | Positive, negative and unknown fixtures all pass. |
| RULE-003 | Evaluate dependent qualifiers/cancellations without losing the original formation result; detect cycles and report incomplete evaluation. | Core | Cancellation and cyclic-dependency fixtures produce explicit qualified/unknown conclusions. |
| RULE-004 | Log facts and rule versions used, per-condition outcomes and reasons for accepted, rejected or unknown applicability. | Core | A reviewer can replay a rule decision without reading hidden model reasoning. |
| RULE-005 | Preserve ambiguous prose as source text requiring interpretation/review; do not fabricate executable precision or citations. | Core | Ambiguous rule fixture cannot enter the approved predicate set automatically. |

### 4.6 Retrieval and agent execution

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| RET-001 | Support lexical and semantic passage retrieval plus exact entity, rule and numeric/interval lookups; apply trusted access/method/source filters to every path. | Core | Exact verse, transliterated alias and numeric/time conditions each retrieve correctly. |
| RET-002 | Route by intent and topic; compute only needed facts and skip personal calculations for educational/narrative questions. | Core | A tithi-definition question does not request birth data. |
| RET-003 | Retrieve prerequisites, exceptions, cancellations and contrary evidence explicitly; maintain method-specific coverage rather than relying on similarity rank alone. | Core | Benchmark includes the exception and adverse interpretation, not only supporting passages. |
| RET-004 | Retrieve each requested school/source independently and preserve separate evidence through comparison. | Core | A larger corpus from one school cannot erase the smaller requested school. |
| RET-005 | Bound calls, retries, dependency depth, elapsed time, cost and context; surface exhaustion and any omitted evidence categories. | Core | Forced-budget fixture returns partial/insufficient status and identified gaps. |
| RET-006 | Assemble nonredundant context while retaining material qualifiers and reserving coverage for required methods/families; do not claim completeness after truncation. | Core | Small-context fixture retains exceptions or marks the affected conclusion incomplete. |
| RET-007 | Handle missing data, empty retrieval, unsupported methods, tool failures and contradictory sources explicitly; never replace unavailable evidence with model invention. | Core | Failure scenarios yield actionable missing-evidence records and bounded retries. |
| RET-008 | Provide a machine-readable evidence-bundle interface independent of answer generation; authorize follow-up evidence fetches as well as initial searches. | Core | A downstream agent receives sufficient authorized evidence without access to hidden chat history. |

### 4.7 Output contract

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| OUT-001 | Return resolved query scope, chart/input provenance, method/calculation profiles, relevant facts/periods/events, applicable/unknown rules, qualifications, contrary evidence, passages, cases, gaps and versions. | Core | Schema validator rejects dangling references or missing per-method records. |
| OUT-002 | Include source excerpts and precise locators, not only IDs; preserve enough context for the receiving agent to assess each material claim. | Core | An independent consumer can inspect an exception and its supporting passage. |
| OUT-003 | Distinguish complete-for-declared-scope, partial, needs-input, unsupported and failed results; label coverage as a checklist against declared dependencies, not corpus-wide certainty. | Core | Mixed-method partial success keeps successful evidence and failed-method status. |
| OUT-004 | Generated answers shall cite material claims, identify methods/defaults, distinguish facts from traditional interpretations/symbolism, and expose relevant uncertainty or disagreement. | Core | Human review verifies source entailment and correct chart-fact references. |
| OUT-005 | Do not treat similarity scores, LLM confidence, school agreement or retrieval accuracy as calibrated probabilities of life outcomes. | Core | Answer audit finds no such substitution. |

## 5. Knowledge acquisition inventory

DOM-001 and SRC-007 require the inventory below. Registry coverage is Core; full implementation/content activation follows the method and use-case scope. The information column specifies collection coverage; representations are illustrative and do not mandate a storage product.

| Knowledge/data domain | Information to gather | Representation and retrieval use |
|---|---|---|
| Birth and query context | Original birth date/time/place, calendar, location coordinates, time accuracy and source; question, topic, time horizon, current/event location when relevant | Private structured input; determines calculation and missing-data requirements |
| Calculation conventions | Zodiac, named ayanamsa implementation, node model, house method, varga algorithms, dasha conventions, sunrise definition, engine versions | Versioned calculation profile; every computed artifact references it |
| Grahas | Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu; aliases and school-specific meanings | Canonical entities plus cited, tradition-specific assertions |
| Rashis | Twelve signs; boundaries, lords, modalities, elements, classifications and source-specific interpretations | Reference tables plus interpretation records |
| Bhavas and reference frames | Twelve houses, house lords, occupants, derived houses; Lagna, Chandra and other explicitly defined reference points | Calculated chart relations plus interpretive rules |
| Special points and lagnas | Arudha and special-lagna constructions, Gulika/Mandi and other upagrahas, Sahams where supported; algorithm variants and intended use | Derived points with method-specific calculation specifications |
| Nakshatras | Standard 27 mansions and 108 padas; lords, deities, symbols, shakti, gana, yoni, nadi, naming syllables and source variants | Boundary tables, multilingual entities, meanings and matching rules |
| Fixed stars | Catalog identifiers, aliases, epoch, coordinates, proper motion, brightness and sourced interpretations if supported | Separate astronomical entities; do not treat a nakshatra sector as an individual star |
| Panchanga | Tithi, vara, nakshatra, nitya yoga, karana; paksha, lunar month, adhika/kshaya month, regional calendars | Computed intervals plus regional and ritual interpretation rules |
| Natal positions | Longitude, latitude, distance and speed where needed; sign, degree, nakshatra, pada, house, cusp relationship | Structured numeric facts; queryable by exact conditions |
| Planetary condition | Retrogression, stations, combustion, planetary war, dignity, friendship, avastha and boundary conditions | Facts evaluated under named definitions; thresholds remain source-specific |
| Planetary relationships | Conjunction, aspects, exchanges, dispositors, mutual links, argala, sign aspects and BNN relations | Typed edges carrying the method and reference frame |
| Strength | Shadbala components, bhava bala, varga strength, Ashtakavarga/Bhinnashtakavarga/Sarvashtakavarga and conventions | Numerical feature tables plus texts explaining scope and interpretation |
| Divisional charts | Supported vargas, algorithms, intended uses, alternatives and birth-time sensitivity | Derived charts with method IDs and explanatory references |
| Yogas and doshas | Formation predicates, chart scope, strength conditions, cancellation/mitigation, timing prerequisites, exceptions and variant definitions | Structured rule records linked to original passages |
| Dasha systems | Eligibility, starting rules, sequence, durations, balance, nested periods, exceptions and interpretation | Calculation specifications + interval store + interpretation corpus |
| Gochar and movements | Ingresses, nakshatra/pada crossings, stations, retrograde loops, conjunctions, exact contacts, eclipses, returns | Event search/calculation plus tradition-specific timing rules |
| Question domains | Career, education, relationships, residence, travel, property, family, spirituality, etc.; meanings and required evidence per method | Topic-to-dependency maps; these are routing aids, not predictive rules |
| Compatibility | Regional matching systems, component scores, exceptions, two-chart relationships and consented context | Dedicated two-person workflow; preserve score definitions and regional variants |
| Muhurta | Activity-specific requirements, local panchanga, avoid/prefer intervals, exceptions, candidate-time ranking | Constraint records plus interval intersection over the requested place/window |
| Prashna | Question moment/location, question validity rules, chart construction and method-specific interpretation | Separate query profile; do not silently reuse natal rules |
| Annual/other techniques | Tajika/Varshaphala, Muntha, annual periods, Sahams and specialized techniques as supported | Separate calculation and interpretation modules |
| Stories and symbolism | Puranic/epic accounts, graha and nakshatra deities, variants, symbolism, later commentarial links | Narrative records with verse/edition provenance; distinct from prediction rules |
| Remedies | Original prescriptions, devotional context, source, prerequisites, regional practice and any stated efficacy claims | Optional corpus; report as traditional practices with attribution |
| Worked cases | Chart facts, stated method, cited rules, prediction as originally made, reported outcome, uncertainty | Case records; used for explanation and separately governed evaluation |
| Terminology and modern mappings | Sanskrit, IAST, English, Hindi and selected regional aliases; carefully attributed contemporary profession/topic mappings | Lexicon, entity IDs and explicit modern commentary records |

Catalog Sun and Moon as luminaries and Rahu/Ketu as lunar nodes while retaining their traditional graha names. Add Uranus, Neptune, Pluto, asteroids or other points only to profiles that actually use them.

## 6. Method bundle inventory

DOM-003 and DOM-004 govern these bundles. Parashari, BNN and contemporary Indian content are Core; other Indian bundles are Expansion; Western/psychological techniques are Optional. Every active bundle requires reviewed rules and applicable calculation fixtures. Listing a bundle does not assert universal agreement within it.

| Bundle | Knowledge to acquire and encode | Method isolation requirement |
|---|---|---|
| Parashari | Graha/bhava/rashi meanings; lordship; dignity and strength; yogas/doshas with exceptions; vargas; named dasha systems; transit interpretation | Pin source definitions and reference frames; do not universalize one commentary |
| Jaimini | Chara karakas, seven/eight-karaka variants, Rahu handling, rashi drishti, argala, arudhas, karakamsha/upapada, named rashi dashas | Distinguish variants and avoid silently substituting Parashari aspects |
| BNN / R. G. Rao and declared lineages | Natural significators, planetary combinations, sign/dispositor relations, exchanges, relative placements, degree/order rules where attested, transit activation, worked chart narratives | Separate Rao's statements from later teachers' additions and case-derived generalizations |
| KP | Star/sub/sub-sub division algorithms, cusp calculation, ayanamsa choice, significator hierarchy, ruling planets, period/transit and horary rules | Use the chosen KP variant and its cusp precision; do not borrow an unrelated house profile |
| Tajika / Varshaphala | Annual return construction, annual ascendant and lord, Muntha, aspects, Tajika yogas, Sahams, annual period systems | Annual-chart facts and aspect rules retain their own scope |
| Lal Kitab | Edition-specific house/planet conventions, interpretive logic and remedies | Avoid translating its rules directly into generic Parashari rule predicates |
| Prashna | Question chart construction, validity conditions, topic rules and specific methods | Preserve question moment/location; natal inputs may not be required |
| Muhurta | Activity rules, panchanga, natal-relative conditions where used, local intervals and cancellations | Search constrained intervals for a declared activity and place |
| Compatibility | Ashtakoota, Dashakoota and regional variants, score definitions, exceptions and broader chart methods | Do not merge unlike scoring systems or treat a score as a guaranteed outcome |
| Contemporary Indian practice | Named authors' interpretations, contemporary occupations/topics, explicit combinations of methods | Label new mappings and hybrid methods as modern commentary |
| Western/psychological, if required | Tropical/sidereal choice, outer planets, aspects/orbs, houses, returns, progressions and interpretive schools | A distinct optional profile; do not silently introduce it into Indian methods |
| Other Nadi/regional traditions | Specific texts, language, lineage, chart construction and interpretive methods | BNN, other Nadi texts and palm-leaf consultation practices are not interchangeable datasets |

Rao's introduction discusses natural significators, relative planetary positions, sign lords, exchanges and transits, and gives Lagna a different emphasis. This supports a distinct BNN relation model; it does not establish one universal three-rule BNN algorithm. [Primary text scan, introduction](https://astrofoxx.wordpress.com/wp-content/uploads/2018/11/bhrigu-nandi-nadi.pdf).

## 7. Acquisition candidates

The following source families guide SRC-001/SRC-007. They are candidates requiring edition, rights and quality checks; no claim is made that all listed texts have been obtained or inspected. The source register, rather than this document, will hold acquired edition records.

Create an acquisition register before large-scale ingestion. For each entry record: exact title, attributed author, editor, translator, publisher, edition/year, language/script, ISBN or catalog ID, scan/source URI, rights status, coverage, OCR condition, reviewer and ingestion status.

| Source family | Candidate materials | Why acquire them |
|---|---|---|
| Classical natal texts | Brihat Parashara Hora Shastra, Brihat Jataka, Saravali, Phaladeepika, Jataka Parijata, Sarvartha Chintamani, Uttara Kalamrita | Definitions, natal interpretation, yogas and period rules; verify each edition rather than assuming identical contents |
| Jaimini | Upadesha/Jaimini Sutras with multiple identified commentaries | Preserve differences in interpretation and computation |
| BNN | R. G. Rao's Bhrigu Nandi Nadi and relevant related works; explicitly identified later lineage materials | Rule passages and full worked-chart contexts |
| Other Nadi | Named editions such as Deva Keralam/Chandra Kala Nadi and regional materials | Extend coverage without treating all Nadi as BNN |
| KP | K. S. Krishnamurti's Readers and identified later technical works | Original method definitions, worked cases and variant tracking |
| Tajika, Prashna, Muhurta | Tajika Nilakanthi, Prashna Marga, Muhurta Chintamani and method-specific commentaries | Specialized question and timing workflows |
| Lal Kitab | Clearly identified original editions and licensed translations/commentaries | Edition-specific interpretation and remedies |
| Samhita and calendrical works | Brihat Samhita, astronomical/calendrical texts and regional panchanga manuals | Broader cultural/calendar coverage; not all content belongs in natal prediction retrieval |
| Modern teaching | Named-author books, licensed course notes, permitted lecture transcripts and worked examples | Contemporary explanations and modern domain mappings |
| Puranic and devotional | Identified Purana/epic editions, relevant passages, graha/nakshatra accounts, stotras and regional practice sources | Narrative, symbolism, devotional context and attributed practices |
| Astronomical references | Ephemeris documentation/data, time-zone rules, geographic gazetteer, star catalogs when required | Reproducible computation and validation |
| Evaluation material | Expert-written questions, verified calculation fixtures, cited rule applicability cases and separately documented outcomes | Measure the different kinds of correctness separately |

This is a proposed acquisition list, not a claim that all listed editions have been inspected. Do not infer dates, exact chapter numbers or textual authenticity from unsourced summaries. Record textual variants and conflicting translations as evidence, not as ingestion noise.

Useful starting points include [GRETIL's catalog of Indian-language texts](https://gretil.sub.uni-goettingen.de/gretil.html), the [author's textbook page](https://vedicastrologer.org/articles/astro_books.htm), and [Sagar's description of that textbook's coverage](https://sagarpublications.com/astrology/vedic-astrology-an-integrated-approach/). Catalog availability or a free download is not itself permission to redistribute or commercially ingest a particular edition.

Prefer primary text → identified translation/commentary → named practitioner exposition. Unverified web summaries may help discover sources but should not become executable rules automatically. Source authority is a property within a tradition; it is not evidence of empirical predictive validity.

## 8. Nonfunctional requirements

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| SEC-001 | Isolate private birth details, chart graphs, uploads and conversation state from shared knowledge and from unauthorized users. | Core | Negative tests cover search, SQL/rules, graph expansion, source fetch, exports and caches. |
| SEC-002 | Enforce source rights and access revocations in retrieval and citation display; exclude unauthorized excerpts before any model call. | Core | Revocation during an in-flight request prevents affected delivery. |
| SEC-003 | Treat source content as untrusted data; keep tool permissions and publication authority outside document/model control. | Core | Prompt-injection fixture cannot reveal another chart, publish rules or expand permissions. |
| SEC-004 | Apply declared retention/deletion policy to personal data, derived artifacts, logs, caches and backups; prevent resurrection after restore. | Core | Deletion/restore drill demonstrates tombstone reapplication and documented backup expiry. |
| SEC-005 | Make external data transmission explicit and configurable, with redacted tracing; no private data leave a local-only deployment. | Core | Offline/egress-denied acceptance run includes ingestion, retrieval, generation and evaluation paths. |
| OPS-001 | Allow a fully local runtime after provisioning; keep embedding, reranking, generation and evaluation providers replaceable. | Core deployment option | Local-only run succeeds; changing generation does not require re-embedding. |
| OPS-002 | Pin compatible corpus/rule/index/calculation versions per query and prevent mixing releases; support rollback without reviving withdrawn evidence. | Core | Concurrent publication and rollback fixtures preserve coherent evidence versions. |
| OPS-003 | Record structured execution/evidence traces, durations, errors, versions and resource use without exposing unnecessary personal data. | Core | Replay reconstructs evidence decisions; logs pass redaction checks. |
| OPS-004 | Support bounded retries, resumable ingestion and explicit degraded/failure states; do not silently substitute conventions or methods during failure. | Core | Failed worker/tool scenarios are recoverable and remain visible. |
| OPS-005 | Declare supported languages/scripts, date/geographic ranges, resource budgets and performance targets before production acceptance; measure per workload. | Core | A published acceptance profile has concrete values, not unresolved placeholders. |

## 9. Acceptance and validation

| ID | Requirement | Scope | Acceptance evidence |
|---|---|---|---|
| EVAL-001 | Maintain expert-reviewed calculation, extraction, retrieval, applicability and answer fixtures independently. | Core | Failures are attributable to a layer; changing a model cannot conceal numerical errors. |
| EVAL-002 | Cover aliases/scripts, tables, diagrams, numbers/negations, variants, missing inputs, conflicting sources, exact boundaries, DST, high latitudes, unsupported dates and repeated transit contacts. | Core | Acceptance catalog records the required edge scenarios and outcomes. |
| EVAL-003 | Measure required-family/exception recall, ranking, cross-school contamination, citation entailment, unknown handling, latency and resource consumption. | Core | Baseline and changed-system results use the same versioned benchmark. |
| EVAL-004 | Require zero observed authorization leaks, valid required references and passing critical deterministic/applicability fixtures in the release suite. Set numeric tolerances, retrieval/answer targets and p95 objectives before production sign-off. | Core | Release manifest links the acceptance profile and passing report; unset targets block production sign-off. |
| EVAL-005 | Split cases/persons/sources to prevent answer leakage; keep illustrative cases separate from held-out outcome evaluation. | Core | Test outcomes cannot be retrieved as if they were prospective predictions. |
| EVAL-006 | Evaluate predictive-validity claims separately, if pursued, using predefined outcomes/windows, timestamped predictions, verified outcomes and baselines. | Optional research | A cited-answer benchmark alone cannot support a predictive-validity claim. |

Required end-to-end scenarios include: a chart-backed career question; a period/transit window crossing; BNN versus Parashari with a relevant disagreement; a contemporary author mapping; a Puranic variant; an image with missing degrees; an uncertain-time chart crossing a relevant boundary; a draft rule with an exception; budget exhaustion; a failed calculation tool; a source update/deletion; and an unauthorized follow-up source fetch. Each scenario records expected facts, required evidence families, accepted abstentions and requirement IDs.

Proposed measured targets are intentionally not invented here. The production acceptance profile must set dataset/language slices, fixture tolerances, recall and citation targets, latency/concurrency, context/resource limits, freshness and deletion/retention deadlines before a production-ready claim. Development can proceed against the explicit invariant checks above.

## 10. Remaining configuration decisions

Exact source editions and reviewers, supported language order, numerical conventions/defaults, deployment hardware, provider policy, performance/resource targets and expansion sequencing remain configurable decisions. They do not reopen whether chart-backed retrieval is part of the core objective. Specific choices and their rationale belong in the design or versioned deployment/source manifests.
