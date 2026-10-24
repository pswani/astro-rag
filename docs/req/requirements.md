# Jyotish Agentic RAG — Requirements

| | |
|---|---|
| **Status** | Baseline (rev 3, input scope revised) |
| **Date** | 2026-10-18 |
| **Supersedes** | `rag-cl.md` and `rag-gpt.md` (both removed; see git history) |
| **Review log** | [review.md](review.md): conflicts resolved, rabbit holes removed, ID mapping |
| **Extensions** | [memory.md](memory.md): what the application remembers (refines AGT-5, AGT-6, QRY-6, NFR-2, NFR-6) |
| **Memory** | [memory.md](memory.md): memory stores, use cases and MEM-* requirements (refines AGT-5, QRY-6, NFR-6) |
| **Design** | [design.md](../design/design.md) (rev 5; traces every requirement in §22) |

This document says **what** the system must do and **how acceptance is shown**. The design says **how** it is built. Frameworks, database products, model names, chunk sizes and retrieval counts are design decisions, not requirements. Every requirement has a stable ID that design sections, rule cards, tests and evaluation cases can refer to.

### Priority, phase and release tier

| Pri | Meaning |
|---|---|
| **M** | Must have by the phase listed. Blocks that phase's exit. |
| **S** | Should have. Delivered in the listed phase if possible; does not block exit. |
| **C** | Could have. Not planned. Picked up only with a separate decision. |

**Phase** refers to the delivery plan (design §20; phases 1–7 are used here, and phase 8 optimization is not a place to defer any **M** item).

**Release tiers** follow from priority and phase:

- **Core release** = every **M** item in phases 1–6. This is the first release that satisfies the question-plus-chart objective. A search-only build does not.
- **Expansion** = phase 7 items. Each method or use case is activated as a separately validated bundle. A bundle that is not active is reported as unsupported. It is never emulated by another school.
- **Optional** = **C** items. Not required for the Indian-astrology baseline.

---

## 1. Purpose

Build the knowledge, calculation and retrieval layer for an agentic Indian astrology application. Given a user's **question** and **birth data**, the system:

1. Calculates the chart facts the question depends on.
2. Retrieves the relevant, cited knowledge for the selected astrological methods.
3. Decides deterministically which retrieved rules apply to this chart.
4. Hands an agentic LLM a structured **evidence bundle** for synthesis.

It also answers concept, source-comparison and story questions without a personal chart.

"All relevant knowledge" means **complete coverage of the question's declared dependencies**: the required facts, rule families, exceptions and contrary evidence for the selected methods, within resource limits. It does not mean returning the whole corpus. The system exposes gaps and truncation. It never claims completeness just because a top-k search finished.

## 2. Scope

### 2.1 Astrological methods

| Method / school | Description | Tier | Phase |
|---|---|---|---|
| **Parashari** | Classical Vedic natal astrology (BPHS lineage), one declared profile | Core | 1–4 |
| **BNN** | Bhrigu Nandi Nadi as published by R. G. Rao. Later lineages are labelled separately | Core | 5 |
| **Contemporary Indian** | Named contemporary authors' interpretations and declared hybrid techniques, labelled as modern commentary | Core (S) | 6 |
| **Jaimini** | Chara karakas, arudhas, rashi drishti, rashi dashas | Expansion | 7 |
| **KP** | Krishnamurti Paddhati: stellar sub-lords, significators, ruling planets, horary | Expansion | 7 |
| **Tajika / Varshaphala** | Annual charts | Expansion | 7 |
| **Prashna** | Horary (question-moment) astrology | Expansion | 7 |
| **Muhurta** | Electional astrology | Expansion | 7 |
| **Compatibility** | Ashtakoota, Dashakoota, Kuja dosha, two-chart comparison | Expansion | 7 |
| **Lal Kitab** | One declared edition | Optional | 7 |
| **Western / psychological** | Tropical zodiac, outer planets, orbs. Separate profile only | Optional | — |

"Vedic" is an umbrella label, not an executable rule set. **Modern** means contemporary Indian interpretation unless the Western profile is chosen explicitly.

### 2.2 Deployment scope (v1)

- **Local, single-operator deployment.** One operator runs the system on their own machine and may store charts for several people (self, family, clients). Multi-tenant accounts, per-user authorization and hosted service operation are out of scope for v1.
- **Interface:** a programmatic API (and CLI) that returns the evidence bundle and, optionally, a generated answer. An end-user UI is out of scope for this document.
- **Birth dates:** no fixed product-level year range. Preserve the entered date and calendar; Gregorian is the default when no calendar is specified. Use supported calendar converters or a user-supplied verified conversion. Calculation availability depends on the selected engine, installed data and requested feature, not an arbitrary date cutoff. An unavailable conversion or uncertain historical time is handled as missing/uncertain input; unsupported calculation features are reported individually without blocking unrelated knowledge retrieval.
- **Places:** worldwide place names or valid latitude/longitude, with no country preference or geographic exclusion. Accept coordinates and an explicit time-zone identifier or documented time standard when place lookup is unavailable. Only ambiguous or insufficient inputs require clarification. A selected calculation that is undefined for an input returns an explicit feature-level status; other supported features and knowledge retrieval remain available.

### 2.3 Out of scope

