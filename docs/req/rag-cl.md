# Jyotish Agentic RAG — Requirements

| | |
|---|---|
| **Status** | Draft (rev 1) |
| **Date** | 2026-10-17 |
| **Design** | [rag-claude.md](../design/rag-claude.md) (how these requirements are met) |
| **Companion** | [rag-gpt.md](../design/rag-gpt.md) (domain detail: input contract, calculation profiles, evidence bundle) |

This document says **what** the system must do. The design document says **how**. Every requirement has a stable ID so that design sections, rule cards, tests and evaluation cases can refer to it.

**Priority:**

| Code | Meaning |
|---|---|
| **M** | Must have for the phase listed |
| **S** | Should have |
| **C** | Could have |

**Phase** refers to the delivery plan in the design (§18).

---

## 1. Purpose

Build the knowledge and retrieval layer for an agentic Indian astrology application. Given a user's **question** and **birth data** (or an imported chart), the system:

1. Calculates the chart facts the question depends on.
2. Retrieves all relevant, cited knowledge for the selected astrological methods.
3. Decides which retrieved rules actually apply to this chart.
4. Hands an agentic LLM a structured evidence bundle for synthesis.

Relevant knowledge includes:
- Definitions, rules, exceptions and contrary views.
- Dasha and transit interpretations.
- Stories, remedies and worked cases.

"All relevant knowledge" means **complete coverage of the question's dependencies** within the selected methods and context budget. It does not mean returning the whole corpus.

## 2. Scope

### 2.1 Astrological methods

| Method / school | Description | Phase |
|---|---|---|
| **Parashari** | Classical Vedic natal astrology (BPHS lineage) | 1–4 |
| **BNN** | Bhrigu Nandi Nadi, as published by R. G. Rao, with later lineages labelled separately | 5 |
| **Jaimini** | Chara karakas, arudhas, rashi drishti, rashi dashas | 7 |
| **KP** | Krishnamurti Paddhati: stellar sub-lords, significators, ruling planets, horary | 7 |
| **Tajika / Varshaphala** | Annual charts | 7 |
| **Prashna** | Horary (question-moment) astrology | 7 |
| **Muhurta** | Electional astrology | 7 |
| **Compatibility** | Ashtakoota, Dashakoota, Kuja dosha, two-chart comparison | 7 |
| **Lal Kitab** | Edition-specific | 7 |
| **Modern Indian** | Named contemporary authors and hybrid methods, labelled as modern commentary | 6–7 |
| **Western / psychological** | Optional separate profile: tropical, outer planets, orbs | 7 (C) |

### 2.2 Out of scope

- Palm-leaf (Nadi leaf) consultation, numerology, palmistry, vastu.
- Claims of empirical predictive validity.
- Medical, legal or financial advice.
- Selling remedies, gemstones or services.

## 3. Definitions

| Term | Meaning |
|---|---|
| **Profile** | A versioned set of calculation conventions: ayanamsa, house system, node model, varga variants, dasha variant, sunrise definition, ephemeris version. Each method has a default profile. |
| **Chart fact** | A computed value (e.g., Saturn in Aries, 10th house, Bharani pada 2, retrograde) tied to a profile and an input set. |
| **Rule card** | One source-attributed rule: conditions as a machine-checkable predicate, the interpretation, qualifiers and exceptions, plus the source locator. |
| **Applicability** | The result of evaluating a rule card against chart facts: `satisfied`, `not_satisfied` or `unknown`. |
| **Topic map** | For each method, the mapping from a question domain (career, marriage, …) to the chart factors it needs: houses, lords, karakas, vargas, special points, KP cusps, BNN significators. |
| **Evidence bundle** | The typed package handed to the synthesizer: facts, applicable rules, qualifiers, contrary evidence, passages, cases, gaps and versions. |
| **As-of date** | The timestamp against which "now", "next year" and active dashas or transits are resolved. |

## 4. Use cases

