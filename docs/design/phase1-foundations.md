# Phase 1 closure: private store, ontology, source register, calculation evals

| | |
|---|---|
| **Status** | Reviewed (v4, four review rounds with dry runs; §8) |
| **Date** | 2026-10-19 |
| **Parent** | [design.md](design.md) rev 5, §5, §8, §9.1, §16, §17, §19, §20 |
| **Requirements** | NFR-6, MEM-X-4, MEM-X-5, KNW-1, KNW-10, KNW-11, KNW-12, EVAL-1, NFR-1 |
| **Review log** | §8 |

The calculation layer is done ([tasks.md](../build/tasks.md) B–E). Phase 1 cannot exit until four more pieces exist (design §20):

| # | Piece | Phase-1 exit criterion it serves |
|---|---|---|
| A | Encrypted private store with person storage, fact cache, inspection and deletion; log redaction | "deletion and redaction tests pass" |
| B | Ontology loader, aliases, confusables and the alias matcher | "ontology reviewed"; KNW-12 acceptance |
| C | Source register: schema, validator, CLI | KNW-10 (M, phase 1) |
| D | Calculation eval harness for the reviewer's Jagannatha Hora exports | "EVAL-1 calc fixtures pass at NFR-1 tolerances" |

All four can be **built** without an LLM, a corpus or an open reviewer decision. Two phase-1 **exits** still wait on people: the ontology review and the JHora exports need the reviewer (open question 3), and a reviewed ontology must cite a registered edition, which needs open question 1 (§3.4 rule 5). What is built here is what their work plugs into.

**Not in this document:** session context, proposals, reference resolution and reading records (memory, phase 3), the PII scrubber (phase 2, `api` mode only), canonicalized query rewriting (phase 2), ingestion (phase 2).

---

## 1. Module layout and boundaries

```
src/astro/store/        A: keys.py, db.py (open, migrations), tables.py (personal-data registry),
                        persons.py, cache.py (CachePort over fact_cache)
src/astro/obs/          A: redact.py (log redaction)
src/astro/ontology/     B: model.py, load.py, fold.py, matcher.py
src/astro/sources.py    C: register model and checks
src/astro/evals/calc.py D: fixture model, runner, report
sources/register.yaml   C
evals/calc/             D: charts/*.yaml, settings_map.yaml, README.md
```

Import contracts added to `pyproject.toml` (checked by `lint-imports` in CI):

| Contract | Why |
|---|---|
| `astro.calc` imports nothing from `astro.store`, `astro.ontology`, `astro.sources`, `astro.evals` | The calculation layer stays pure; it sees the store only through `CachePort` |
| Only `astro.store` imports `sqlcipher3`; only `astro.store.keys` imports `keyring` | One place to audit for key handling |
| `astro.ontology` and `astro.sources` import nothing from `astro.store` | Curated knowledge never touches personal data (design §5.2) |

New runtime dependencies: `sqlcipher3==0.6.4` (wheels with SQLCipher 4 bundled for macOS arm64/x86_64, Linux and Windows, Python 3.10–3.13) and `keyring>=25`.

---

## 2. A — Encrypted private store

### 2.1 Location and files

| File | Default | Contents |
|---|---|---|
| `private.db` | `$ASTRO_DATA` or the platform data directory (`~/Library/Application Support/astro-rag/`, `$XDG_DATA_HOME/astro-rag/`) | SQLCipher 4 database |
| `private.db.meta.json` | next to it | Not secret: `{store_id, format, key_provider, key_file?}`. Says where the key is, because the encrypted header cannot be read before the key is known |

The directory is created `0700` and the files `0600`. The store is never inside the repository: opening a path under `astro_home()` is refused.

### 2.2 Keys

- **Master secret:** 32 random bytes, created by `astro store init`.
- **Key providers.** `astro store init` picks one and records it in the sidecar, so later commands need no environment setup:
  1. `keychain` (default): the OS keychain via `keyring` (macOS Keychain on the reference deployment), service `astro-rag`, account `store:<store_id>`.
  2. `file` (`--key-file PATH`, for machines without a keychain backend): the master secret in hex. Refused when the file is group- or world-readable or lies inside the repository.

  `ASTRO_KEY_FILE` overrides the sidecar for one run (recovery, moved files). If the recorded provider cannot supply the key, the command stops with the steps to fix it: there is no plaintext fallback and no key in an environment variable. `init` without `--key-file` on a machine whose `keyring` backend is the null backend stops and suggests `--key-file`.

  Tests and CI inject a `StaticKeyProvider`.
