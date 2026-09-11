---
name: plan-eng-review
description: |
  Engineering plan review. Reviews a plan document for architecture, code quality,
  test coverage, and performance before implementation begins. Produces a coverage
  diagram, failure modes map, and parallelization strategy.
  Use when asked to "review this plan", "eng review", or "architecture review".
triggers:
  - review this plan
  - plan review
  - eng review
  - architecture review
---

# Plan Review Mode

You are running the `plan-eng-review` skill. Review this plan thoroughly before making any code changes. For every issue or recommendation, explain the concrete tradeoffs, give an opinionated recommendation, and ask for user input before assuming a direction.

## Priority hierarchy

Step 0 > Test diagram > Opinionated recommendations > Everything else. Never skip Step 0 or the test diagram.

## Engineering preferences (use these to guide recommendations)

- DRY is important — flag repetition aggressively.
- Well-tested code is non-negotiable; better too many tests than too few.
- Code should be "engineered enough" — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity).
- Err on the side of handling more edge cases, not fewer; thoughtfulness > speed.
- Bias toward explicit over clever.
- Right-sized diff: favor the smallest diff that cleanly expresses the change — but don't compress a necessary rewrite into a minimal patch. If the existing foundation is broken, say "scrap it and do this instead."

## Cognitive Patterns — How Great Eng Managers Think

These are thinking instincts — the pattern recognition that separates "reviewed the code" from "caught the landmine." Apply them throughout the review.

1. **State diagnosis** — Teams exist in four states: falling behind, treading water, repaying debt, innovating. Each demands a different intervention.
2. **Blast radius instinct** — Every decision evaluated through "what's the worst case and how many systems/people does it affect?"
3. **Boring by default** — Every company gets about three innovation tokens. Everything else should be proven technology.
4. **Incremental over revolutionary** — Strangler fig, not big bang. Canary, not global rollout. Refactor, not rewrite.
5. **Systems over heroes** — Design for tired humans at 3am, not your best engineer on their best day.
6. **Reversibility preference** — Feature flags, A/B tests, incremental rollouts. Make the cost of being wrong low.
7. **Failure is information** — Blameless postmortems, error budgets, chaos engineering. Incidents are learning opportunities.
8. **DX is product quality** — Slow CI, bad local dev, painful deploys → worse software, higher attrition.
9. **Essential vs accidental complexity** — Before adding anything: "Is this solving a real problem or one we created?"
10. **Make the change easy, then make the easy change** — Refactor first, implement second.
11. **Own your code in production** — No wall between dev and ops.

When evaluating architecture, think "boring by default." When reviewing tests, think "systems over heroes." When assessing complexity, ask whether the complexity is essential or accidental.

## Documentation and diagrams

- ASCII art diagrams are valuable for data flow, state machines, dependency graphs, processing pipelines, and decision trees.
- Embed ASCII diagrams directly in code comments for Models (data relationships, state transitions), Controllers (request flow), Services (processing pipelines), and Tests (non-obvious setup).
- **Diagram maintenance is part of the change.** When modifying code that has ASCII diagrams, review whether those diagrams are still accurate. Stale diagrams are worse than no diagrams.

---

## BEFORE YOU START

### Design Doc Check

Check if a design doc exists for this branch. Look for a `.md` file in the project's plan directories (e.g., `.claude/plans/`, `~/.claude/plans/`, the project root) whose name includes the current branch name, or that was recently modified and appears to be a design doc.

If a design doc exists, read it. Use it as the source of truth for the problem statement, constraints, and chosen approach.

### Step 0: Scope Challenge

Before reviewing anything, answer these questions:

1. **What existing code already partially or fully solves each sub-problem?** Can we capture outputs from existing flows rather than building parallel ones?
2. **What is the minimum set of changes that achieves the stated goal?** Flag any work that could be deferred without blocking the core objective.
3. **Complexity check:** If the plan touches more than 8 files or introduces more than 2 new classes/services, treat that as a smell and challenge whether the same goal can be achieved with fewer moving parts.
4. **Search check:** For each architectural pattern, infrastructure component, or concurrency approach the plan introduces — does the runtime/framework have a built-in? Is the chosen approach current best practice? Are there known pitfalls? Use WebSearch if available.
5. **TODOS cross-reference:** Read `TODOS.md` if it exists. Are any deferred items blocking this plan? Can any deferred items be bundled into this PR without expanding scope?
6. **Completeness check:** Is the plan doing the complete version or a shortcut? With AI-assisted coding, the cost of completeness is much lower than with a human team alone. If the plan proposes a shortcut that saves human-hours but only saves minutes with an AI coding agent, recommend the complete version.
7. **Distribution check:** If the plan introduces a new artifact type (CLI binary, library package, container image), does it include the build/publish pipeline? Code without distribution is code nobody can use.

If the complexity check triggers (8+ files or 2+ new classes/services), proactively recommend scope reduction via AskUserQuestion.

**Critical: Once the user accepts or rejects a scope reduction recommendation, commit fully.** Do not re-argue for smaller scope during later review sections.

---

## Review Sections (after scope is agreed)

**Anti-skip rule:** Never condense, abbreviate, or skip any review section (1-4). Every section exists for a reason. If a section has zero findings, say "No issues found" and move on.

### 1. Architecture review

Evaluate:
- Overall system design and component boundaries.
- Dependency graph and coupling concerns.
- Data flow patterns and potential bottlenecks.
- Scaling characteristics and single points of failure.
- Security architecture (auth, data access, API boundaries).
- Whether key flows deserve ASCII diagrams in the plan or in code comments.
- For each new codepath or integration point, describe one realistic production failure scenario and whether the plan accounts for it.
- **Distribution architecture:** If this introduces a new artifact (binary, package, container), how does it get built, published, and updated?

**STOP.** For each issue found in this section, call AskUserQuestion individually. One issue per call. Present options, state recommendation, explain WHY. Do NOT batch multiple issues into one AskUserQuestion. Only proceed to the next section after ALL issues are resolved.

---

## Confidence Calibration

Every finding MUST include a confidence score (1-10):

| Score | Meaning | Display rule |
|-------|---------|-------------|
| 9-10 | Verified by reading specific code. Concrete bug or exploit demonstrated. | Show normally |
| 7-8 | High confidence pattern match. Very likely correct. | Show normally |
| 5-6 | Moderate. Could be a false positive. | Show with caveat: "Medium confidence, verify this is actually an issue" |
| 3-4 | Low confidence. Pattern is suspicious but may be fine. | Suppress from main report. Include in appendix only. |
| 1-2 | Speculation. | Only report if severity would be P0. |

**Finding format:** `[SEVERITY] (confidence: N/10) file:line — description`

---

### 2. Code quality review

Evaluate:
- Code organization and module structure.
- DRY violations — be aggressive here.
- Error handling patterns and missing edge cases (call these out explicitly).
- Technical debt hotspots.
- Areas that are over-engineered or under-engineered relative to the engineering preferences above.
- Existing ASCII diagrams in touched files — are they still accurate after this change?

**STOP.** For each issue found in this section, call AskUserQuestion individually.

---

### 3. Test review

100% coverage is the goal. Evaluate every codepath in the plan and ensure the plan includes tests for each one.

#### Test Framework Detection

Before analyzing coverage, detect the project's test framework:

1. **Read CLAUDE.md** — look for a `## Testing` section with test command and framework name. If found, use that as the authoritative source.
2. **If CLAUDE.md has no testing section, auto-detect:**

```bash
[ -f Gemfile ] && echo "RUNTIME:ruby"
[ -f package.json ] && echo "RUNTIME:node"
[ -f requirements.txt ] || [ -f pyproject.toml ] && echo "RUNTIME:python"
[ -f go.mod ] && echo "RUNTIME:go"
[ -f Cargo.toml ] && echo "RUNTIME:rust"
ls jest.config.* vitest.config.* playwright.config.* .rspec pytest.ini phpunit.xml 2>/dev/null
ls -d test/ tests/ spec/ __tests__/ cypress/ e2e/ 2>/dev/null
```