| ID | Use case | Example | Phase |
|---|---|---|---|
| UC-1 | Concept question | "What does the Navamsha signify?" "What is a tithi?" | 2 |
| UC-2 | Natal reading on a topic | "What does my chart say about career?" | 3 |
| UC-3 | Timing question | "What will my Saturn–Venus period bring?" "Is a job change likely in the next 12 months?" | 4 |
| UC-4 | Method-specific reading | "Read my marriage prospects using BNN." | 5 |
| UC-5 | Cross-method comparison | "How do Parashari and BNN differ on my career?" | 5 |
| UC-6 | Story / symbolism | "Why does Rahu swallow the Moon?" "Story of Rohini nakshatra." | 6 |
| UC-7 | Remedy | "What remedies are traditionally given for Sade Sati?" | 6 |
| UC-8 | Compatibility | "Match these two charts." | 7 |
| UC-9 | Muhurta | "Pick a date to open a shop in Pune next month." | 7 |
| UC-10 | Prashna / horary | "Will I get this job?" (question-moment chart, KP or Prashna) | 7 |
| UC-11 | Annual chart | "What does my Varshaphala for this year show?" | 7 |
| UC-12 | Follow-up | "And my D10?" — reuses the stored chart without re-entry | 3 |

## 5. Functional requirements

### 5.1 Inputs (INP)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| INP-1 | Accept birth date, local clock time and birth place. Resolve the place to latitude/longitude using a gazetteer and record the resolved location ID. | M | 1 |
| INP-2 | Resolve the historical time-zone offset and DST from the IANA tz database for the birth date. Never apply today's offset. Ask the user when the local time is ambiguous or falls in a DST gap. | M | 1 |
| INP-3 | Record birth-time precision and provenance: certificate, family memory, rounded, rectified or unknown. Also record an uncertainty interval. | M | 1 |
| INP-4 | Accept question text, an explicit or default as-of date, an optional time window and an optional current location (needed for transits, muhurta and prashna). | M | 1 |
| INP-5 | Accept the selected method(s)/profile. When none is given, use a visible configured default (Parashari) and say so in the answer. | M | 1 |
| INP-6 | Accept a second person's birth data for compatibility, with that person's consent recorded. | S | 7 |
| INP-7 | Import a chart from structured files or from images (North, South or East Indian layouts). Keep field-level confidence, never invent missing degrees, and reconcile with calculated values when birth data is also given. | C | 7 |
| INP-8 | Do not require name, caste, religion or gender as calculation inputs. Where a method uses gender-specific karakas (e.g., BNN Jupiter vs Venus as the native), ask for it explicitly as an optional method input. | M | 1 |

### 5.2 Calculation core (CALC)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| CALC-1 | Compute sidereal longitude, latitude, speed and retrograde status for Sun through Saturn, Rahu and Ketu, plus the Lagna, using Swiss Ephemeris. | M | 1 |
| CALC-2 | For each body, derive sign, degree, nakshatra, pada, nakshatra lord, house (per profile), dignity, combustion, planetary war, gandanta, sandhi and vargottama. | M | 1 |
| CALC-3 | Support named, versioned calculation profiles: ayanamsa (Lahiri default; Raman, KP, True Chitra), house system (whole-sign, Sripati/bhava chalit, Placidus for KP), mean or true nodes. Every computed artifact references its profile. | M | 1 |
| CALC-4 | Compute houses from alternative reference points (Lagna, Chandra lagna, Surya lagna, and any planet for BNN/bhavat-bhavam), with the reference point recorded on each fact. | M | 3 |
| CALC-5 | Compute upagrahas (Gulika, Mandi, Dhuma and the rest) and special lagnas (Hora, Ghati, Bhava, Indu, Sri). | S | 7 |
| CALC-6 | Compute Uranus, Neptune and Pluto, tropical positions and Western aspects with orbs, **only** in the Western profile. | C | 7 |
| CALC-7 | Mark each fact with birth-time sensitivity: the time shift that would change it. When birth time is uncertain, report which facts are stable, which are sensitive and which cannot be established. | M | 3 |
| CALC-8 | Calculate on demand and cache by (inputs, profile, version). Do not precompute every technique for every chart. | M | 1 |
| CALC-9 | Calculations are deterministic and reproducible: the same inputs and profile give identical outputs, with engine and data versions recorded. | M | 1 |

