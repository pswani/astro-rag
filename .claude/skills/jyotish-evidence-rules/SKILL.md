---
name: jyotish-evidence-rules
description: Apply the project's evidence rules for chart calculation and rule evaluation. Use whenever writing or changing code in src/astro (calc, methods, normalize, cli), ontology or profile YAML, rule cards, evidence bundles or reports; when designing a feature that computes chart facts, evaluates a rule, cites a source or handles birth data; and when reviewing such code.
---
# Jyotish evidence rules

When you write or change calculation, method, normalisation or reporting code:
1. **Code decides, never the LLM.** Chart facts and rule applicability are computed by code. No path lets model output decide a fact or whether a rule applies.
2. **Unknown is an answer.** If something cannot be determined, return `unknown` with a reason code (`astro.calc.core.status`). Never collapse it to `False`, an empty list or a default.
3. **Never substitute silently.** An unsupported setting or a failure raises/returns a reason; it never falls back to another convention, ephemeris model (e.g. Moshier), method or profile value.
4. **Never guess input.** Ambiguous places, impossible or repeated local times (DST gaps/overlaps) and unconverted calendar dates stop and ask. Never alter a birth time.
5. **Attribute, never blend.** Every fact, rule and passage carries its school and source. Parashari, BNN and others meet only in an explicit comparison.
6. **Reproducible.** Same inputs → same canonical result and content hash; record the versions (profile hash, ephemeris files, tzdata) that produced it. Provisional conventions are profile options listed under `provisional:`.
7. **Private by default.** Raw birth data is never logged, never sent off the machine, and stored only encrypted.

Verify: `make verify` (ruff, import contracts — `astro.calc` independent of `normalize`/`methods`, only the Swiss adapter imports `swisseph` — and pytest). Include its output in your summary. Add a test for every new `unknown` reason or refusal path.
If a rule cannot be met, raise a Flagged concern (spec) or stop and tell the maintainer.

---
Owner: Prashant Wani · Source of truth: `intent/0001-jyotish-evidence-layer.md` (Constraints), `docs/design/design.md` · Skill version: 1.0.0
Enforcement: import-linter contracts (CI, deterministic) for layering; tests for reason codes; `pr-review` Compliance pass and REVIEW.md "Important" definition for the rest.