- Palm-leaf (Nadi leaf) consultation, other Nadi texts (Deva Keralam, Chandra Kala Nadi, …), numerology, palmistry, vastu.
- Fixed-star (individual star) astrology. Nakshatras are handled as 13°20′ sectors only.
- Birth-time rectification. The system never silently changes a birth time.
- Claims of empirical predictive validity.
- Selling remedies, gemstones or services.

## 3. Definitions

| Term | Meaning |
|---|---|
| **Calculation profile** | A versioned set of numerical conventions: zodiac, ayanamsa, house system, node model, varga variants, dasha variant and year length, sunrise definition, ephemeris version. |
| **Method profile** | A school/lineage plus its reviewed interpretation conventions. Each method profile names a default calculation profile; the two are linked but not identical. |
| **Chart fact** | A computed value (e.g., Saturn in Aries, 10th house, Bharani pada 2, retrograde) tied to a calculation profile, an input set and a reference point. |
| **Rule card** | One source-attributed rule: conditions as a machine-checkable predicate, the interpretation, qualifiers and exceptions, plus the source locator. |
| **Applicability** | The result of evaluating a rule card against chart facts: `satisfied`, `not_satisfied` or `unknown`. |
| **Topic map** | Per method, the mapping from a question domain (career, marriage, …) to the chart factors and rule families it needs. Topic maps are routing aids, not predictive rules. |
| **Dependency plan** | For one question: the facts to compute and the rule families to evaluate, derived from the topic map. |
| **Evidence bundle** | The typed package handed to the synthesizer (contract in AGT-3). It can be used without any generated prose. |
| **Evidence class** | One of: astronomical fact, traditional rule, commentary, narrative, reported case. |
| **As-of date** | The timestamp against which "now", "next year" and active dashas or transits are resolved. |

## 4. Use cases

| ID | Use case | Example | Acceptance scenario | Tier | Phase |
|---|---|---|---|---|---|
| UC-1 | Concept question | "What does the Navamsha signify?" "What is a tithi?" | Cited definitions; no birth data requested | Core | 2 |
| UC-2 | Natal reading on a topic | "What does my chart say about career?" | Relevant chart facts plus applicable, source-backed rules and contrary factors | Core | 3 |
| UC-3 | Timing question | "What will my Saturn–Venus period bring?" "Is a job change likely in the next 12 months?" | Actual active/overlapping periods; promise, period and trigger reported separately | Core | 4 |
| UC-4 | Method-specific reading | "Read my marriage prospects using BNN." | Only BNN evidence used | Core | 5 |
| UC-5 | Cross-method comparison | "How do Parashari and BNN differ on my career?" | Separately attributed bundles; differences preserved, not blended | Core | 5 |
| UC-6 | Story / symbolism | "Why does Rahu swallow the Moon?" "Story of Rohini nakshatra." | Source episode, variants and later associations separately attributed | Core | 6 |
| UC-7 | Contemporary interpretation | "How do modern astrologers read the 11th house for career?" | Named author; modern mappings labelled as such | Core (S) | 6 |
| UC-8 | Follow-up | "And my D10?" | Stored chart reused without re-entry; changed topic/time/method re-planned | Core | 3 |
| UC-9 | Remedy | "What remedies are traditionally given for Sade Sati?" | Original prescription with attribution and contraindications; no invented efficacy | Expansion | 7 |
| UC-10 | Compatibility | "Match these two charts." | Both charts validated; scoring variant named | Expansion | 7 |
| UC-11 | Muhurta | "Pick a date to open a shop in Pune next month." | Candidate intervals ranked against declared constraints | Expansion | 7 |
| UC-12 | Prashna / horary | "Will I get this job?" | Question-moment chart and a named method used | Expansion | 7 |
| UC-13 | Annual chart | "What does my Varshaphala for this year show?" | Validated Tajika calculations and evidence | Expansion | 7 |

## 5. Functional requirements

### 5.1 Inputs (INP)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| INP-1 | Accept birth date with its calendar (Gregorian by default), local clock time and worldwide birth place (name or coordinates), without fixed year or country restrictions. Resolve place names with a gazetteer; preserve supplied coordinates when lookup is unavailable and record provenance, with a location ID when available. Record any calendar conversion and its provenance; use a configured converter or request a verified converted date rather than inventing a conversion. Ask when inputs are ambiguous or insufficient. | M | 1 | Worldwide and pre-1900/post-2100 fixtures reach capability checks without a product-level rejection; ambiguous place prompts; coordinates bypass lookup; calendar-conversion provenance is retained. |
| INP-2 | Resolve the time-zone offset and DST for the entered date using a pinned IANA database or an explicit, documented historical time standard. Never apply today's offset. Use case-by-case ambiguity handling, with no country-wide historical-year prompt. Record the resolved instant, source and assumptions; clarify a DST fold/gap or a material unresolved historical ambiguity and mark dependent facts unknown when it cannot be resolved. | M | 1 | Fold/gap fixtures do not silently produce a chart; an older birth with an established time standard proceeds without an age-based prompt; unresolved assumptions remain visible. |
| INP-3 | Record birth-time precision and provenance (certificate, family memory, rounded, unknown) and an uncertainty interval. A fully unknown time is allowed: Lagna-dependent facts become `unknown` and Moon-based analysis proceeds. | M | 1 | Unknown-time fixture yields a Chandra-lagna reading with Lagna facts marked `unknown`. |
| INP-4 | Accept question text, an explicit or default as-of date, the user's time zone, an optional time window and an optional current location (for transits, muhurta and prashna). | M | 1 | — |
| INP-5 | Accept the selected method(s). When none is given, use the configured default (Parashari) and say so in the answer. | M | 1 | Answer states the default used. |
| INP-6 | Accept a second person's birth data for compatibility, with that person's consent recorded. | S | 7 | — |
| INP-7 | Import a chart from structured files (e.g., JSON export) with declared settings. Keep field-level provenance, never invent missing degrees, keep both versions when birth data is also given and explain any mismatch. **Image extraction is C (Optional).** | S | 7 | Missing degrees stay `unknown`; mismatch fixture shows both values. |
| INP-8 | Do not require name, caste, religion or gender to calculate. Where a method uses a gender-specific karaka (e.g., BNN Jupiter vs Venus as the native), ask for it as an explicit, optional method input. | M | 1 | Basic chart calculation works without those fields. |
| INP-9 | Ask only for inputs the question needs. Concept and story questions never request birth data. | M | 2 | A tithi-definition question does not request birth data. |