### 5.3 Panchanga (PAN)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| PAN-1 | Compute the five limbs at birth: tithi (with paksha), vara, nakshatra, nitya yoga, karana. Also compute the start and end times of each. | M | 1 |
| PAN-2 | Compute local sunrise and sunset under a declared definition, and assign the vara by the sunrise convention. | M | 1 |
| PAN-3 | Compute lunar month (amanta/purnimanta per profile), adhika/kshaya months, samvatsara, ayana and ritu. | S | 4 |
| PAN-4 | Compute daily intervals for muhurta: Rahu Kalam, Yamaganda, Gulika Kalam, Abhijit, Choghadiya, hora lords. | S | 7 |
| PAN-5 | Keep **nitya yoga** (panchanga limb) distinct from **yoga** (chart combination), and the **nadi** koota distinct from Nadi astrology, in the ontology, tags and answers. | M | 1 |

### 5.4 Divisional charts (VAR)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| VAR-1 | Compute D1, D9 and D10. | M | 1 |
| VAR-2 | Compute the remaining Shodashvarga (D2, D3, D4, D7, D12, D16, D20, D24, D27, D30, D40, D45, D60), with alternative construction methods as named variants. | S | 4 |
| VAR-3 | Expose varga amsha deities (e.g., D60 amshas) as lookups. | C | 7 |

### 5.5 Relationships and strength (REL, STR)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| REL-1 | Compute lordships, occupants, dispositor chains, conjunctions, sign exchanges (parivartana) and Parashari graha drishti, including special aspects. | M | 1 |
| REL-2 | Compute natural, temporal and compound (panchadha) friendships, and functional benefic/malefic status per lagna. Keep natural nature, functional role, dignity and strength as separate properties. | M | 3 |
| REL-3 | Store each relationship as a typed edge with its aspect system, reference frame and counting convention, so that "2nd from Venus" is unambiguous. | M | 3 |
| STR-1 | Compute Ashtakavarga (BAV and SAV) with component tables. | S | 4 |
| STR-2 | Compute Shadbala and Bhava Bala with components and units. | S | 4 |
| STR-3 | Compute avasthas (Baladi, Jagradadi, Lajjitadi), Vimshopaka, and Ishta/Kashta Phala. | C | 7 |

### 5.6 Dashas (DAS)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| DAS-1 | Compute Vimshottari as a tree (mahadasha → antardasha → pratyantardasha → sookshma → prana) with UTC boundaries, birth balance and the year-length convention recorded. | M | 1 |
| DAS-2 | Return the active period chain at the as-of date, and every period that overlaps a requested window. | M | 4 |
| DAS-3 | Support other systems as separate, validated specifications, each with its own eligibility rules: Yogini, Ashtottari, Kalachakra (Parashari); Chara, Narayana (Jaimini); Mudda (Tajika). | S | 7 |
| DAS-4 | Flag dasha sandhi (period junctions) and dasha boundaries that move under birth-time uncertainty. | S | 4 |
| DAS-5 | Interpret a dasha from the **condition of the period lord in this chart** (placement, lordships, dignity, strength, relationships, karakatva) plus the sub-period lord's relationship to it. Generic "Saturn mahadasha" text alone is not enough. | M | 4 |

### 5.7 Transits and planetary movements (TRN)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| TRN-1 | Compute transit positions at the as-of date relative to natal Lagna, Moon and natal planets. | M | 4 |
| TRN-2 | Search a time window for events: sign ingresses, nakshatra and pada crossings, retrograde and direct stations, conjunctions with natal points, and returns. | M | 4 |
| TRN-3 | Detect named transit states: Sade Sati (with phase), Ashtama Shani, Kantaka Shani, Jupiter's transit from the Moon, the Jupiter–Saturn double transit, and the Rahu–Ketu axis over natal points. | M | 4 |
| TRN-4 | Apply gochara vedha and Ashtakavarga transit scoring (bindus, kakshya). | S | 4 |
| TRN-5 | Compute solar and lunar eclipses and their contact with natal points. | S | 4 |
| TRN-6 | Compute the BNN transit triggers: Jupiter, Saturn and the nodes over natal planets and their trines. | M | 5 |
| TRN-7 | Compute the Sarvatobhadra Chakra. | C | 7 |