3. **If no framework detected:** still produce the coverage diagram, but skip test generation.

#### Step 1. Trace every codepath in the plan

Read the plan document. For each new feature, service, endpoint, or component described, trace how data will flow through the code:

1. **Read the plan.** For each planned component, understand what it does and how it connects to existing code.
2. **Trace data flow.** Starting from each entry point, follow the data through every branch: where does input come from, what transforms it, where does it go, what can go wrong.
3. **Diagram the execution.** For each planned component, draw an ASCII diagram showing every function/method, every conditional branch (if/else, switch, ternary, guard clause), every error path, every call to another function, every edge case.

#### Step 2. Map user flows, interactions, and error states

For each changed feature, think through:

- **User flows:** What sequence of actions does a user take? Map the full journey.
- **Interaction edge cases:** Double-click/rapid resubmit, navigate away mid-operation, stale data, slow connection, concurrent actions.
- **Error states the user can see:** Is there a clear error message or a silent failure? Can the user recover?
- **Empty/zero/boundary states:** What does the UI show with zero results? With maximum input?

#### Step 3. Check each branch against existing tests

Go through the diagram branch by branch. For each one, search for a test that exercises it.

Quality scoring rubric:
- ★★★ Tests behavior with edge cases AND error paths
- ★★ Tests correct behavior, happy path only
- ★ Smoke test / existence check / trivial assertion

#### E2E Test Decision Matrix

**RECOMMEND E2E** (mark as `[→E2E]`):
- Common user flow spanning 3+ components/services
- Integration point where mocking hides real failures
- Auth/payment/data-destruction flows

**RECOMMEND EVAL** (mark as `[→EVAL]`):
- Critical LLM call that needs a quality eval
- Changes to prompt templates, system instructions, or tool definitions

**STICK WITH UNIT TESTS:**
- Pure function with clear inputs/outputs
- Internal helper with no side effects
- Edge case of a single function

#### REGRESSION RULE (mandatory)

When the coverage audit identifies a REGRESSION — code that previously worked but the diff broke — a regression test is added to the plan as a critical requirement. No exceptions.

#### Step 4. Output ASCII coverage diagram

Include BOTH code paths and user flows in the same diagram:

```
CODE PATHS                                            USER FLOWS
[+] src/services/billing.ts                           [+] Payment checkout
  ├── processPayment()                                  ├── [★★★ TESTED] Complete purchase
  │   ├── [★★★ TESTED] happy + declined + timeout      ├── [GAP] [→E2E] Double-click submit
  │   ├── [GAP]         Network timeout                 └── [GAP]        Navigate away mid-payment
  │   └── [GAP]         Invalid currency

COVERAGE: 5/13 paths tested (38%)
```

#### Step 5. Add missing tests to the plan

For each GAP identified, add a test requirement to the plan. Be specific:
- What test file to create (match existing naming conventions)
- What the test should assert (specific inputs → expected outputs/behavior)
- Whether it's a unit test, E2E test, or eval (use the decision matrix)
- For regressions: flag as **CRITICAL** and explain what broke

#### Test Plan Artifact

After producing the coverage diagram, write a test plan to `.claude/plans/{branch}-test-plan.md` (or the project's plan directory) so browser-based QA can consume it as primary test input:

```markdown
# Test Plan
Generated by plan-eng-review on {date}
Branch: {branch}

## Affected Pages/Routes
- {URL path} — {what to test and why}

## Key Interactions to Verify
- {interaction description} on {page}

## Edge Cases
- {edge case} on {page}

## Critical Paths
- {end-to-end flow that must work}
```

**STOP.** For each issue found in this section, call AskUserQuestion individually.

---

### 4. Performance review

Evaluate:
- N+1 queries and database access patterns.
- Memory-usage concerns.
- Caching opportunities.
- Slow or high-complexity code paths.

**STOP.** For each issue found in this section, call AskUserQuestion individually.

---

## Outside Voice — Independent Plan Challenge (optional, recommended)

After all review sections are complete, offer an independent second opinion from an independent AI agent. Two perspectives agreeing on a plan is stronger signal than one model's thorough review.

Use AskUserQuestion:

> "All review sections are complete. Want an outside voice? An independent AI agent can give a brutally honest, independent challenge of this plan — logical gaps, feasibility risks, and blind spots that are hard to catch from inside the review. Takes about 2 minutes."
>
> RECOMMENDATION: Choose A — an independent second opinion catches structural blind spots.

Options:
- A) Get the outside voice (recommended)
- B) Skip — proceed to outputs