### 5.2 Calculation core (CALC)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| CALC-1 | Compute sidereal longitude, latitude, speed and retrograde status for Sun through Saturn, Rahu and Ketu, plus the Lagna. | M | 1 | NFR-1 tolerances. |
| CALC-2 | For each body, derive sign, degree, nakshatra, pada, nakshatra lord, house (per profile), dignity, combustion, planetary war, gandanta, sandhi and vargottama. Thresholds that differ between sources (e.g., combustion orbs) are profile settings. | M | 1 | Expert-reviewed fixtures. |
| CALC-3 | Support named, versioned calculation profiles: ayanamsa (Lahiri default; Raman, KP, True Chitra), house system (whole-sign, Sripati/bhava chalit, Placidus for KP), mean or true nodes. Every computed artifact references its profile. Never silently use a different profile; an unsupported setting returns an explicit status. | M | 1 | Two profiles on one chart keep distinct profile IDs. |
| CALC-4 | Compute houses from alternative reference points (Lagna, Chandra lagna, Surya lagna, and any planet for BNN/bhavat-bhavam), with the reference point recorded on each fact. | M | 3 | — |
| CALC-5 | Compute upagrahas (Gulika, Mandi, Dhuma and the rest) and special lagnas (Hora, Ghati, Bhava, Indu, Sri). | S | 7 | — |
| CALC-7 | For birth-time-sensitive facts, compute the time shift that would change them, by solving for the boundary crossing (not by sampling the interval's endpoints). Scope: Lagna sign and nakshatra, Moon nakshatra and pada, house placements, D9/D10 Lagna, and dasha boundaries. Report each fact as `stable`, `sensitive` or `unknown` for the recorded uncertainty interval. | M | 3 | A fixture that crosses and re-crosses a boundary inside the interval is not labelled stable. |
| CALC-8 | Calculate on demand and cache by (inputs, profile, engine version). Do not precompute every technique for every chart. | M | 1 | — |
| CALC-9 | Calculations are deterministic: the same inputs and profile give identical outputs, with engine and data versions recorded. | M | 1 | Re-run fixture is byte-identical. |

*(CALC-6 was merged into SCH-WES-1.)*

### 5.3 Panchanga (PAN)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| PAN-1 | Compute the five limbs at birth: tithi (with paksha), vara, nakshatra, nitya yoga, karana, each with its start and end times. | M | 1 | Boundary fixtures include adjacent instants. |
| PAN-2 | Compute local sunrise and sunset under a declared definition, and assign the vara by the sunrise convention. | M | 1 | Birth before sunrise fixture assigns the previous vara. |
| PAN-3 | Compute lunar month (**amanta by default**, purnimanta per profile), adhika/kshaya months, samvatsara, ayana and ritu. | S | 4 | Adhika-month fixture. |
| PAN-4 | Compute daily muhurta intervals: Rahu Kalam, Yamaganda, Gulika Kalam, Abhijit, Choghadiya, hora lords. | S | 7 | — |

*(PAN-5 was merged into KNW-12.)*

### 5.4 Divisional charts (VAR)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| VAR-1 | Compute D1, D9 and D10. | M | 1 | — |
| VAR-2 | Compute the remaining Shodashvarga (D2, D3, D4, D7, D12, D16, D20, D24, D27, D30, D40, D45, D60) using **one declared Parashari construction per varga**. | S | 4 | — |
| VAR-4 | Alternative varga constructions as named variants, only when an active rule family needs them. | S | 7 | Variant fixtures keep distinct outputs. |
| VAR-3 | Expose varga amsha deities (e.g., D60 amshas) as lookups. | C | — | — |

### 5.5 Relationships and strength (REL, STR)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| REL-1 | Compute lordships, occupants, dispositor chains, conjunctions, sign exchanges (parivartana) and Parashari graha drishti, including special aspects. | M | 1 | — |
| REL-2 | Compute natural, temporal and compound (panchadha) friendships, and functional benefic/malefic status per lagna. Keep natural nature, functional role, dignity and strength as separate properties. | M | 3 | — |
| REL-3 | Store each relationship as a typed edge with its aspect system, reference frame and counting convention, so that "2nd from Venus" is unambiguous. | M | 3 | — |
| STR-1 | Compute Ashtakavarga (BAV and SAV) with component tables. | S | 4 | — |
| STR-2 | Compute Shadbala and Bhava Bala with components and units. | S | 4 | — |
| STR-3 | Compute avasthas (Baladi, Jagradadi, Lajjitadi), Vimshopaka, and Ishta/Kashta Phala. | C | — | — |

### 5.6 Dashas (DAS)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| DAS-1 | Compute Vimshottari as a tree (mahadasha → antardasha → pratyantardasha) with UTC boundaries, birth balance and the year-length convention recorded. Sookshma is S; prana is not required. | M | 1 | Parent/child boundary fixtures. |
| DAS-2 | Return the active period chain at the as-of date, and every period that overlaps a requested window. | M | 4 | Interval-overlap fixtures. |
| DAS-3 | Support other systems as separate, validated specifications, each with its own eligibility rules: Yogini, Ashtottari (Parashari); Chara, Narayana (Jaimini); Mudda (Tajika). Kalachakra is C. | S | 7 | — |
| DAS-4 | Flag dasha sandhi (period junctions) and dasha boundaries that move under birth-time uncertainty (CALC-7). | S | 4 | — |
| DAS-5 | Interpret a dasha from the **condition of the period lord in this chart** (placement, lordships, dignity, strength, relationships, karakatva) plus the sub-period lord's relationship to it. Generic "Saturn mahadasha" text alone is not enough. | M | 4 | Timing eval (EVAL-7). |

### 5.7 Transits and planetary movements (TRN)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| TRN-1 | Compute transit positions at the as-of date relative to natal Lagna, Moon and natal planets. | M | 4 | — |
| TRN-2 | Search a time window for events: sign ingresses, nakshatra and pada crossings, retrograde and direct stations, conjunctions with natal points, and returns. Keep every crossing of a retrograde loop. | M | 4 | Retrograde-loop fixture returns all three crossings, not a daily sample. |
| TRN-3 | Detect named transit states: Sade Sati (with phase), Ashtama Shani, Kantaka Shani, Jupiter's transit from the Moon, the Jupiter–Saturn double transit, and the Rahu–Ketu axis over natal points. | M | 4 | — |
| TRN-4 | Apply gochara vedha and Ashtakavarga transit scoring (bindus, kakshya). | S | 4 | — |
| TRN-5 | Compute solar and lunar eclipses and their contact with natal points. | S | 4 | — |
| TRN-6 | Compute the BNN transit triggers: Jupiter, Saturn and the nodes over natal planets and their trines. | M | 5 | — |
| TRN-7 | Compute the Sarvatobhadra Chakra. | C | — | — |

### 5.8 Method-specific features (SCH)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| SCH-BNN-1 | For each planet, compute planets in trines (1/5/9), 2nd, 12th and 7th from it, exchanges and conjunctions. Treating retrograde planets as also in the previous sign is a variant flag in the BNN profile. | M | 5 | — |
| SCH-BNN-2 | Model BNN natural significators as method-specific karaka roles: Jupiter = the male native (jiva), Venus = wife or the female native, Saturn = karma/career, Mars = brother/land, Moon = mother, Sun = father, Mercury = intellect/trade, Rahu/Ketu. Keep these apart from Parashari karakatva. | M | 5 | — |
| SCH-BNN-3 | Separate R. G. Rao's published statements from later teachers' additions and from case-derived generalizations (`lineage` field). | M | 5 | — |
| SCH-JAI-1 | Compute chara karakas (7- and 8-karaka variants), karakamsha, arudha padas (AL, UL, A7, A10 and the rest), argala/virodha argala and rashi drishti. Never substitute Parashari aspects. | S | 7 | — |
| SCH-KP-1 | Compute Placidus cusps and the star lord, sub lord and sub-sub lord of every cusp and planet; four-level significators; ruling planets; horary numbers 1–249. | S | 7 | — |
| SCH-TAJ-1 | Compute the solar-return chart, Muntha, the year lord (Varshesha), Tajika aspects and yogas, Sahams and Mudda dasha. | S | 7 | — |
| SCH-PRS-1 | Build a chart for the question moment and place, with the method's question-validity rules. Do not silently reuse natal rules. | S | 7 | — |
| SCH-MUH-1 | Search a date window at a given place for intervals that meet activity-specific constraints: tara bala, chandra bala, panchaka, doshas, lagna suddhi. Rank the candidates with reasons. | S | 7 | — |
| SCH-CMP-1 | Compute Ashtakoota (36 points) and Dashakoota with each koota's score, Kuja dosha with its cancellations, and Nadi/Bhakoot doshas. Preserve regional variants and never merge unlike scoring systems. | S | 7 | — |
| SCH-LK-1 | Compute the Lal Kitab fixed-house chart, pakka ghar, soya ghar, rin and varshphal rotation per the declared edition. | C | — | — |
| SCH-WES-1 | Western profile: tropical zodiac, Uranus/Neptune/Pluto, aspects with orbs, returns and progressions. Never mixed into Indian methods. | C | — | — |

### 5.9 Knowledge content (KNW)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| KNW-1 | **Entity reference** (ontology) for: 9 grahas, 12 rashis, 12 bhavas, 27 nakshatras (+ Abhijit variant) and 108 padas, 30 tithis, 7 varas, 27 nitya yogas, 11 karanas, vargas, yogas/doshas, dasha systems, upagrahas and special lagnas, karaka schemes per method, deities, topics and methods. Each entity has aliases in Sanskrit, IAST, Devanagari, English and Hindi. Regional-language aliases are S, phase 6. | M | 1 | Ontology reviewed by an astrologer. |
| KNW-2 | **Graha attributes:** nature, gender, element, guna, varna, karakatva, body parts, diseases, professions, relatives, dignities (with degrees), moolatrikona, own signs, special aspects, dig bala, natural friendships, maturity age, deity, colour, metal, gem, grain, day, direction, mantras. Disputed values carry their source. | M | 1 | — |
| KNW-3 | **Rashi attributes** (lord, modality, element, gender, direction, body part, classifications); **bhava attributes** (significations, karakas, groupings: kendra, trikona, dusthana, upachaya, maraka, moksha; bhavat-bhavam); **nakshatra attributes** (boundaries, lord, deity, symbol, shakti, gana, yoni, nadi, varna, naming syllables). | M | 1 | — |
| KNW-4 | **Panchanga element meanings:** results of birth in each tithi, vara, nitya yoga and karana; tithi groups (Nanda, Bhadra, Jaya, Rikta, Purna) and deities. | M | 2 | — |
| KNW-5 | **Rule families**, each as rule cards linked to source passages. Core (Parashari, phases 3–4): (a) graha in rashi; (b) graha in bhava; (c) bhava lord in bhava (12×12); (d) graha in nakshatra; (e) conjunctions; (f) aspects; (g) a **curated, expert-chosen set of 20–30 yogas/doshas** with their cancellations; (h) dasha and antardasha results; (i) transit results. Core (BNN, phase 5): (j) BNN combinations and transit triggers. Review is ordered by topic: phase 3 covers the cards reached by the career, marriage and education topic maps, and the remaining Core cards are reviewed by the end of phase 6 (design §10.7). Expansion (phase 7): (k) KP house-group rules per event; (l) Jaimini, Tajika, compatibility, muhurta rules. More yogas are added only through the review workflow, never in bulk. | M | 3–6 | Each family has positive, negative and `unknown` fixtures (EVAL-4). |
| KNW-6 | **Topic maps** per Core method for: career, wealth, marriage/relationships, children, education, health (traditional framing), property, siblings, parents, foreign travel/residence, spirituality. (Vehicles and litigation are S.) Topic maps may surface additional prerequisites found during retrieval. | M | 3 | Career query shows a dependency checklist. |
| KNW-7 | **Puranic and devotional narratives** at episode level, with work, recension, book/canto, chapter, verse range, edition and variants. Store separately: what the story says; who links it to a graha, nakshatra or theme; and any practice or prediction derived from it. Story evidence alone never justifies a personal prediction. | M | 6 | — |
| KNW-8 | **Remedies** (mantra, stotra, dana, vrata, yantra, gemstone, rudraksha, temple), each with source, prerequisites, **contraindications** (e.g., do not wear the gem of a functional malefic), and any efficacy claim attributed to its source. | S | 7 | — |
| KNW-9 | **Worked cases:** chart facts, method, cited rules, the prediction as originally made, the reported outcome and its provenance, and a data-quality rating. A worked example is never labelled a verified outcome without outcome evidence. | S | 5 | — |
| KNW-11 | **Calculation reference knowledge** (dasha durations, varga division rules, Ashtakavarga tables) lives in the ontology/calculation specifications and is cited to its source table. Calculation never retrieves it from the vector index. | M | 1 | — |
| KNW-12 | Keep confusable concepts distinct in the ontology, tags and answers: **nitya yoga** (panchanga limb) vs **yoga** (chart combination); **nadi** koota vs Nadi astrology; BNN vs other Nadi texts; signs vs houses; nakshatra sectors vs individual stars. | M | 1 | Ambiguous-term fixtures resolve or ask without merging entities. |

### 5.10 Sources and ingestion (ING)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| KNW-10 | Register every source in an **acquisition register** before ingestion: title, author, editor/translator, publisher, edition/year, language/script, ISBN or catalog ID, source URI, rights status, coverage, OCR condition, reviewer and status (`candidate`, `acquired`, `parsed`, `reviewed`, `published`). | M | 1 | Every retrieved passage resolves to its registered edition. |
| ING-8 | **Core source set:** one identified BPHS edition/translation (phase 2), R. G. Rao's *Bhrigu Nandi Nadi* (phase 5), Puranic sources for the Core story set (phase 6) and 1–2 named modern authors (phase 6). Other works enter only with a phase-7 bundle or a separate decision. | M | 2 | — |
| ING-1 | Parse Markdown, text/HTML, native and scanned PDF and Office documents into one intermediate representation that keeps headings, lists, tables, page numbers and verse numbers. Mark extraction failures. | M | 2 | Representative corpus keeps page order, table headers and numbers. |
| ING-2 | OCR scanned pages in Devanagari and Latin scripts. Score quality per page, and send low-quality pages to a VLM or a review queue instead of indexing them. | M | 2 | — |
| ING-3 | Chunk by content unit: verse (with translation and commentary), section, story episode, table (with header), rule card, remedy, worked case. Keep links between a rule, its prerequisites, exceptions, tables and explanations. | M | 2 | An exception stays reachable when its rule is retrieved. |
| ING-9 | Keep stable locators (printed page, verse, chapter) distinct from file indices, and keep verified translation/commentary alignment. | M | 2 | Locators still resolve after reindexing. |
| ING-4 | Tag every chunk with ontology entity IDs, topics, school, lineage, method variant, reference frame, chart scope (varga), rule family and evidence class. | M | 2 | — |
| ING-5 | Extract candidate rule cards from text with an LLM. A rule card becomes executable only after review by an expert for that method. Ambiguous prose stays as source text; machine-proposed cards, generated summaries and teaching analogies are never cited as source evidence. | M | 3 | A draft card cannot enter the approved predicate set or be cited. |
| ING-6 | Ingestion is idempotent and incremental and builds a versioned index. Updates and withdrawals propagate to passages, rule cards, links and caches. Ontology changes trigger re-tagging. | M | 2 | Unchanged re-ingestion duplicates nothing; withdrawn evidence disappears from new queries. |
| ING-7 | Never index sources whose rights status is `restricted` into anything distributed. | M | 2 | — |

### 5.11 Question understanding and planning (QRY)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| QRY-1 | Classify intent: concept, natal topic reading, timing, method-specific reading, comparison, story, contemporary interpretation, remedy, compatibility, muhurta, prashna, annual. Route intents whose bundle is not active to an `unsupported` response. | M | 2 | — |
| QRY-2 | Extract the topic(s), entities, method(s), as-of date, time window, and whose chart is meant (the native, or a relative via bhavat-bhavam). | M | 3 | — |
| QRY-3 | List missing inputs (e.g., birth time for a timing question) and either ask for them or proceed with the limitations stated. | M | 3 | — |
| QRY-4 | Expand each topic into the required chart factors for each selected method using the topic map, producing a **dependency plan**. Compute only those facts. | M | 3 | — |
| QRY-5 | Resolve relative times ("now", "next year") against the recorded as-of date and the user's time zone. | M | 4 | Fixtures resolve reproducibly. |
| QRY-6 | For follow-ups, reuse the stored chart and re-plan when the time, method, chart or topic changes. | M | 3 | Follow-up fixture uses the intended chart and drops stale assumptions. |

### 5.12 Rule applicability (APP)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| APP-1 | Evaluate the conditions of every rule card in the planned rule families against chart facts deterministically. The LLM never decides whether a rule or yoga is present. | M | 3 | — |
| APP-2 | Applicability has three states: `satisfied`, `not_satisfied`, `unknown`. Missing degrees, an unknown birth time, a `sensitive` fact or an uncomputed feature give `unknown`, never `not_satisfied`. | M | 3 | Positive, negative and unknown fixtures pass. |
| APP-3 | Evaluate the cancellation, qualification and exception rules linked to each satisfied rule, to a bounded depth. Keep the original formation result alongside the qualified one. Detect cycles and report them as `unknown`. | M | 3 | Cancellation and cyclic-dependency fixtures. |
| APP-4 | For dasha and transit questions, apply the three-step test: does the natal chart **promise** the event, does the **dasha** activate it, does a **transit** trigger it? Report each step separately. | M | 4 | EVAL-7. |
| APP-5 | Log the facts and rule-card versions used, the outcome of each condition, and why each candidate rule was accepted, rejected or left unknown. | M | 3 | A reviewer can replay a decision without model reasoning. |

### 5.13 Retrieval (RET)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| RET-1 | Retrieval is **hybrid**: (a) fetch the passages linked to applicable rule cards by ID; (b) entity-filtered lexical + semantic search; (c) exact lookup by verse, entity or rule ID; (d) ontology expansion (nakshatra lord, dispositor, house lord, karaka). | M | 3 | Exact verse, transliterated alias and numeric conditions each retrieve correctly. |
| RET-2 | Filters on entities, school, method variant, doc type, evidence class and licence run **inside** the search, not after it. | M | 2 | — |
| RET-3 | Retrieval for a chart factor must not confuse factors (e.g., "Saturn in the 10th" vs "10th lord in Saturn's sign" vs "10th from the Moon"). | M | 2 | Factor-confusion fixtures. |
| RET-4 | Aliases are normalized to entity IDs before search: queries that differ only by alias (Shani / Sani / Saturn / शनि) return the same results. | M | 2 | Alias fixture returns identical top-k. |
| RET-5 | Retrieve passages for each active dasha lord and sub-lord in the context of its natal condition, and for each transit event in the window. | M | 4 | — |
| RET-6 | Explicitly search for **contrary evidence**: mitigations, cancellations and opposing readings for each main finding. | M | 3 | Benchmark includes the exception and the adverse reading. |
| RET-7 | Check coverage against the dependency plan. If a required rule family or fact is missing, do a targeted retry within the RET-11 budget, and report any gap that remains. | M | 3 | — |
| RET-8 | Method isolation: a BNN analysis retrieves only BNN-tagged (or method-neutral definitional) material unless the user requests a named hybrid. The same holds for every method. In a comparison, each method is retrieved separately so a larger corpus cannot crowd out a smaller one. | M | 5 | Contamination rate (EVAL-3). |
| RET-9 | Stories and remedies come only through their own routes, so their lexical richness cannot crowd rule evidence out of predictive retrieval. | M | 6 | — |
| RET-10 | Retrieve relevant worked cases as illustrations, labelled as such. | S | 5 | — |
| RET-11 | Bound tool calls, retries, dependency depth, elapsed time and context size per question. When a bound is hit, return a `partial` result naming the omitted evidence categories. When context is trimmed, keep qualifiers and exceptions, or mark the affected conclusion incomplete. | M | 3 | Forced-budget fixture returns `partial` with gaps listed. |
| RET-12 | Handle empty retrieval, unsupported methods, tool failures and contradictory sources explicitly. Never replace missing evidence with model-generated content. | M | 3 | Failure fixtures yield missing-evidence records. |

### 5.14 Agent and synthesis (AGT)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| AGT-1 | Calculation, rule evaluation and filtering are deterministic tools, not LLM calls. The LLM plans, retrieves via tools and synthesizes. | M | 3 | — |
| AGT-2 | When more than one method is selected, each method is analysed only over its own evidence bundle before any comparison. | M | 5 | — |
| AGT-3 | The **evidence bundle** is a typed, machine-readable object containing: resolved question scope; input and chart provenance; method and calculation profiles; relevant facts, periods and events (with sensitivity); applicable and `unknown` rules with qualifiers; contrary evidence; passages with excerpts and precise locators; cases; gaps; and versions. It is produced independently of answer generation. | M | 3 | Schema validator rejects dangling references and missing per-method records. |
| AGT-5 | Store per-person birth data, profiles and computed charts so that follow-ups need no re-entry (UC-8). | M | 3 | — |
| AGT-6 | Treat retrieved text and imported files as data, never as instructions. Tool permissions and rule publication are outside the model's control. | M | 2 | Prompt-injection fixture cannot change tools, publish rules or read another person's chart. |

*(AGT-4 is a design choice and moved to the design.)*

### 5.15 Answer (OUT)

| ID | Requirement | Pri | Ph | Acceptance |
|---|---|---|---|---|
| OUT-1 | Every interpretive claim in a generated answer cites a chart fact **and** a source passage or rule card (`[BPHS 24.12]`). | M | 2 | Citation entailment (EVAL-5). |
| OUT-2 | Facts such as dignities and lordships come from the ontology or calculation, never from model memory. | M | 1 | — |
| OUT-3 | Where methods or texts disagree, present each view with attribution. Do not present school agreement, similarity scores or model confidence as a probability of a life outcome. | M | 3 | — |
| OUT-4 | State the profile used (ayanamsa, house system, dasha variant), any default applied, and any birth-time sensitivity that affects the conclusion. | M | 3 | — |
| OUT-5 | Chart readings follow a fixed structure: inputs and profile → key placements → yogas → dasha context → transits → synthesis by method → contrary factors → gaps. | M | 3 | — |
| OUT-6 | Explicitly allow "not found in the sources" and "cannot be established with the given birth data". | M | 2 | — |
| OUT-7 | Answers are in English. Sanskrit terms are shown with IAST or Devanagari as configured. Hindi and Marathi answers are S, phase 7. | M | 2 | — |
| OUT-8 | Every result has a status: `complete` (for the declared dependencies), `partial`, `needs_input`, `unsupported` or `failed`. A mixed-method result keeps successful evidence alongside the failed method's status. | M | 3 | — |

## 6. Non-functional requirements (NFR)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| NFR-1 | **Accuracy** against a reference (Jagannatha Hora) under matched settings: discrete facts (sign, nakshatra, pada, house, varga sign, dasha lord sequence) match exactly, except for values within the tolerance below of a boundary; planet longitudes within 10″; Lagna within 30″; Vimshottari boundaries within 2 days. | M | EVAL-1 fixtures. |
| NFR-2 | **Reproducibility:** each answer records its corpus, rule-set, ontology, calculation and model versions. A query uses one consistent set of versions. | M | — |
| NFR-3 | **Latency (initial targets, revisable at phase exit):** concept questions p95 < 8 s; full chart reading p95 < 60 s with streaming partial output, on the reference deployment declared in the design. | S | Measured per release. |
| NFR-4 | **Index size:** total < 10 GB on a single node. | M | — |
| NFR-5 | **Local-first:** every component runs locally. The LLM is configurable (local, or an API). A fully local mode with no network egress must work end to end. | M | Egress-denied run passes. |
| NFR-6 | **Privacy:** birth data is personal data. Store it encrypted and locally, keep it out of the shared knowledge index, redact it from logs and traces, and support deleting a person's data from the store, caches and logs. Birth date, time and place are never sent to an external API; computed chart facts are sent to an API LLM only when that mode is explicitly enabled. | M | Deletion fixture; log redaction check. |
| NFR-7 | **Licensing:** track rights per source and filter on them (ING-7, RET-2). Decide the Swiss Ephemeris licence (AGPL or commercial) before distributing the system. | M | — |
| NFR-8 | **Observability:** trace every step and tool call with durations, errors and versions. Run the evaluation suite on every change. | M | — |
| NFR-9 | **Extensibility:** add a new method by supplying a profile, features, ontology entries, rule cards, a topic map and eval cases, without changing core code paths. | S | Demonstrated by the first phase-7 bundle. |
| NFR-10 | **Failure handling:** bounded retries, resumable ingestion and explicit degraded states. Never substitute a different convention or method on failure. | M | Failed-tool fixture stays visible. |

## 7. Evaluation and acceptance (EVAL)

| ID | Requirement | Pri | Ph |
|---|---|---|---|
| EVAL-1 | **Calculation fixtures:** positions, Lagna, nakshatra/pada, panchanga boundaries, vargas, dasha balance and sub-periods, transit events. Edge cases: 0°/360° wrap, sector boundaries, DST folds and gaps, documented historical time standards, dates outside the former product range, worldwide coordinate input, calendar conversions, feature-specific engine/data limits, high latitudes, retrograde re-crossings, unknown birth time. | M | 1 |
| EVAL-2 | **Golden question set**, built with an astrologer: 50–200 questions across the Core use cases, covering aliases, conflicts, missing inputs and ambiguous terms. | M | 2 |
| EVAL-3 | **Retrieval metrics:** recall@k for required rule families and for exceptions/contrary passages, MRR, nDCG, and cross-method contamination rate. | M | 2 |
| EVAL-4 | **Applicability tests:** positive, negative and `unknown` cases for every rule card, including cancellations. | M | 3 |
| EVAL-5 | **Answer grounding:** faithfulness, citation entailment, correct chart facts, correct method labels, stated uncertainty, and no invented rules or dates. | M | 2 |
| EVAL-6 | **Chart readings** of reference charts, scored by an expert on a rubric covering factor coverage and correctness. | M | 3 |
| EVAL-7 | **Timing questions:** the correct dasha chain and transit events are identified, and promise/period/trigger are reported separately. | M | 4 |
| EVAL-9 | **End-to-end scenarios**, each recording expected facts, required evidence families, accepted abstentions and requirement IDs: a chart-backed career question; a timing window crossing a dasha boundary; BNN vs Parashari with a real disagreement; a modern-author mapping; a Puranic variant; an uncertain-time chart crossing a boundary; a draft rule with an exception; budget exhaustion; a failed calculation tool; a source withdrawal; a prompt-injection passage. | M | 3–6 |
| EVAL-10 | Keep calculation, extraction, retrieval, applicability and answer results separate, so a failure is attributable to one layer. Keep illustrative cases separate from any test data. | M | 2 |
| EVAL-8 | Outcome-prediction evaluation, if ever pursued, is prospective, uses held-out persons and predefined outcomes, and is kept separate from retrieval quality. | C | — |

**Phase exit:** a phase is accepted when its **M** items pass, its EVAL items meet targets agreed with the expert reviewer and recorded in the release notes, and earlier phases do not regress. Targets are set at the start of each phase, not deferred to a final production gate.

## 8. Safety and responsible use (SAFE)

| ID | Requirement | Pri |
|---|---|---|
| SAFE-1 | Frame longevity, maraka, illness, accidents and misfortune as traditional interpretation. Make no fatalistic, medical, legal or financial claims. Do not volunteer longevity or death-timing predictions. | M |
| SAFE-2 | Present remedies only on request, as traditional practices with attribution and contraindications. Never push purchases. | M |
| SAFE-3 | Never present compatibility scores as guarantees. Never frame Kuja or other doshas in a fear-inducing way. | M |
| SAFE-4 | Answers distinguish the evidence classes: astronomical fact, traditional rule, commentary, narrative and reported case. | M |
| SAFE-5 | Source authority is a property within a tradition, not evidence of predictive validity. Unverified web summaries may help find sources but never become rule cards directly. | M |

## 9. Constraints and assumptions

- Calculation uses Swiss Ephemeris (or a wrapper on it). Other technology choices belong to the design.
- An astrologer reviewer is available from Phase 1 for the ontology, rule cards, topic maps and the golden set. A BNN-competent reviewer is available by Phase 5.
- **BNN** means Bhrigu Nandi Nadi (R. G. Rao). Rao's text supports a distinct BNN relation model; it does not establish a single universal BNN algorithm, so BNN rules carry lineage (SCH-BNN-3).
- Catalog availability or a free download is not permission to ingest or redistribute an edition.

## 10. Traceability

Design [§22](../design/design.md#22-requirements-traceability) maps every requirement ID to its design section and verification.

## 11. Open questions

> The current, consolidated list with answers is [open-questions.md](open-questions.md); this table is kept for history.

| # | Question | Blocks |
|---|---|---|
| 1 | Which BPHS edition/translation and which BNN edition are licensed for ingestion? | Phases 2, 5 |
| 2 | Which 1–2 modern authors are in the Core source set? | Phase 6 |
| 3 | Who is the expert reviewer for Parashari and for BNN? | Phase 1, Phase 5 exits |
| 4 | Swiss Ephemeris licence: AGPL or commercial. | Distribution only (NFR-7) |
| 5 | Order of phase-7 bundles. | Phase 7 |

Resolved in this revision (see review §2): Western profile in v1 (no, Optional); remedies by default (no, on request); amanta vs purnimanta default (amanta); response languages (English first); Lal Kitab edition (deferred with Lal Kitab to Optional).