### 5.8 Method-specific features (SCH)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| SCH-BNN-1 | For each planet, compute planets in trines (1/5/9), 2nd, 12th and 7th from it, with retrograde planets also treated as being in the previous sign (variant-flagged), exchanges and conjunctions. | M | 5 |
| SCH-BNN-2 | Model BNN natural significators as method-specific karaka roles: Jupiter = the male native (jiva), Venus = wife or the female native, Saturn = karma/career, Mars = brother/land, Moon = mother, Sun = father, Mercury = intellect/trade, Rahu/Ketu. Keep these apart from Parashari karakatva. | M | 5 |
| SCH-BNN-3 | Separate R. G. Rao's published statements from later teachers' additions and from case-derived generalizations (`lineage` field). | M | 5 |
| SCH-JAI-1 | Compute chara karakas (7- and 8-karaka variants), karakamsha, arudha padas (AL, UL, A7, A10 and the rest), argala/virodha argala and rashi drishti. | S | 7 |
| SCH-KP-1 | Compute Placidus cusps and the star lord, sub lord and sub-sub lord of every cusp and planet; four-level significators; ruling planets; horary numbers 1–249. | S | 7 |
| SCH-TAJ-1 | Compute the solar-return chart, Muntha, the year lord (Varshesha), Tajika aspects and yogas, Sahams and Mudda dasha. | S | 7 |
| SCH-LK-1 | Compute the Lal Kitab fixed-house chart, pakka ghar, soya ghar, rin and varshphal rotation per the chosen edition. | C | 7 |
| SCH-PRS-1 | Build a chart for the question moment and place, with the method's question-validity rules. Do not silently reuse natal rules. | S | 7 |
| SCH-MUH-1 | Search a date window at a given place for intervals that meet activity-specific constraints: tara bala, chandra bala, panchaka, doshas, lagna suddhi. Rank the candidates with reasons. | S | 7 |
| SCH-CMP-1 | Compute Ashtakoota (36 points) and Dashakoota with each koota's score, Kuja dosha with its cancellations, and Nadi/Bhakoot doshas. Preserve regional variants and never merge unlike scoring systems. | S | 7 |
| SCH-WES-1 | Western profile: tropical zodiac, outer planets, aspects with orbs, and returns/progressions as supported. Never mixed into Indian methods silently. | C | 7 |

### 5.9 Knowledge content (KNW)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| KNW-1 | **Entity reference** (ontology) for: 9 grahas (+3 outer for Western), 12 rashis, 12 bhavas, 27 nakshatras (+ Abhijit variant) and 108 padas, 30 tithis, 7 varas, 27 nitya yogas, 11 karanas, vargas, yogas/doshas, dasha systems, upagrahas and special lagnas, karaka schemes per method, deities, topics and methods. Each entity has multilingual aliases (Sanskrit, IAST, Devanagari, Hindi, English and selected regional names). | M | 1 |
| KNW-2 | **Graha attributes:** nature, gender, element, guna, varna, karakatva, body parts, diseases, professions, relatives, dignities (with degrees), moolatrikona, own signs, special aspects, dig bala, natural friendships, maturity age, deity, colour, metal, gem, grain, day, direction, mantras. Disputed values carry their source. | M | 1 |
| KNW-3 | **Rashi, bhava and nakshatra attributes** as listed in design §7, including bhava groupings (kendra, trikona, dusthana, upachaya, maraka, moksha), bhavat-bhavam, house karakas, and nakshatra lord, deity, symbol, shakti, gana, yoni, nadi, varna and naming syllables. | M | 1 |
| KNW-4 | **Panchanga element meanings:** results of birth in each tithi, vara, nitya yoga and karana; tithi groups (Nanda, Bhadra, Jaya, Rikta, Purna) and deities. | M | 2 |
| KNW-5 | **Rule families**, each as rule cards linked to source passages: (a) graha in rashi; (b) graha in bhava; (c) bhava lord in bhava (12×12); (d) graha in nakshatra; (e) conjunctions; (f) aspects; (g) yogas and doshas with cancellations; (h) dasha and antardasha results; (i) transit results; (j) BNN combinations and transit triggers; (k) KP house-group rules per event; (l) Jaimini, Tajika, Lal Kitab, compatibility and muhurta rules. | M | 3–7 |
| KNW-6 | **Topic maps** per method for at least: career, wealth, marriage/relationships, children, education, health (traditional framing), property, vehicles, siblings, parents, foreign travel/residence, litigation, spirituality. | M | 3 |
| KNW-7 | **Puranic and devotional narratives** at episode level, with work, recension, book/canto, chapter, verse range, edition and variants. Store separately: what the story says; who links it to a graha, nakshatra or theme; and any rule or practice derived from it. | M | 6 |
| KNW-8 | **Remedies** (mantra, stotra, dana, vrata, yantra, gemstone, rudraksha, temple, Lal Kitab totke), each with source, prerequisites, **contraindications** (e.g., do not wear a gem of a functional malefic), and any efficacy claim attributed to its source. | S | 6 |
| KNW-9 | **Worked cases:** chart facts, method, cited rules, the prediction as made, the reported outcome and its provenance, and data-quality rating. Used for explanation and few-shot examples; governed separately for evaluation. | S | 5 |
| KNW-10 | **Classical and modern sources** registered before ingestion in an acquisition register: title, author, translator, edition, ISBN, language/script, rights status, OCR condition, reviewer and status. | M | 1 |
| KNW-11 | **Calculation reference knowledge** (dasha durations, varga division rules, Ashtakavarga tables) lives in the ontology/calculation specs and is cited to its source table. Calculation never retrieves it from the vector index. | M | 1 |

