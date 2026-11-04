# astro — Jyotish agentic RAG: deterministic calculation layer
<!-- Shared agent instructions (Codex, Claude via @AGENTS.md). Keep under one page. -->

## How we work (AI-native SDLC)
- Process: `docs/sdlc/AI-NATIVE-SDLC.md`. Rules: `.claude/rules/*.md` — **read the matching rule file before writing an artifact** (intent 10, spec 20, plan 30, code 40, tests 50, PR/review 60, agent config 70, ops 80). Core rules (00) always apply.
- New changes live in `intent/<NNNN-slug>/`: `intent.md` → `spec.md` → `plan.md`; commits titled `[<NNNN-slug>] …`; PR links all three. Pick the track first (Full / Light / Trivial, G0).
- Baseline artifacts (pre-SDLC): root intent `intent/0001-jyotish-evidence-layer.md`, requirements `docs/req/requirements.md` (IDs like `CALC-9`), design `docs/design/design.md` (normative; wins on conflict), build plan `docs/build/tasks.md`. New specs cite and extend these IDs.
- No source edits before `plan.md` is approved by the maintainer. Set the active change: `echo <id> > .sdlc/state/active-change`.
- Agents never self-approve, merge, or push to `main`. If a guardrail blocks you, follow the route in its message.

## Commands
- Setup: `make setup` (uv sync + pinned Swiss Ephemeris into `data/ephe/`, git-ignored)
- Lint: `make lint` → "All checks passed!" and "Contracts: 2 kept, 0 broken."
- Test: `make test` → "N passed, 2 skipped" (oracle tests need the `oracle` extra; CI sets `ASTRO_REQUIRE_ORACLE=1`)
- Verify (lint + test, = CI): `make verify` → ends with "verify: OK"

## Verifying your work
Run `make verify` before reporting any task complete and paste the output. If a test fails, fix the code, not the test.

## Conventions (from intent 0001 and design.md)
- The LLM never calculates and never decides whether a rule applies; code does both.
- Reproducible: same inputs → same result, recorded with the versions that produced it (canonical JSON + content hash).
- Unknown is an answer: report `unknown` with a reason code, never a silent "no".
- Attribute, never blend: every fact, rule and passage names its school and source.
- Never guess input, never substitute silently: ambiguous input stops and asks; unsupported settings fail with a reason.
- Python ≥ 3.11, ruff (line 100), Pydantic v2 frozen models; runtime deps are pinned — do not bump without a plan entry.
- Undecided conventions are profile options; provisional values are listed under `provisional:` in `profiles/calc/*.yaml`.

## Architecture
- `src/astro/calc/` core maths, model, profile, refdata, ephemeris (SwissEphemeris is the **only** importer of `swisseph`), solver, sensitivity, engine, features, dasha, transits
- `src/astro/methods/` school adapters (parashari, bnn) · `src/astro/normalize/` birth input → instant · `src/astro/cli/` CLI + PDF
- `ontology/*.yaml` reference data (status provisional) · `profiles/calc|method/` calculation/method profiles
- Import contracts (`lint-imports`): `astro.calc` must not import `astro.normalize` or `astro.methods`.

## Things the agent gets wrong
<!-- Add one line when the same correction happens twice (G12). Newest first. -->
