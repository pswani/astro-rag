---
paths:
  - "intent/**/spec.md"
---
# Rules for spec.md (Stage 2 — Design)

Template: `docs/sdlc/templates/spec.md`. Skill: `spec-design`.

- **S1 Approved intent only.** A spec starts from an intent with `status: approved`. Frontmatter `parent:` points to it.
- **S2 Apply the policy skills.** Load every organisational policy skill that applies (brand, security, compliance, UX, API, data, accessibility). List each in *Policy conformance* with its version (git SHA or skill version) and how the spec satisfies it.
- **S3 Testable requirements.** Number every requirement `REQ-1…` (or extend the repo's existing IDs, e.g. `CALC-n`, `DAS-n` from docs/req/requirements.md), trace it to an intent section, and give acceptance criteria a test can check (Given/When/Then or an equivalent observable outcome).
- **S4 Non-functional requirements are explicit:** security & data classification, privacy/PII, performance & limits, accessibility, observability/audit, failure behaviour. "N/A" needs a reason.
- **S5 Flagged concerns section is mandatory** (write "None" if none). Each concern: severity (blocker/major/minor), the policy or constraint involved, why it cannot be fully satisfied, options, and the named policy owner who must resolve it. Contradicting policies are always flagged, never silently resolved.
- **S6 Carry every open question.** Each open question from intent.md is answered (with source) or carried forward with an owner.
- **S7 Design fits the existing system.** Name the components, interfaces/contracts, data changes and UX references (mock link) at the level an engineer can plan against. No code beyond interface sketches.
- **S8 Out of scope** is stated and matches or narrows the intent.
- **S9 Provenance.** Record the prompt (or command) that produced the spec and the skills in force, so the run is reproducible and auditable.
- **S10 Risk class** proposed with justification (see G8). Higher-risk specs name the technical lead who must co-approve.
- **S11 Status.** `draft` until the product owner (and tech lead for elevated/high) approves; all blocker concerns must be resolved first.