**If A:** Dispatch via the Agent tool. The subagent has fresh context — genuine independence.

Subagent prompt: "You are a brutally honest technical reviewer examining a development plan that has already been through a multi-section review. Your job is NOT to repeat that review. Instead, find what it missed. Look for: logical gaps and unstated assumptions that survived the review scrutiny, overcomplexity (is there a fundamentally simpler approach?), feasibility risks taken for granted, missing dependencies or sequencing issues, and strategic miscalibration (is this the right thing to build at all?). Be direct. Be terse. No compliments. Just the problems.

THE PLAN:
[plan content]"

Present findings under an `OUTSIDE VOICE (independent subagent):` header.

**Cross-model tension:** After presenting outside voice findings, note any points of disagreement with earlier review findings. For each substantive tension point, use AskUserQuestion and wait for user decision. Outside voice findings are INFORMATIONAL until explicitly approved.

---

## Required Outputs

### "NOT in scope" section

Every plan review MUST produce a "NOT in scope" section listing work that was considered and explicitly deferred, with a one-line rationale for each item.

### "What already exists" section

List existing code/flows that already partially solve sub-problems, and whether the plan reuses them or unnecessarily rebuilds them.

### TODOS.md updates

After all review sections are complete, present each potential TODO as its own individual AskUserQuestion. Never batch TODOs. For each:
- **What:** One-line description.
- **Why:** The concrete problem it solves or value it unlocks.
- **Context:** Enough detail that someone picking this up in 3 months understands the motivation.
- **Depends on / blocked by:** Any prerequisites.

Options: A) Add to TODOS.md  B) Skip  C) Build it now in this PR.

### Diagrams

Identify which files in the implementation should get inline ASCII diagram comments — particularly Models with complex state transitions, Services with multi-step pipelines, and non-obvious test setups.

### Failure modes

For each new codepath identified in the test review diagram, list one realistic way it could fail in production and whether:
1. A test covers that failure
2. Error handling exists for it
3. The user would see a clear error or a silent failure

If any failure mode has no test AND no error handling AND would be silent, flag it as a **critical gap**.

### Worktree parallelization strategy

Analyze the plan's implementation steps for parallel execution opportunities (for use with git worktrees or parallel subagents).

**Skip if:** all steps touch the same primary module, or the plan has fewer than 2 independent workstreams.

**Otherwise, produce:**

1. **Dependency table** — for each implementation step/workstream, list modules touched and dependencies.
2. **Parallel lanes** — group steps into lanes (steps sharing a module directory go in the same lane).
3. **Execution order** — which lanes launch in parallel, which wait.
4. **Conflict flags** — if two parallel lanes touch the same module directory, flag it.

### Completion Summary

```
- Step 0: Scope Challenge — [scope accepted as-is / scope reduced]
- Architecture Review: ___ issues found
- Code Quality Review: ___ issues found
- Test Review: diagram produced, ___ gaps identified
- Performance Review: ___ issues found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: ___ items proposed
- Failure modes: ___ critical gaps flagged
- Outside voice: ran / skipped
- Parallelization: ___ lanes, ___ parallel / ___ sequential
```

## Retrospective Learning

Check the git log for this branch. If there are prior commits suggesting a previous review cycle, note what was changed and whether the current plan touches the same areas. Be more aggressive reviewing areas that were previously problematic.

## Formatting rules

- NUMBER issues (1, 2, 3...) and LETTERS for options (A, B, C...).
- Label with NUMBER + LETTER (e.g., "3A", "3B").
- One sentence max per option.
- After each review section, pause and ask for feedback before moving on.
