---
name: yoke-retrofit
description: Use when asked to "retrofit", "yoke this project", or set up the Yoke harness in a project — runs the shared setup wizard and configures the same behavior for the supported Yoke harnesses.
---

# Yoke Retrofit

Set up or update Yoke through the shared `yoke setup` contract.

1. Inspect the project and identify the current host (`claude`, `codex`, `gemini`, `qwen`, `opencode`, `kilo`, or `pi`).
2. Ask these setup questions one at a time and give a direct recommendation:
   - target agents (recommend the current host; use `all` for deliberately cross-agent projects),
   - code-graph tool,
   - autonomous loop on/off,
   - default runner (recommend the current host),
   - decision mode: `auto` or `critical`.
3. Recommend the code graph based on this project:
   - **Serena** is LSP-accurate and best for large typed codebases or systematic symbol refactors where a missed reference is costly. It needs a language server per language.
   - **graphify** is fast and multimodal, and is best for exploration, migration, onboarding, or mixed code and document repositories. Its graph is an index and can become stale.
4. Apply the answers without a second round of prompts:
   `yoke setup . --yes --host=<host> --agent=<agents> --code-graph=<choice> --runner=<runner> --decision-policy=<auto|critical> --loop|--no-loop`.
   A human who runs `yoke setup .` directly receives the same five terminal questions.
5. Show the generated report and backup paths. Existing files are backed up under `.yoke/backup/`; settings are merged where supported.
6. If an old generated `CLAUDE.md` or `GEMINI.md` contained project-specific instructions, restore them inside its `<!-- yoke:preserve:start -->` / `<!-- yoke:preserve:end -->` block. Preserve blocks survive every later retrofit.

The generated harness includes the provider-neutral `yoke-workflow` skill. It owns the planning questions, approved-plan handoff, autonomous stories, and critical-decision resume flow.
