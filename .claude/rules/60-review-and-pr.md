---
paths:
  - "REVIEW.md"
  - ".github/pull_request_template.md"
---
# Rules for pull requests and reviews (Stage 5 — Deploy)

Also applied by the `pr-review` and `pr-babysit` skills whenever a PR is opened or reviewed.

- **R1 PR description** contains: change ID and links to intent.md / spec.md / plan.md · what changed and why · verification evidence (commands + output summary, screenshots for UI) · risk class and required approver · plan deviations (or "none") · rollback.
- **R2 Review runs fixed passes** from REVIEW.md: Bugs · Security · Compliance (against spec.md, plan.md, design principles, policy skills). Tag each finding with its pass.
- **R3 Severity.** *Important* = breaks behaviour, leaks data, or breaches a policy/rule. Everything else is a *Nit*; report at most five nits and summarise the rest as a count. Mark *Pre-existing* issues separately.
- **R4 Findings are actionable:** file:line, what is wrong, a concrete failure scenario, the rule or policy ID it breaks, and the suggested fix.
- **R5 Do not report** generated files, anything CI already enforces, or style the formatter owns.
- **R6 Separation of duties.** The agent that wrote the code never approves it. Findings inform, they do not approve or block; code-owner approval via branch protection decides.
- **R7 Close the loop.** A finding raised a second time becomes a CLAUDE.md/AGENTS.md entry in that PR (G12). Flag when a change makes CLAUDE.md outdated.
- **R8 Addressing comments** (babysitting): fix, push, and reply on the thread with what changed; never resolve a thread you did not fix, never force-push over review history, stop when only code-owner approval remains.
