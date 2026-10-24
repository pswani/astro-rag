# Open questions

| | |
|---|---|
| **Date** | 2026-10-24 |
| **Replaces** | the question lists in [requirements.md](requirements.md) §11, [memory.md](memory.md) §8, [design.md](../design/design.md) §23 and [calc-review.md](../design/calc-review.md) §5, which now point here |
| **How to answer** | Write in the **Your answer** lines (or reply in chat). Part B can be sent to the astrologer as it is. Where a question has a recommendation, "OK" accepts it |

Every question below was checked for three things: it needs a person (code or a measurement cannot settle it), it changes what gets built, and it is asked no earlier than needed. §5 lists what was dropped or reframed on those grounds.

## Summary

| # | Question | Who | Needed by | Recommendation |
|---|---|---|---|---|
| **A1** | Who reviews the astrology, and which software do they use? | You | Phase-1 exit; essential by phase 3 | Name one person now |
| **A2** | Which BPHS edition do you have? | You (with the reviewer) | Phase 2; "ontology reviewed" | The edition the reviewer cites |
| **A3** | What machine runs this, and may chart facts go to an API model? | You | Private store (F3) now; phase 2 | Mac + `api` mode allowed |
| **A4** | Will anyone but you run or receive this system? | You | Before any distribution | No |
| **B1** | Settings of the reviewer's reference software | Reviewer | Phase-1 exit (accuracy check) | — |
| **B2** | Eleven interpretation conventions (dignity, combustion, war, gandanta…) | Reviewer | Phase-1 exit | Current defaults |
| **B3** | Ontology review | Reviewer | Phase-1 exit | — |
| **C1–C5** | Confirm five proposed defaults | You | Various | As proposed |
| **D** | Later questions, no answer needed yet | — | Phases 4–7 | — |

---

## A. For you, now

### A1. Who is the reviewer, and which software do they use? *(was requirements Q3)*

An astrologer has to:
- **sign off on the ontology** (the 257 entities, their names and values);
- **settle the conventions** in Part B;
- **export about 30 reference charts** from their software, for the accuracy check;
- later, **review rule cards** (phase 3: career, marriage, education) and the golden question set.

A rule card cannot become executable without a reviewer (ING-5). That is the project's main protection against invented or misremembered rules.

