@AGENTS.md

## Claude Code specifics
- Start non-trivial work in **plan mode**; the `implementation-plan` skill writes `intent/<id>/plan.md`.
- Stage skills (plugin `ai-native-sdlc`): `intent-capture` → `spec-design` → `implementation-plan` → `build-and-verify` / `bugfix-test-first` → `pr-review` / `pr-babysit`; audit: `sdlc-trace`. Policy skill: `jyotish-evidence-rules`.
- Before reporting done: `make verify`, then the `verifier` subagent.