### 5.10 Ingestion (ING)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| ING-1 | Parse Markdown, PDF, scans, Office and HTML into one intermediate representation that keeps headings, lists, tables, page numbers and verse numbers. | M | 2 |
| ING-2 | OCR scanned pages in Devanagari and Latin scripts. Score quality per page, and route low-quality pages to a VLM or a review queue instead of indexing them. | M | 2 |
| ING-3 | Chunk by content unit: verse (with translation and commentary), section, story episode, table (with header), rule card, remedy, worked case. | M | 2 |
| ING-4 | Tag every chunk with ontology entity IDs, topics, school, lineage, method variant, reference frame, chart scope (varga), rule family and evidence class. | M | 2 |
| ING-5 | Extract candidate rule cards from text with an LLM. A rule card becomes executable only after expert review. | M | 3 |
| ING-6 | Ingestion is idempotent and incremental, and builds a versioned index. Ontology changes trigger re-tagging. | M | 2 |
| ING-7 | Never index sources whose rights status is `restricted` into anything distributed. | M | 2 |

### 5.11 Question understanding and planning (QRY)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| QRY-1 | Classify intent: concept, natal topic reading, timing, method-specific reading, comparison, story, remedy, compatibility, muhurta, prashna, annual. | M | 2 |
| QRY-2 | Extract the topic(s), entities, method(s), as-of date, time window, and whose chart is meant (native, or a relative via bhavat-bhavam). | M | 3 |
| QRY-3 | List missing inputs (e.g., birth time for a timing question) and either ask for them or proceed with stated limitations. | M | 3 |
| QRY-4 | Expand each topic into the required chart factors for each selected method using the topic map, producing a **dependency plan** of facts to compute and rule families to evaluate. | M | 3 |
| QRY-5 | Resolve relative times ("next year") against the recorded as-of date and the user's time zone. | M | 4 |

### 5.12 Rule applicability (APP)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| APP-1 | Evaluate the conditions of every rule card in the planned rule families against chart facts deterministically. The LLM never decides whether a rule or yoga is present. | M | 3 |
| APP-2 | Applicability has three states: `satisfied`, `not_satisfied`, `unknown`. Missing degrees, an unknown birth time or an uncomputed feature give `unknown`, never `false`. | M | 3 |
| APP-3 | Evaluate cancellation, qualification and exception rules linked to each satisfied rule, to a bounded depth. | M | 3 |
| APP-4 | For dasha and transit questions, apply the three-step test: does the natal chart **promise** the event, does the **dasha** activate it, does a **transit** trigger it? Report each step separately. | M | 4 |
| APP-5 | Log why each candidate rule was accepted, rejected or left unknown. | M | 3 |

