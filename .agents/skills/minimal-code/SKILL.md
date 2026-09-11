---
name: minimal-code
description: Use before writing any code — write the least code that fully solves the task (YAGNI, stdlib-first, no unrequested abstractions) to save tokens and reduce maintenance.
---

# Minimal Code (lazy senior dev)

The best code is the code you never wrote. Before writing anything, walk this ladder and stop at the first rung that solves the task:

1. **Does it already exist?** Reuse an existing function, file, or builtin before writing new code.
2. **Can the language/stdlib do it?** Prefer the standard library and built-in platform features over a dependency or a hand-rolled version.
3. **Is the abstraction requested?** Do not add layers, config, interfaces, or generality nobody asked for. Solve the concrete case.
4. **Is it the shortest correct version?** Prefer deletion over addition, boring over clever, one obvious path over branching flexibility.
5. **Did the task actually ask for this?** Build only what was requested — no speculative features (YAGNI).

Rules:
- Deletion over addition. Boring over clever. No abstractions that were not requested.
- Prefer the standard library and existing code over new code or new dependencies.
- Mark an intentional simplification with a short `minimal-code:` comment so reviewers see it was deliberate.

This saves tokens (less generated code), shrinks the review surface, and lowers maintenance — complementary to rtk, which compresses command output. Adapted from the MIT-licensed "ponytail" ruleset (github.com/DietrichGebert/ponytail).
