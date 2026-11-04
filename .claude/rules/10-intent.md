---
paths:
  - "intent/**/intent.md"
---
# Rules for intent.md (Stage 1 — Plan)

Template: `docs/sdlc/templates/intent.md`. Skill: `intent-capture`.

- **I1 Originator's words.** Capture what the originator means, in their terms. Do not translate into solution language or story points.
- **I2 Required sections**, in order: Problem · Proposed outcome · Affected users and systems · Constraints · Out of scope · Success measures · Open questions. Write "None known" rather than deleting a section.
- **I3 What and why, not how.** No implementation design, file names or technology choices unless the originator states them as a constraint.
- **I4 Measurable success.** At least one success measure with a baseline or target (e.g. "status-only calls fall from ~33% of call time").
- **I5 No invented facts.** Anything not confirmed by the originator or a cited source is an Open question or marked `(assumption)`.
- **I6 Origin and evidence.** Frontmatter `origin: idea | ticket | incident | monitor`. Incident/monitor intents include the evidence (metric, band breached, timestamps, links) in the Problem section.
- **I7 One page.** If it needs more, it is two intents or the extra belongs in the spec.
- **I8 Status.** Created as `status: draft`. Only the product owner accepts it (merge of the intent PR, then `status: approved`, `approved_by`, `approved_at`). Rejected intents are closed with the reason recorded, not deleted.
- **I9 Frozen after spec.** Changes to an approved intent after spec.md exists are rework: make them in a new commit titled `[<id>] intent rework: <why>` so they are measurable.