### 5.13 Retrieval (RET)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| RET-1 | Retrieval is **hybrid**: (a) fetch the passages linked to applicable rule cards by ID; (b) entity-filtered dense + BM25 search; (c) ontology/graph expansion (nakshatra lord, dispositor, house lord, karaka). | M | 3 |
| RET-2 | Filters on entities, school, method variant, doc type, evidence class and licence run **inside** the search, not after it. | M | 2 |
| RET-3 | Retrieving for a chart factor must not confuse factors (e.g., "Saturn in the 10th" vs "10th lord in Saturn's sign" vs "10th from the Moon"). | M | 2 |
| RET-4 | Alias-invariant: Shani / Sani / Saturn / शनि give identical top-k. | M | 2 |
| RET-5 | Retrieve passages for each active dasha lord and sub-lord in the context of its natal condition, and for each transit event in the window. | M | 4 |
| RET-6 | Explicitly search for **contrary evidence**: mitigations, cancellations and opposing readings for each main finding. | M | 3 |
| RET-7 | Check coverage: if a required rule family or fact is missing, do a targeted retry within limits on iterations, latency and context, and report any gap that remains. | M | 3 |
| RET-8 | Method isolation: a BNN analysis retrieves only BNN-tagged (or method-neutral definitional) material unless the user requests a named hybrid. The same holds for every method. | M | 5 |
| RET-9 | Stories and remedies come only through their own routes, so their lexical richness cannot crowd rule evidence out of predictive retrieval. | M | 6 |
| RET-10 | Retrieve relevant worked cases as illustrations, labelled as such. | S | 5 |

### 5.14 Agent and synthesis (AGT)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| AGT-1 | Use a coordinator with scoped steps: input validator → planner → calculation → rule evaluation → retrieval → per-method analyst → evidence checker → synthesizer. Deterministic steps are not LLM calls. | M | 3 |
| AGT-2 | Use one analyst per selected method. It reasons only over that method's evidence bundle. | M | 5 |
| AGT-3 | Pass the synthesizer a typed **evidence bundle** (see the companion doc, §11) rather than loose text. | M | 3 |
| AGT-4 | Use an open tool-using agent for concept, story and comparison questions, and fixed workflows for chart readings, timing, compatibility and muhurta. | M | 3 |
| AGT-5 | Store per-user birth data, profiles and computed charts so that follow-ups need no re-entry (UC-12). | M | 3 |
| AGT-6 | Treat retrieved text as data, never as instructions. | M | 2 |

### 5.15 Answer (OUT)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| OUT-1 | Every interpretive claim cites a chart fact ID **and** a source passage or rule card (`[BPHS 24.12]`). | M | 2 |
| OUT-2 | Facts such as dignities and lordships come from the ontology or calculation, never from model memory. | M | 1 |
| OUT-3 | Where methods or texts disagree, present each view with attribution. Agreement between methods is not reported as a probability. | M | 3 |
| OUT-4 | State the profile used (ayanamsa, house system, dasha variant) and any birth-time sensitivity that affects the conclusion. | M | 3 |
| OUT-5 | Chart readings follow a fixed structure: inputs and profile → key placements → yogas → dasha context → transits → synthesis by method → contrary factors → gaps. | M | 3 |
| OUT-6 | Explicitly allow "not found in the sources" and "cannot be established with the given birth data". | M | 2 |
| OUT-7 | Respond in the user's language (English first; Hindi, Marathi and others later). Sanskrit terms are shown with IAST or Devanagari as configured. | S | 6 |

## 6. Non-functional requirements (NFR)

| ID | Requirement | Pri |
|---|---|---|
| NFR-1 | **Accuracy:** positions match reference software (e.g., Jagannatha Hora) to within 1 arc-second under matched settings; dasha boundaries match to within 1 day. | M |
| NFR-2 | **Reproducibility:** each answer records its corpus, rule-set, ontology, calculation and model versions. | M |
| NFR-3 | **Latency (targets):** concept questions p95 < 8 s; full chart reading p95 < 60 s (streaming partial output allowed). | S |
| NFR-4 | **Index size:** total < 10 GB on a single node. | M |
| NFR-5 | **Model choice:** the LLM is configurable (local via Ollama, or API). Every other component runs locally. | M |
| NFR-6 | **Privacy:** birth data is personal data. Store it encrypted and locally, keep it out of the shared knowledge index, redact it from logs and traces, and support deleting it. | M |
| NFR-7 | **Licensing:** track rights per source and filter on them. Decide the Swiss Ephemeris licence (AGPL or commercial) before distributing the system. | M |
| NFR-8 | **Observability:** trace every node and tool call. Run the evaluation suite on every change. | M |
| NFR-9 | **Extensibility:** add a new method by supplying a profile, features, ontology entries, rule cards, a topic map and eval cases, without changing core code paths. | S |
| NFR-10 | **Security:** defend against prompt injection from retrieved documents and imported charts. Tools have least privilege. | M |

