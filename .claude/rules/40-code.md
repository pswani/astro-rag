---
paths:
  - "src/**"
  - "scripts/**"
---
# Rules for generated code (Stage 3 — Build)

- **C1 Follow the approved plan** in its order. Departures update plan.md in the same commit (P11).
- **C2 Conventions come from CLAUDE.md/AGENTS.md and policy skills.** Load the relevant policy skill before touching its domain (API, security, data, UI/brand, accessibility).
- **C3 No new dependencies or version bumps** unless plan.md lists them and the owner is named.
- **C4 Never edit generated or frozen code** (see `protected_block` in `.sdlc/config.json`); change the source/schema that generates it.
- **C5 Minimal diff.** No drive-by refactors, renames or reformatting outside the plan; propose them as a separate intent.
- **C6 Security by default:** validate input at boundaries, least privilege, parameterised queries, no PII/secrets in logs or errors, audit events for state changes where policy requires.
- **C7 Observability.** New behaviour emits the logs/metrics/traces the spec's observability requirements name, so Stage 6 can monitor it.
- **C8 Commits** are titled `[<change-id>] <imperative summary>` and the body says *why*. One logical step per commit.
- **C9 Done means verified.** Run the verification commands, paste the output, then run the `verifier` subagent before reporting done (G5).