- **Derived keys** (HKDF-SHA256, RFC 5869, about 15 lines over `hmac`; no new dependency):

  | `info` | Use |
  |---|---|
  | `astro/v1/sqlcipher` | Raw SQLCipher key (`PRAGMA key = "x'…'"`), so SQLCipher's own PBKDF2 is skipped |
  | `astro/v1/chart-id` | HMAC key for chart IDs (design §5.3) |

  Chart IDs no longer depend on `ASTRO_CHART_KEY` when a store is configured; the stateless `astro chart` keeps today's behaviour (`ASTRO_CHART_KEY`, else a random per-run key).
- **Backup:** `astro store export-key` prints the master secret once, with a warning. Losing the key loses the data; backups of the database stay encrypted (requirements R5).
- **Rotation** is not in phase 1. It needs `PRAGMA rekey` plus recomputing chart IDs from the birth records; both are possible later without a schema change.

### 2.3 Connection settings

Every connection runs, in order:

```
PRAGMA cipher_log_level = NONE;     -- SQLCipher otherwise prints decryption errors to stderr
PRAGMA key = "x'<derived key>'";
SELECT count(*) FROM sqlite_master; -- wrong key → StoreKeyError("wrong key for <path>")
PRAGMA journal_mode = WAL;  PRAGMA foreign_keys = ON;  PRAGMA secure_delete = ON;
PRAGMA temp_store = MEMORY; PRAGMA busy_timeout = 5000;
```

### 2.4 Schema (phase 1)

```sql
meta(key TEXT PRIMARY KEY, value TEXT)                         -- schema_version, store_id
persons(id TEXT PRIMARY KEY,                                   -- p_<8 random base32>
        label TEXT NOT NULL, relation TEXT, created_at TEXT)
birth_records(person_id TEXT REFERENCES persons ON DELETE CASCADE,
              version INTEGER, input_json TEXT, normalized_json TEXT,
              reason TEXT, created_at TEXT, PRIMARY KEY (person_id, version))
charts(chart_id TEXT PRIMARY KEY, profile_id TEXT, created_at TEXT)
chart_owners(chart_id TEXT REFERENCES charts ON DELETE CASCADE,
             person_id TEXT, birth_version INTEGER,
             FOREIGN KEY (person_id, birth_version) REFERENCES birth_records ON DELETE CASCADE,
             PRIMARY KEY (chart_id, person_id, birth_version))
fact_cache(cache_key TEXT PRIMARY KEY, chart_id TEXT REFERENCES charts ON DELETE CASCADE,
           feature_id TEXT, result_json TEXT, bytes INTEGER, created_at TEXT, last_used_at TEXT)
```

- **Birth records are versioned from the start** (`MEM-PER-5`); phase 1 writes version 1 only.
- **Charts are shared.** Two persons with the same birth data and profile (twins, or a duplicate entry) have the same chart ID and share cached facts. `chart_owners` records who uses a chart. SQLite cascades only from parent to child, so deleting an owner does not delete the chart: the deletion transaction ends with `DELETE FROM charts WHERE chart_id NOT IN (SELECT chart_id FROM chart_owners)`, which cascades to `fact_cache`.
- **Order of writes:** a person-linked run inserts its `charts` and `chart_owners` rows before the engine runs, so every `fact_cache` row has its parent.
- **Migrations** are ordered SQL scripts in `db.py`; `meta.schema_version` records the last applied. A database with a newer version than the code is refused.
- Phase-3 tables (consents, method inputs, readings, notes, flags, preferences, LangGraph checkpoints) arrive with their phase, each registered in §2.6.

### 2.5 Fact cache

- `StoreFactCache` implements the existing `CachePort`. The port gains the chart ID: `put(key, result, *, chart_id)`; `InMemoryCache` ignores it.
- **Serialization is Pydantic JSON** (`model_dump_json` / `model_validate_json`), not the RFC 8785 canonical form, which writes `0.0` as `0` and fails validation of float facts. The CALC-9 determinism test gains a run through `StoreFactCache`.
- **Version check (`MEM-X-6`):** the cache key already includes engine, profile hash, ephemeris file hashes and reference-data version (`Engine.cache_key`), so a stale entry is never hit.
- **Eviction:** `astro store gc` and a size cap (*initial* 200 MB) evict least-recently-used rows.
- **Only person-linked runs write the cache.** `astro chart --person <id>` uses it; the stateless `astro chart` writes nothing to disk except the PDF.
- With `--person`, the default PDF name is `chart-<person id>-<profile>.pdf`: it does not spell out the birth date, time and place the way the stateless default does.