## 7. Evaluation and acceptance (EVAL)

| ID | Requirement | Pri | Phase |
|---|---|---|---|
| EVAL-1 | **Calculation fixtures:** positions, Lagna, nakshatra/pada, panchanga boundaries, vargas, dasha balance and sub-periods, transit events. Include edge cases: 0°/360° wrap, sector boundaries, DST folds and gaps, historical time zones, high latitudes, retrograde re-crossings. | M | 1 |
| EVAL-2 | **Golden question set**, built with an astrologer, with 50–200 questions across UC-1…UC-12. Covers aliases, conflicts and multiple languages. | M | 2 |
| EVAL-3 | **Retrieval metrics:** recall@k, MRR and nDCG for required rule families; exceptions and contrary passages retrieved; cross-method contamination rate. | M | 2 |
| EVAL-4 | **Applicability tests:** positive, negative and `unknown` cases for every rule card, including cancellations. | M | 3 |
| EVAL-5 | **Answer grounding:** faithfulness, citation entailment, correct chart facts, correct method labels, stated uncertainty, and no invented rules or dates. | M | 2 |
| EVAL-6 | **Chart readings** of reference charts, scored by an expert on a rubric covering factor coverage and correctness. | M | 3 |
| EVAL-7 | **Timing questions:** the correct dasha chain and transit events are identified, and promise/period/trigger are reported separately. | M | 4 |
| EVAL-8 | Any outcome-prediction evaluation is prospective, uses held-out persons, and is kept separate from retrieval quality. | C | 7 |

**Phase exit:** a phase is accepted when its EVAL items meet targets agreed with the expert reviewer, with no regression on earlier phases.

## 8. Safety and responsible use (SAFE)

| ID | Requirement | Pri |
|---|---|---|
| SAFE-1 | Frame longevity, maraka, illness, accidents and misfortune as traditional interpretation. Make no fatalistic, medical, legal or financial claims. | M |
| SAFE-2 | Present remedies as traditional practices with attribution. Include contraindications. Never push purchases. | M |
| SAFE-3 | Never present compatibility scores as guarantees. Never frame Kuja or other doshas in a fear-inducing way. | M |
| SAFE-4 | Answers distinguish astronomical fact, traditional rule, commentary, narrative and reported case (evidence class). | M |

## 9. Constraints and assumptions

- Stack: Python, LangChain/LangGraph/LangSmith, Qdrant, Docling, BGE-M3, pyswisseph (see design §4).
- An astrologer reviewer is available from Phase 1 for the ontology, rule cards, topic maps and the golden set.
- **BNN** means Bhrigu Nandi Nadi (R. G. Rao). **Modern** means contemporary Indian interpretation unless the Western profile is chosen explicitly.

## 10. Traceability

| Requirement group | Design section |
|---|---|
| INP, CALC-3, CALC-7 | §5 Inputs and calculation profiles |
| CALC, PAN, VAR, REL, STR, DAS, TRN, SCH | §6 Computation service |
| KNW-1…4, KNW-11 | §7 Ontology |
| KNW-5, APP | §9 Rule cards and applicability |
| KNW-6, QRY | §10 Question planning and topic maps |
| KNW-7…10, ING | §8 Ingestion |
| RET | §11 Retrieval |
| AGT, OUT | §12 Agent design, §13 Generation |
| NFR-5 | §14 Model hosting |
| EVAL | §15 Evaluation |
| SAFE, NFR-6, NFR-7 | §16 Responsible use and legal |

## 11. Open questions

| # | Question | Blocks |
|---|---|---|
| 1 | Which editions and translations of BPHS and BNN are licensed for ingestion? | Phases 2, 5 |
| 2 | Should "Modern" include a Western/tropical profile in v1, or only contemporary Indian authors? | Phase 7 scope |
| 3 | Which Lal Kitab edition is canonical for the project? | SCH-LK-1 |
| 4 | Should remedies be shown by default, or only on request? | SAFE-2, RET-9 |
| 5 | Regional calendar default (amanta or purnimanta) and response languages. | PAN-3, OUT-7 |
| 6 | Swiss Ephemeris licence: AGPL or commercial. | NFR-7 |
| 7 | Who is the expert reviewer for each method (Parashari, BNN, KP, …)? | Every phase exit |
