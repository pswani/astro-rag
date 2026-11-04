---
paths:
  - "CLAUDE.md"
  - "AGENTS.md"
  - ".claude/**"
  - ".sdlc/**"
  - "evals/**"
---
# Rules for agent configuration: CLAUDE.md, AGENTS.md, skills, subagents, hooks, settings, evals

Agent configuration steers every session, so it is reviewed and regression-tested like code.

- **A1 CLAUDE.md/AGENTS.md stay under one page:** commands (with a healthy-output example), conventions that matter, architecture map, "things the agent gets wrong". Nothing a new joiner would not need on day one; nothing stale.
- **A2 One home for shared instructions.** AGENTS.md holds the shared content (read by Codex and other agents); CLAUDE.md imports it with `@AGENTS.md` and adds only Claude-specific notes.
- **A3 Skills encode institutional knowledge** that must be applied consistently: one policy per skill, a named owner and source of truth, frontmatter `description` that says *when* it triggers. Content that belongs in CLAUDE.md or a prompt does not become a skill.
- **A4 Policy owners sign off skill changes** (CODEOWNERS on the skill folder).
- **A5 Must-hold policies get a deterministic backstop:** a hook, CI check or review pass (G10). Record which one in the skill's "Enforcement" section.
- **A6 Hooks are fast and file-scoped.** A block explains itself and names the route to approval. Heavy checks (full test suite) belong at commit/PR/CI. Non-negotiable hooks live in managed settings, not project files.
- **A7 Subagents get least privilege:** the minimum tools, a clear "when to use", and report-only unless their purpose is to write.
- **A8 Every config change runs the eval suite** (`evals/`). A drop in pass rate blocks merge until reviewed.
- **A9 Evals are real tasks:** prompt + objective checks (tests pass, lint clean, behaviour unchanged, policy followed). Retire cases that no longer discriminate; add one per incident.