### 2.6 Inspection and deletion (`MEM-X-4`, `MEM-X-5`, NFR-6)

`tables.py` holds a registry that classifies **every** table:

```python
PERSONAL = {   # table -> SQL selecting its rows for one person (:pid)
  "persons":       "SELECT * FROM persons WHERE id = :pid",
  "birth_records": "SELECT * FROM birth_records WHERE person_id = :pid",
  "chart_owners":  "SELECT * FROM chart_owners WHERE person_id = :pid",
  "charts":        "<charts whose only owner is :pid>",
  "fact_cache":    "<rows of those charts>",
}
NOT_PERSONAL = {"meta"}
```

- A test lists `sqlite_master` and fails if a table is in neither set, so a new table cannot escape deletion.
- `astro person show <id>` prints counts per table from `PERSONAL`, the rows of the person, birth-record and chart tables, and only counts and features for `fact_cache` (its rows are large and recomputable).
- `astro person delete <id>` asks for confirmation (or `--yes`), prints the same counts, deletes in one transaction (cascades do the rest), then runs `PRAGMA wal_checkpoint(TRUNCATE)` and `VACUUM`.
- **Deletion test:** two persons, one a twin of the other (same chart). Delete one: every row naming it is gone, the twin's chart and cache remain. Delete the twin: no row in any table names either, and no text column contains the fixture's date, time or place.

### 2.7 Log redaction (NFR-6, design §16.1)

- `astro.obs.redact.configure_logging()` installs a `RedactingFormatter` on the handlers it creates. It redacts the **rendered message** (`record.getMessage()`, so arguments are included), the exception text and the stack text, then formats a copy of the record. It does not redact the whole line, because the line's own timestamp is a date and time. Exception text matters: Pydantic validation errors include the input values.
- Redacted: ISO and common numeric dates, clock times, decimal coordinates (3+ decimals) and degree-minute coordinates, and registered literal values of at least 3 characters (case-insensitive). Values are registered by:
  - the open store: labels, place queries and resolved place names of every person;
  - the normalizer, for every request, stored or not: the place query and the resolved place label. A stateless `astro chart` has no store, and pattern rules alone would miss "Pune, Maharashtra".
- `logging.captureWarnings(True)` routes warnings through the same formatter.
- **Every CLI entry point calls `configure_logging()` first.** Without a configured handler, Python's `logging.lastResort` prints library warnings to stderr with no formatter, which bypasses redaction. The default is a stderr handler at `WARNING`; `ASTRO_LOG_FILE` adds a file handler and `ASTRO_LOG_LEVEL` sets its level.
- The codebase logs almost nothing today; the rule from here on is that modules log through `logging.getLogger(__name__)` and never print diagnostics with personal data.
- **Redaction test:** the CLI scenarios (chart, person add/show/delete) run with `ASTRO_LOG_LEVEL=DEBUG` and `ASTRO_LOG_FILE`; the test greps the file and stderr for the fixtures' birth data in several formats (`1985-03-14`, `14/03/1985`, `06:42`, `18.5196`, `Pune`). A unit test sends a Pydantic validation error carrying birth data through `log.exception`.
- Report output on stdout (the chart itself) is the operator's own output and is not redacted.

### 2.8 LangGraph checkpointer (design §23 risk, verified now)

The stock `SqliteSaver` accepts a `sqlcipher3` connection, but its `setup()` catches only `sqlite3.OperationalError` around a migration `ALTER TABLE`, and `sqlcipher3` raises its own class. A dry run showed a six-line subclass is enough:

```python
class EncryptedSqliteSaver(SqliteSaver):
    def setup(self) -> None:
        try:
            super().setup()
        except sqlcipher3.dbapi2.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
            self.is_setup = True
```

With it, interrupt → close → reopen → resume and `delete_thread` all worked over SQLCipher. The adapter and its contract test ship with the workflows in phase 3; the risk row in design §23 is closed.

### 2.9 CLI

| Command | Does |
|---|---|
| `astro store init [--key-file PATH]` | Creates the database, sidecar and master secret (keychain, or the given file) |
| `astro store info` | Path, store ID, key provider, schema version, sizes. Never prints keys. Back up the sidecar with the database; if it is lost, `--store-id` (printed here) names the keychain entry |
| `astro store export-key` | Prints the master secret once, with a warning |
| `astro store gc` | Evicts cache rows over the cap |
| `astro person add --label L [--relation R] <birth flags as astro chart>` | Normalizes, stores birth record v1 |
| `astro person list` / `show <id>` / `delete <id> [--yes]` | §2.6 |
| `astro chart --person <id>` | Chart from the person's latest birth record, using the cache. Birth flags with `--person` are refused (a correction is a new birth-record version, phase 3) |