**Questions:**
1. Who is it: you, or a named astrologer? One person can cover Parashari now and BNN by phase 5, or BNN can be a second person.
2. Which software do they use for charts? The accuracy check is built around **Jagannatha Hora**. If they use something else (Parashara's Light, Kala, …), the reference-chart format changes, so this needs knowing before task F4.

**If nobody is available yet:** building continues (register, store, eval harness, phase-2 ingestion), but everything stays `provisional`, answers say so, rule cards cannot be activated, and no phase can formally exit.

**Your answer:**

### A2. Which BPHS edition do you have? *(was requirements Q1, reframed)*

Phase 2 ingests one edition of Brihat Parashara Hora Shastra, and the ontology cites it.

- **Rights are simpler than the old question implied.** Indexing a copy you bought, for your own private use, is allowed by the design (rights `licensed`, private build). Rights only become a hard question if the system is distributed (A4).
- **What matters is verse numbering.** Chapter and verse numbers differ between editions. If the reviewer quotes "BPHS 24.12" from their copy and the system indexes another edition, citations won't line up. So the edition should be the one the reviewer uses, for example R. Santhanam's or G. C. Sharma's English translation.
- **Form matters for effort.** A PDF with a text layer is easiest. A scanned PDF needs OCR, and Devanagari OCR is the riskiest part of ingestion. A printed book needs scanning first.

**Questions:**
1. Which edition: translator, publisher and year?
2. In what form do you have it (printed, scanned PDF, text PDF)?
3. Should the Sanskrit verses be indexed alongside the translation, if the edition has them?

**Your answer:**

### A3. Your machine, and whether an API model may be used

1. **Which machine will run the system** (Mac with Apple Silicon? how much memory?)
   - The private store keeps its key in the macOS Keychain. Elsewhere it uses a locked-down key file.
   - Fully local LLMs need roughly 20 GB of memory for a ~30B model. The design's reference machine is a 64 GB Apple Silicon Mac.
2. **May an API model (Claude) be used** for analysing and writing answers?
   - Birth date, time, place and names never leave the machine in either mode (NFR-6).
   - In `api` mode, the computed chart facts (e.g. "Saturn in the 10th, exalted") and the source passages are sent. A local-only mode always exists, but answer quality and speed are lower.

**Recommendation:** allow `api` mode for the analyst and writer roles, as in the design's reference deployment, and keep `local` available.

**Your answer:**

### A4. Will anyone other than you run or receive a copy of this system? *(was requirements Q4, reframed)*

The old question asked whether to license Swiss Ephemeris under the AGPL or commercially. That decision only matters if the software is distributed. The requirements describe a single-operator tool on your machine (requirements §2.2), and private use is fine under the AGPL. The same answer settles whether books you own but may not redistribute can be indexed (ING-7).

**Recommendation:** no. Revisit only if that changes.

**Your answer:**

---

## B. For the reviewer

Everything in this part already works in the code with a provisional default. Every chart report lists the provisional settings under **Notes**. Answering only replaces a default; it does not cause rework. "Accept all current defaults" is a valid answer to B2.

### B1. Settings in your chart software

The system must use the same conventions as the software that produces the reference charts, or the accuracy check compares unlike things. Please give the setting you use for each:

| Setting | Current default | Why it matters |
|---|---|---|
| Ayanamsa | Lahiri | Shifts every position |
| Rahu/Ketu | Mean node | Mean and true differ by up to 1.5° |
| Vimshottari year length | 365.2425 days | Moves dasha dates by up to about 1.7 days over 120 years. Jagannatha Hora may use a sidereal or "true" year |
| House system for placements | Whole sign | Whole sign, Sripati and Placidus are all supported |
| Software name and version | — | Recorded with each reference chart |

The easiest answer is a screenshot of the software's calculation preferences.

**Your answer:**

### B2. Interpretation conventions

| # | Convention | Current default | Supported alternatives |
|---|---|---|---|
| 1 | Order of dignity checks | Debilitation sign; else moolatrikona degrees; else exaltation sign; else own sign; else the sign lord's friendship. So the Moon at 2° Taurus is exalted and at 5° Taurus moolatrikona | Tell us if your order differs |
| 2 | Friendship used for dignity in another's sign | Compound (natural + temporal, five grades) | Natural only |
| 3 | Combustion orbs (degrees from the Sun) | Moon 12, Mars 17, Mercury 14 (12 retrograde), Jupiter 11, Venus 10 (8 retrograde), Saturn 15 | Any values |
| 4 | Planetary war: who wins | The planet with the more northern latitude | The planet with the lesser longitude |
| 5 | Planetary war: orb | 1° | Any |
| 6 | Gandanta width | 3°20′ (one pada) either side of each water–fire junction | Any width |
| 7 | Rashi sandhi width | 1° either side of a sign boundary | Any width |
| 8 | Rahu/Ketu aspects | None | 7th only; 5th, 7th and 9th |
| 9 | Conjunction | Same sign | Within an orb (give degrees) |
| 10 | Dasha sandhi (junction) margin | 180 days for a mahadasha, 15 days for an antardasha | Any |
| 11 | Eclipse contact orb | 3° | Any |

**Your answer:**

### B3. Ontology review

Run `astro ontology review-pack --out pack.md`. It lists every entity with its names and values in one document. Please check:
- **values against your BPHS edition** (exaltation degrees, moolatrikona ranges, friendships), noting chapter and verse;
- **names:** wrong, missing or regional ones;
- **these names, which are treated as ambiguous rather than matched on their own**, because they are also ordinary words or names: *Kanya* (girl), *Singh* (surname), *Mesh* (English word), *Saumya* (benefic), *Mandi* (market), *Kala* (time), *Guru* (teacher), *Manda*, *Sauri*;
- **the house significators and karakas**, and the seed list of 28 chart yogas. The curated 20–30 for phase 3 are chosen later, with you.

Graha, rashi and nakshatra attributes beyond what the calculations use (nature, gender, guna, nakshatra deity, gana, yoni…; KNW-2, KNW-3) still have to be added. They will be drafted from your edition once A2 is answered, and then reviewed the same way.

**Your answer:**

---

## C. Confirm proposed defaults (you)

| # | Proposal | Why | OK / change |
|---|---|---|---|
| C1 | No births before 1800 | The installed ephemeris covers 1800–2399. Earlier dates need larger files, and before about 1800 birth times and calendars are rarely reliable. Dates outside the range are refused, never approximated | |
| C2 | Reading history kept until you delete it; a conversation session expires after 2 hours idle | Was memory.md question 1 | |
| C3 | A standing "always include remedies" preference is not offered; each question must ask | SAFE-2 says remedies only on request. Was memory.md question 2 | |
| C4 | Shadbala and Ashtakavarga (STR-1, STR-2) and lunar-calendar names such as samvatsara, month and ritu (PAN-3) wait until a phase-4 rule card actually needs them | All are "should" items. Shadbala alone has about 20 components with competing variants: a large effort with no current consumer | |
| C5 | The order of phase-7 expansions (KP, Jaimini, Tajika, compatibility, muhurta, prashna, remedies) is decided when phase 6 ends | Nothing before then depends on it. Was requirements Q5 | |

---

## D. Later: no answer needed yet

Listed so nothing is lost. Each will be raised again when its phase starts.

| Question | Who | Phase |
|---|---|---|
| Which one or two modern authors go in the Core source set? (e.g. B. V. Raman, K. N. Rao) *(was requirements Q2)* | You + reviewer | 6 |
| Which edition of R. G. Rao's *Bhrigu Nandi Nadi*? | You + BNN reviewer | 5 |
| Which relations count as "linked" in BNN (lineage decision, calc-review G-B1) | BNN reviewer | 5 |
| Source for functional benefics and malefics per Lagna. Sources disagree; Laghu Parashari is the usual table (calc-review G-R2) | Reviewer | 4 |
| Lunar-calendar conventions (samvatsara cycle, adhika and kshaya month naming, ritu, ayana), if C4 is not accepted (calc-review G-PN2) | Reviewer | 4 |
| Evaluation targets for each phase (requirements §7) | You + reviewer | Start of each phase |

---

## 5. How this list was reviewed

Each earlier question was tested: does it need a person, does the answer change what gets built, and is now the right time?

**Dropped: a measurement or the code settles it.**

| Earlier item | Why it is not a question |
|---|---|
| Ayanamsa nutation (calc-review G-C4) | It changes only the printed ayanamsa value, never a position. It will be set to match the reference software's display |
| Node retrograde rule (G-C3) | The mean node is always retrograde, so the rule matters only under the true node. It follows B1 |
| Apparent vs true planetary positions (G-C12) | The two differ by about 20″, twice the tolerance, so the first reference chart shows which one the software uses |
| Ephemeris file set (calc-review §5 item 1) | Installed and checked (1800–2399); only C1 remains |
| Varga specification format (item 5) | Built: all 16 divisional charts from one data spec, checked against PyJHora |
| Adopting modularity additions M1–M8 (item 7) | Adopted and built |

**Reframed: the old question was harder than the decision behind it.**

| Earlier question | Now |
|---|---|
| "Which BPHS edition is licensed for ingestion?" | A2: which edition do you have. Private use of a bought copy is allowed; verse numbering is what matters |
| "Swiss Ephemeris licence: AGPL or commercial?" | A4: will the system be distributed. If not, there is nothing to decide |
| "Shadbala component specification" (G-S2) | C4: is Shadbala needed at all yet. Specifying 20 components with no consumer is a rabbit hole |
| "Order of phase-7 bundles" | C5: deferred to the end of phase 6 |
| Thirteen separate calculation settings | B1 (four settings, answerable with one screenshot) and B2 (a table where "accept defaults" is a valid answer) |

**Added: missing before, but they change the work.**
- **Which software the reviewer uses (A1.2).** The accuracy check assumed Jagannatha Hora without asking.
- **Your machine and API use (A3).** The key storage and the LLM setup depend on them.
- **The dignity order (B2.1).** It was fixed in code without being shown to the reviewer.

**Inconsistency fixed:** mean vs true node was listed as open (calc-review G-C13, design §23) but missing from the `provisional:` list of both calculation profiles, so chart reports did not flag it. It is now listed.

## 6. After you answer

Answers are copied into the documents they affect (profiles, register, requirements, memory, design). The question's row here then gets the date and the decision. A changed calculation default creates a new profile version (`parashari_v2`), so charts computed under the old settings stay reproducible.
