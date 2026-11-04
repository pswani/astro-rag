---
paths:
  - "intent/**/plan.md"
---
# Rules for plan.md (Stage 3 — Build, before any code)

Template: `docs/sdlc/templates/plan.md`. Skill: `implementation-plan`.

- **P1 Plan before code.** Produced in plan mode (read-only) from the approved spec (Full track) or intent (Light track). No source edits until the plan is approved (hook: `plan_gate`).
- **P2 Files that change** lists every path in backticks with its action: `` `path/to/file` `` new | modify | delete — reason. Globs only for generated groups. This list is what the plan-sync hook checks commits against.
- **P3 Order of work** in small steps, each independently verifiable, each naming the check that proves it.
- **P4 Proof** maps every `REQ-n` from spec.md to at least one test and lists the exact verification commands with the expected healthy result (e.g. `make test` → "all green").
- **P5 Risks** names what the change could break, the single riskiest step, external limits (rate limits, quotas, migrations), and the mitigation.
- **P6 Alternatives considered** — at least one option not taken and why.
- **P7 Workstreams.** Mark which steps touch disjoint files and can run in parallel worktrees; steps sharing files stay sequential.
- **P8 Rollback.** How to back the change out (revert, feature flag, down-migration). Required for elevated/high risk.
- **P9 Standalone test.** An engineer who never saw the conversation could implement from the plan alone.
- **P10 Approval.** The engineer approves routine plans; elevated/high go to a tech lead/architect (`approved_by`). The agent never sets `status: approved` itself (G2).
- **P11 Stay in sync.** When implementation departs from the plan, update plan.md in the same commit (files, order, risks) and note the deviation in the PR.