---

## 3. B — Ontology

### 3.1 Entity model

Every entity has an ID `<kind>:<slug>` (design §5.3), `names` (aliases that the matcher may use) and optionally `ambiguous_names` (never matched alone; reported as ambiguous). Attribute schemas per kind are Pydantic models.

Kinds in phase 1 (KNW-1):

| Kind | File | Count |
|---|---|---|
| `graha`, `rashi`, `nakshatra` | existing files | 9, 12, 27 |
| `dignity` | `dignities.yaml` (new) | IDs equal the engine's values: `exalted`, `moolatrikona`, `own`, `great_friend`, `friend`, `neutral`, `enemy`, `great_enemy`, `debilitated` |
| `bhava`, `bhava_group` | `bhavas.yaml` (new) | 12; kendra, trikona, dusthana, upachaya, maraka, panaphara, apoklima and the four trikonas. The file also holds each house's ordinals and the house words (§3.6) |
| `tithi`, `paksha`, `vara`, `nitya_yoga`, `karana` | `panchanga.yaml` (restructured, §3.5) | 30, 2, 7, 27, 11 |
| `varga`, `dasha_system`, `karaka_scheme` | existing files | 16, 1, 1 |
| `yoga` | `yogas.yaml` (new) | IDs and names only; the curated 20–30 are chosen with the reviewer in phase 3 |
| `point`, `upagraha`, `special_lagna` | `points.yaml` (new) | `point:lagna` (the calculation's bare `lagna` subject); Gulika, Mandi…; Hora, Ghati, Bhava lagna… |
| `deity`, `topic`, `school`, `koota` | `deities.yaml`, `topics.yaml`, `methods.yaml`, `kootas.yaml` (new) | Topics: the KNW-6 list. Schools: the payload enum (design §9.7). Kootas: only what KNW-12 needs (`koota:nadi`) until phase 7 |

### 3.2 Loading and versions

- `astro.ontology.load(home)` reads every file into Pydantic models and runs the checks in §3.4. Loaded once per process (same stamp-based cache as `load_refdata`).
- **Two versions:**
  - `refdata.version` (existing) is part of the fact-cache key. Today it hashes whole entries, `names` included (a dry run confirmed that adding an alias changes it). It changes to hash a **projection** of the fields the calculation reads (lords, dignities, friendships, sequences, varga specs, IDs and order), so editing an alias does not invalidate cached facts. A test edits an alias and asserts the version is unchanged.
  - `ontology_version` hashes every file plus `FOLD_VERSION` (§3.3). It goes on passages and releases (design §5.4, §9.8).
- `calc/refdata.py` keeps its narrow interface (calc-review M6) and its table checks; it is adapted to the restructured panchanga file only.

### 3.3 Folding and tokenization

Aliases and text are compared after `fold()`:

1. Unicode NFC.
2. Latin: NFD, drop combining marks, casefold (`Śani` → `sani`, `Bṛhaspati` → `brhaspati`).
3. Devanagari: an anusvara stands for any class nasal before a consonant of that class, so `ङ्ग`/`ं` and the like are normalized to the anusvara (`मङ्गल` → `मंगल`); nukta and zero-width joiners dropped.

Tokens are runs of letters, digits **and combining marks**: `\w` plus the Devanagari block U+0900–U+097F except the dandas U+0964–U+0965, which separate. (Python's `\w` excludes vowel signs, so `शनि` would split into `शन` + `ि`; a dry run confirmed this.)

Transliteration variants (`Shani`, `Sani`, `Shanee`) are listed explicitly in `names`; folding does not guess them.

### 3.4 Integrity checks (`astro ontology check`, CI)

1. Every referenced ID resolves and has a known kind.
2. **Alias uniqueness:** a folded alias appears in the `names` of at most one entity.
3. **Collisions are declared:** if a folded alias is in one entity's `names` and another's `ambiguous_names`, that is an error — the alias must be ambiguous everywhere, so the matcher never silently picks one reading.
4. **Disputed values carry sources:** an attribute given as a list of views needs a `source` on each view.
5. Files with `meta.status: reviewed` cite sources as `<edition_id>:<locator>` resolving in the source register (§4); `provisional` files may use free text. **Consequence:** no file can be marked reviewed until the BPHS edition is chosen and registered (requirements open question 1), so the phase-1 exit "ontology reviewed" depends on that decision as well as on the reviewer.
6. The existing calculation table checks (`YamlReferenceData.check`).
7. **The two readers agree:** every ID the calculation can emit (`refdata.rashi_id`, `nakshatra_id`, `tithi_id`, `karana_id`, `nitya_yoga_id`, `vara`, the dignity values, the varga IDs) is an ontology entity. The two loaders parse the same files independently (the calculation layer may not import `astro.ontology`), and this test keeps them from drifting.
8. Core kinds (graha, rashi, nakshatra, bhava, dignity, panchanga limbs, varga) have at least one Latin and one Devanagari name (KNW-1).
9. There are 12 houses and their ordinals are unique.

Spacing and spelling variants of compounds (`Gajakesari`, `Gaja Kesari`) must be listed explicitly; no check can find a missing one, so the review pack (§3.8) shows every alias.

Rules 1–9 are implemented in `astro/ontology/load.py`, each with a test that breaks a copy of the data and expects the message.

### 3.5 Panchanga file restructure

`tithis`, `nitya_yogas` and `karanas` are lists of bare IDs today. They become `{id, names}` entries in the same order, so names live next to their entity. `YamlReferenceData` reads `entry["id"]`; the calculation results are unchanged (checked by the determinism and oracle tests).

### 3.6 Alias matcher

`AliasMatcher(ontology).match(text, reserved=()) -> list[Span]`:

- Folds and tokenizes the text, then scans a token trie, **longest match first**: `Shiva yoga` is one span (`nitya_yoga:shiva`), not `deity:shiva` + `yoga`.
- Each span is `resolved(entity_id)` or `ambiguous(candidates)`. An ambiguous span with one candidate means "this entity or an ordinary word" (`Guru` is Jupiter or a teacher; `Kanya` is Virgo or a girl).
- `ambiguous_names` and colliding names give `ambiguous`. What to do with an ambiguous span (ask, or tag every candidate) is the caller's choice in phase 2; the matcher never picks.
- **Naming conventions that keep collisions few:**
  - Tithi names that occur in both pakshas (`Ekadashi`) are ambiguous; the full name (`Shukla Ekadashi`) resolves.
  - Nitya yogas whose bare name is another entity (`Brahma`, `Indra`, `Shiva` are deities) are listed only with "yoga" (`Brahma yoga`); the bare name resolves to the deity.
- `reserved` maps folded strings to extra candidates (e.g. `person`). A person labelled *Ravi* makes `Ravi` ambiguous between `graha:sun` and the person, so the planner asks instead of reading "Ravi's career" as the Sun's.
- **House ordinals** are a small closed pattern set: an ordinal (`10th`, `tenth`, `dashama`, `दशम`) followed by `house`/`bhava`/`bhāva`/`भाव` gives `bhava:10`. A bare ordinal is left to the planner (phase 2).

The matcher is what the phase-2 tagger and canonicalizer (design §9.6, §12.2) call; phase 1 uses it for the KNW-12 fixtures and `astro ontology match "<text>"`.

### 3.7 Confusable fixtures (KNW-12 acceptance)

`tests/ontology/test_confusables.py`, one case per row:

| Text | Expected |
|---|---|
| `Siddha yoga at birth` | `nitya_yoga:siddha` |
| `Gajakesari yoga` | `yoga:gajakesari` |
| `Vajra yoga` | ambiguous: `nitya_yoga:vajra`, `yoga:vajra` (also a Nabhasa yoga) |
| `Bhadra` | ambiguous: `karana:vishti` (Bhadra), `yoga:bhadra` (Mahapurusha) |
| `Nadi koota` | `koota:nadi` |
| `Bhrigu Nandi Nadi`, `BNN` | `school:bnn` |
| `Nadi astrology` | `school:nadi_other` |
| `nadi` alone | ambiguous |
| `Makara` / `10th house` | `rashi:capricorn` / `bhava:10` |
| `शनि`, `Śani`, `Shani`, `Saturn` | `graha:saturn` |
| `Guru`, `Kanya` | ambiguous with one candidate: `graha:jupiter`, `rashi:virgo` |
| `Krishna paksha` / `Krishna` | `paksha:krishna` / `deity:krishna` |
| `Ekadashi` / `Shukla Ekadashi` | ambiguous: both ekadashis / `tithi:shukla_ekadashi` |
| `Brahma` / `Brahma yoga` | `deity:brahma` / `nitya_yoga:brahma` |
| `Mula`, `mula trikona` | `nakshatra:mula`; `dignity:moolatrikona` |
| `Ravi` with a stored person *Ravi* | ambiguous: `graha:sun`, person |

### 3.8 Content work and review

The data is drafted as `provisional` from standard sources and reviewed with the astrologer (phase-1 exit "ontology reviewed"). `astro ontology review-pack` renders every entity with its names and attributes as a single document for that review.

---

## 4. C — Source register (`KNW-10`)

### 4.1 Schema

`sources/register.yaml`, one entry per edition, loaded into a Pydantic model:

| Field | Rule |
|---|---|
| id (key) | `<work>_<editor or translator>_<year>`, lowercase slug |
| `title`, `author`, `editor`, `translator`, `publisher`, `edition_year` | As in design §9.1 |
| `language`, `script` | ISO 639-1 codes; `devanagari` / `latin` |
| `isbn` or `catalog_id` | One required from `acquired` on |
| `source_uri` | `data/raw/<id>/` |
| `files` | `[{path, sha256, bytes}]`, required from `acquired` on |
| `rights` | `public_domain` / `licensed` / `restricted` / `unknown` (= restricted) |
| `rights_basis` | Why that rights value holds (e.g. "purchased copy, private use"). Required unless `unknown` |
| `external_processing` | `allowed` / `denied` (default `denied`). Gates an API VLM pass (design §9.3) |
| `school`, `lineage` | `school` resolves to an ontology `school:*`; `lineage` required for `bnn` (SCH-BNN-3) |
| `coverage` | List of locator ranges, e.g. `ch1-97` |
| `ocr_condition` | `native_text` / `good` / `fair` / `poor` |
| `verse_pattern` | A regex; must compile |
| `reviewer` | Name, required from `reviewed` on |
| `status` | `candidate` → `acquired` → `parsed` → `reviewed` → `published`; `withdrawn` (+ `withdrawn_reason`) |

### 4.2 Checks

- `astro sources check`: schema; required fields per status; `school` resolves; regex compiles. Which rights may enter which build (private vs distributable, ING-7) is enforced when a collection is built (phase 2), not here.
- `astro sources check --files` (local, not CI, since `data/raw/` is not in git): every listed file exists and matches its hash; no unlisted file sits under `source_uri`.
- Payload mapping: the passage `license` field (design §9.7) is `rights`, with `unknown` stored as `restricted`.

### 4.3 Content now

The register starts with no entries. Candidate BPHS editions are added when open question 1 is answered; their ISBNs and rights are entered from the books themselves, not guessed.

---

## 5. D — Calculation eval harness (`EVAL-1`, NFR-1)

### 5.1 Fixture format

`evals/calc/charts/<id>.yaml`, one reference chart each:

```yaml
id: ref_001
edge_cases: [high_latitude, retrograde_recrossing]   # EVAL-1 labels, closed list
source: {tool: jagannatha_hora, version: "8.0", exported_by: <reviewer>, date: 2026-11-02}
settings: {ayanamsa: lahiri, nodes: mean, year: "365.2425", houses: whole_sign}  # JHora labels
birth: {date: 1985-03-14, time: "06:42:00", offset: "+05:30", lat: 18.5196, lon: 73.8554}
expected:
  longitudes: {sun: "330 12 05", moon: "…", lagna: "…"}            # sidereal DMS
  nakshatra_pada: {moon: [uttara_bhadrapada, 2]}
  varga_signs: {D9: {sun: capricorn, …}, D10: {…}}
  panchanga: {tithi: {id: shukla_ekadashi, ends: "1985-03-14T10:12"}, …}
  vimshottari: {MD: [[venus, "1990-03-30"], …], AD: [[…]]}
```

- **Offsets, not zone names.** The birth time carries an explicit UTC offset, so JHora and the engine see the same instant. Expected panchanga times are in the same offset. IANA, DST-gap and fold cases are tested against `tzdata` in `test_normalize.py`, not against JHora.
- **Longitudes** are accepted in absolute DMS (`330 12 05.2`) or JHora's sign notation (`0 Pi 12' 05.2"`).
- **Settings are matched, not assumed.** `settings_map.yaml` maps each JHora setting label to a calculation-profile field. A fixture must give a value for every mapped setting (no implicit defaults); an unknown or missing label refuses the fixture. The runner builds a profile variant (base profile + mapped overrides, validated by `CalcProfile`), with ID `<base>+<hash of overrides>`.
- **Behaviour JHora does not expose as a setting** (whether positions are apparent or true geometric, calc-review G-C12) is listed under `fixed:` in the map, marked `unverified` until a fixture confirms it. The two differ by about 20″ for the Sun, twice the tolerance, so the first fixture settles it.

### 5.2 Comparison rules

| Fact | Tolerance |
|---|---|
| Planet longitude | 10″ |
| Lagna | 30″ |
| Vimshottari boundary | 2 days; boundaries after birth only (the first MD's start is a display convention) |
| Panchanga limb end | 1 min (*initial*, design §19.2) |
| Discrete facts (sign, nakshatra, pada, varga sign, dasha lord) | Exact, unless the engine's longitude is within the tolerance of a boundary: then the result is `boundary`, recorded, not a failure |

### 5.3 Runner and report

- **Edge cases are split by who can check them** (`evals/calc/edge_cases.yaml`):

  | Checked against JHora | Checked by engine tests (pytest node IDs listed in the file) |
  |---|---|
  | 0°/360° wrap, sector boundaries (sign, nakshatra, pada, varga), high latitude, retrograde re-crossing, dates outside the former 1900–2100 range, southern/western coordinates | DST fold and gap, documented historical standards, calendar conversion, feature-specific engine/data limits, unknown birth time |

  JHora takes a fixed offset and a Gregorian date, so the right-hand cases cannot be compared with it.
- `astro eval calc [--gate] [--report out.json]` prints a pass rate per fact kind, every failure with its fixture and values, the `boundary` list, and the edge-case coverage.
- Without `--gate` it fails only on a mismatch. With `--gate` (phase-1 exit) it also needs at least 30 fixtures, every left-hand label covered by a fixture, and every right-hand test ID collected by pytest.
- **Reviewer pack:** `astro eval calc --pack` writes 30 proposed charts (inputs, edge-case labels, and the JHora settings to use) for the reviewer to export. The boundary cases are found with the engine's own solver (e.g. a birth minute when the Moon is within 20″ of a nakshatra boundary), so the pack is reproducible.
- The harness is tested with fixtures built from the engine's own output, perturbed to check each tolerance and the boundary rule.

---

## 6. Changes to existing documents and code

The document changes were applied with this design (design.md rev 6, calc-review.md, tasks.md §F); the code changes are tasks F1–F4.

| Where | Change |
|---|---|
| design.md §4.4 | Add `store/`, `obs/`, `ontology/`, `sources.py`, `evals/calc.py` |
| design.md §5.3 | Chart-ID key derived from the master secret (§2.2) |
| design.md §8 | Folding, token rule, collision rule, `reserved`, two versions |
| design.md §9.1 | `files`, `rights_basis`, `external_processing`, `withdrawn_reason` |
| design.md §16.1 | Key providers, sidecar, HKDF, redaction of formatted lines |
| design.md §20 | Phase 1 ships person storage, inspection and deletion; reference resolution, proposals and sessions stay in phase 3 |
| design.md §23 | Checkpointer risk closed (§2.8) |
| calc-review.md §1.2 | Persistent fact cache: unblocked by A |
| tasks.md | New section F |
| `calc/engine.py` | `CachePort.put(..., chart_id=)` |
| `calc/refdata.py` | Restructured panchanga entries |

## 7. Build order

1. B (ontology), because C's `school` check and the reviewed-source rule use it.
2. C (register).
3. A (store, cache, redaction, CLI).
4. D (eval harness and reviewer pack).

Each follows the existing loop: plan → code → tests → review → fix.

## 8. Review log

Each round reviewed the draft and **dry-ran** it: prototype code against the real libraries and the repository's own code, plus scenario walk-throughs. Probes ran in a scratch environment (sqlcipher3 0.6.4 / SQLCipher 4.19.0, langgraph-checkpoint-sqlite 3.1.2, keyring 25.7.0, Python 3.13) and are not committed.

### Analysis (before v1)

| Probe | Result | Effect on the design |
|---|---|---|
| SQLCipher: create, write, read back raw bytes | No plaintext in the file or WAL; wrong key → "file is not a database" | §2.3 |
| `SqliteSaver` over a `sqlcipher3` connection | `setup()` fails: it catches `sqlite3.OperationalError` only | §2.8 subclass |
| The subclass: interrupt, close, reopen, resume; `delete_thread` | All work; rows gone after delete | §23 risk closed |
| `keyring` on headless Linux | Null backend | `--key-file` provider |
| `re` `\w` on Devanagari | `शनि` → `शन` + `ि` | §3.3 token rule |
| Full 15-feature determinism run through a Pydantic-JSON cache | Byte-identical | §2.5 |
| Same through a canonical-JSON cache | Fails: `0.0` written as `0`, rejected by the fact model | §2.5 serialization rule |

### Round 1 (v1 → v2): 13 findings

| # | Finding | How found | Fix |
|---|---|---|---|
| 1 | Without a keychain the operator had to set `ASTRO_KEY_FILE` on every run | Linux walk-through | Provider recorded in the sidecar (§2.2) |
| 2 | Deleting one twin cannot delete the shared chart through cascades, and the last owner's delete would orphan it | Executed the schema and both deletions in SQLCipher | Explicit orphan-chart delete; write order (§2.4) |
| 3 | Redacting the whole formatted line erases the log's own timestamp | Walk-through of `%(asctime)s` | Redact message, exception and stack only (§2.7) |
| 4 | `refdata.version` changes when an alias is added, so alias edits would invalidate every cached fact | Executed: added `Shanee`, version changed | Hash a calculation projection (§3.2) |
| 5 | The confusables table used `dignity:moolatrikona`, a kind not in the model | Cross-check against `condition.py` | `dignity` kind with the engine's values (§3.1) |
| 6 | `Ekadashi` and the other tithi names exist in both pakshas | Alias drafting | Bare name ambiguous; full name resolves (§3.6) |
| 7 | `Brahma`, `Indra`, `Shiva` are both nitya yogas and deities | Alias drafting | Nitya yogas listed with "yoga" (§3.6) |
| 8 | "Every EVAL-1 label covered by a JHora fixture" cannot be met: JHora takes a fixed offset and a Gregorian date | Walk-through of each label | Labels split between fixtures and engine tests (§5.3) |
| 9 | "Unknown rights cannot be published to a distributable build" is a build-time rule, not a register rule | Walk-through of ING-7 | Moved to phase-2 collection build (§4.2) |
| 10 | A reviewed ontology must cite a registered edition, so "ontology reviewed" depends on open question 1 | Rule 5 against §4.3 | Stated as a dependency (§3.4, intro) |
| 11 | The default PDF name spells out birth data for stored persons | `--person` walk-through | Person ID in the name (§2.5) |
| 12 | Panchanga times and longitude notation in fixtures were unspecified | Fixture drafting | Offset time; two notations (§5.1) |
| 13 | How the runner applies JHora settings was unspecified | Fixture drafting | Profile variant `<base>+<hash>` (§5.1) |

### Round 2 (v2 → v3): 6 findings

The matcher was prototyped (folding, token trie, collision check) and the §3.7 table run through it: all 30 cases gave the expected result, and a deliberately colliding alias was caught. The redacting formatter was prototyped against a Pydantic validation error carrying birth data: nothing leaked, and the timestamp and version strings survived.

| # | Finding | Fix |
|---|---|---|
| 1 | A hard-coded "open" set for words like `Guru` was data in code | An ambiguous span with one candidate already means "entity or ordinary word"; flag dropped (§3.6) |
| 2 | `Krishna paksha` had no entity; bare `Krishna` went to the deity | `paksha` kind (§3.1, §3.7) |
| 3 | A stateless `astro chart` registers no literal values, so "Pune, Maharashtra" in a log line passes the patterns | The normalizer registers each request's place values (§2.7) |
| 4 | JHora has no setting for apparent vs true positions; an implicit default would decide NFR-1 silently | Complete settings block; `fixed:` entries marked unverified (§5.1) |
| 5 | Calculation and ontology parse the same files separately and could drift | Integrity rule 7 (§3.4) |
| 6 | A lost sidecar left no way to name the keychain entry | `--store-id` (§2.9) |

### Round 3 (v3 → v4): 5 findings

| # | Finding | Fix |
|---|---|---|
| 1 | The intro said nothing waits on a reviewer decision, contradicting round 1 #10 | Intro separates building from exit |
| 2 | `person show` would print megabytes of cached JSON | Counts and features only for the cache (§2.6) |
| 3 | With no handler configured, Python's `lastResort` prints library warnings unformatted, bypassing redaction | Every entry point calls `configure_logging()` (§2.7) |
| 4 | Birth flags combined with `--person` had no meaning | Refused (§2.9) |
| 5 | "Former product range" was undefined | 1900–2100, from requirements review R7 |

### Round 4: no new findings

The remaining claims were checked against the code: the `CachePort` change touches one call site and one implementation; every new import respects the contracts in §1; `sqlcipher3` 0.6.4 publishes wheels for the reference deployment (macOS arm64, Python 3.11–3.13). Not verifiable here and left as build-time checks: `keyring` against the real macOS Keychain, and the JHora behaviour in §5.1.
