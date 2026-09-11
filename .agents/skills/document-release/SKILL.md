---
name: document-release
description: |
  Post-ship documentation update. Runs after ship (code committed, PR exists) but before
  the PR merges. Updates every documentation file to reflect the changes in the diff:
  README, CHANGELOG, ARCHITECTURE, CONTRIBUTING, TODOS.md, VERSION.
  Use when asked to "update docs", "document the release", or "update the changelog".
triggers:
  - update docs
  - document the release
  - update the changelog
  - document-release
---

# Document Release: Post-Ship Documentation Update

You are running the `document-release` workflow. This runs **after `ship`** (code committed, PR exists or about to exist) but **before the PR merges**. Your job: ensure every documentation file in the project is accurate, up to date, and written in a friendly, user-forward voice.

You are mostly automated. Make obvious factual updates directly. Stop and ask only for risky or subjective decisions.

For prose changes, use `no-ai-slop` in Detect mode before editing, then make only the named,
voice-preserving fixes that apply. Check the result against that skill's `eval.md`. This review is
advisory, not a mechanical release gate; factual accuracy and the writer's intended meaning take
priority over stylistic uniformity.

**Only stop for:**
- Risky/questionable doc changes (narrative, philosophy, security, removals, large rewrites)
- VERSION bump decision (if not already bumped)
- New TODOS items to add
- Cross-doc contradictions that are narrative (not factual)

**Never stop for:**
- Factual corrections clearly from the diff
- Adding items to tables/lists
- Updating paths, counts, version numbers
- Fixing stale cross-references
- CHANGELOG voice polish (minor wording adjustments)
- Marking TODOS complete
- Cross-doc factual inconsistencies (e.g., version number mismatch)

**NEVER do:**
- Overwrite, replace, or regenerate CHANGELOG entries — polish wording only, preserve all content
- Bump VERSION without asking — always use AskUserQuestion for version changes
- Use `Write` tool on CHANGELOG.md — always use `Edit` with exact `old_string` matches

---

## Step 0: Detect platform and base branch

Detect the git hosting platform from the remote URL:

```bash
git remote get-url origin 2>/dev/null
```

- URL contains "github.com" → platform is **GitHub**
- URL contains "gitlab" → platform is **GitLab**
- Otherwise check: `gh auth status 2>/dev/null` → GitHub; `glab auth status 2>/dev/null` → GitLab

Determine the base branch (target of the PR, or the repo's default):

- GitHub: `gh pr view --json baseRefName -q .baseRefName` or `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`
- GitLab: `glab mr view -F json 2>/dev/null` → extract `target_branch`
- Fallback: `git symbolic-ref refs/remotes/origin/HEAD`, then `main`, then `master`

Use it as `<base>` in all subsequent commands.

---

## Step 1: Pre-flight & Diff Analysis

1. Check the current branch. If on the base branch, **abort**: "You're on the base branch. Run from a feature branch."

2. Gather context about what changed:

```bash
git diff <base>...HEAD --stat
git log <base>..HEAD --oneline
git diff <base>...HEAD --name-only
```

3. Discover all documentation files in the repo:

```bash
find . -maxdepth 2 -name "*.md" -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.context/*" | sort
```

4. Classify the changes into categories relevant to documentation:
   - **New features** — new files, new commands, new skills, new capabilities
   - **Changed behavior** — modified services, updated APIs, config changes
   - **Removed functionality** — deleted files, removed commands
   - **Infrastructure** — build system, test infrastructure, CI

5. Output a brief summary: "Analyzing N files changed across M commits. Found K documentation files to review."

---

## Step 2: Per-File Documentation Audit

Read each documentation file and cross-reference it against the diff:

**README.md:**
- Does it describe all features and capabilities visible in the diff?
- Are install/setup instructions consistent with the changes?
- Are examples, demos, and usage descriptions still valid?
- Are troubleshooting steps still accurate?

**ARCHITECTURE.md:**
- Do ASCII diagrams and component descriptions match the current code?
- Are design decisions and "why" explanations still accurate?
- Be conservative — only update things clearly contradicted by the diff. Architecture docs describe things unlikely to change frequently.

**CONTRIBUTING.md — New contributor smoke test:**
- Walk through the setup instructions as if you are a brand new contributor.
- Are the listed commands accurate? Would each step succeed?
- Do test tier descriptions match the current test infrastructure?
- Are workflow descriptions (dev setup, build steps, etc.) current?
- Flag anything that would fail or confuse a first-time contributor.

**CLAUDE.md / project instructions:**
- Does the project structure section match the actual file tree?
- Are listed commands and scripts accurate?
- Do build/test instructions match what's in package.json (or equivalent)?

**Any other .md files:**
- Read the file, determine its purpose and audience.
- Cross-reference against the diff to check if it contradicts anything the file says.

For each file, classify needed updates as:

- **Auto-update** — Factual corrections clearly warranted by the diff: adding an item to a table, updating a file path, fixing a count, updating a project structure tree.
- **Ask user** — Narrative changes, section removal, security model changes, large rewrites (more than ~10 lines in one section), ambiguous relevance, adding entirely new sections.

---

## Step 3: Apply Auto-Updates

Make all clear, factual updates directly using the Edit tool.

For each file modified, output a one-line summary describing **what specifically changed** — not just "Updated README.md" but "README.md: added /new-skill to skills table, updated skill count from 9 to 10."

**Never auto-update:**
- README introduction or project positioning
- ARCHITECTURE philosophy or design rationale
- Security model descriptions
- Do not remove entire sections from any document

---

## Step 4: Ask About Risky/Questionable Changes

For each risky or questionable update identified in Step 2, use AskUserQuestion with:
- Context: project name, branch, which doc file, what we're reviewing
- The specific documentation decision
- `RECOMMENDATION: Choose [X] because [one-line reason]`
- Options including C) Skip — leave as-is

Apply approved changes immediately after each answer.

---

## Step 5: CHANGELOG Voice Polish

**CRITICAL — NEVER CLOBBER CHANGELOG ENTRIES.**

This step polishes voice. It does NOT rewrite, replace, or regenerate CHANGELOG content.

**Rules:**
1. Read the entire CHANGELOG.md first. Understand what is already there.
2. Only modify wording within existing entries. Never delete, reorder, or replace entries.
3. Never regenerate a CHANGELOG entry from scratch. The entry was written by `ship` from the actual diff and commit history. It is the source of truth. You are polishing prose, not rewriting history.
4. If an entry looks wrong or incomplete, use AskUserQuestion — do NOT silently fix it.
5. Use Edit tool with exact `old_string` matches — never use Write to overwrite CHANGELOG.md.

**If CHANGELOG was not modified in this branch:** skip this step.

**If CHANGELOG was modified in this branch**, review the entry for voice:

- **Sell test:** Would a user reading each bullet think "oh nice, I want to try that"? If not, rewrite the wording (not the content).
- Lead with what the user can now **do** — not implementation details.
- "You can now..." not "Refactored the..."
- Flag and rewrite any entry that reads like a commit message.
- Internal/contributor changes belong in a separate "### For contributors" subsection.
- Auto-fix minor voice adjustments. Use AskUserQuestion if a rewrite would alter meaning.

---

## Step 6: Cross-Doc Consistency & Discoverability Check

After auditing each file individually, do a cross-doc consistency pass:

1. Does the README's feature/capability list match what CLAUDE.md (or project instructions) describes?
2. Does ARCHITECTURE's component list match CONTRIBUTING's project structure description?
3. Does CHANGELOG's latest version match the VERSION file?
4. **Discoverability:** Is every documentation file reachable from README.md or CLAUDE.md? If ARCHITECTURE.md exists but neither README nor CLAUDE.md links to it, flag it.
5. Flag any contradictions between documents. Auto-fix clear factual inconsistencies (e.g., a version mismatch). Use AskUserQuestion for narrative contradictions.

---

## Step 7: TODOS.md Cleanup

If TODOS.md does not exist, skip this step.

1. **Completed items not yet marked:** Cross-reference the diff against open TODO items. If a TODO is clearly completed by the changes in this branch, move it to the Completed section with `**Completed:** vX.Y.Z (YYYY-MM-DD)`. Be conservative — only mark items with clear evidence in the diff.

2. **Items needing description updates:** If a TODO references files or components that were significantly changed, its description may be stale. Use AskUserQuestion to confirm whether the TODO should be updated, completed, or left as-is.

3. **New deferred work:** Check the diff for `TODO`, `FIXME`, `HACK`, and `XXX` comments. For each one that represents meaningful deferred work (not a trivial inline note), use AskUserQuestion to ask whether it should be captured in TODOS.md.

---

## Step 8: VERSION Bump Question

**CRITICAL — NEVER BUMP VERSION WITHOUT ASKING.**

1. **If VERSION does not exist:** Skip silently.

2. Check if VERSION was already modified on this branch:

```bash
git diff <base>...HEAD -- VERSION
```

3. **If VERSION was NOT bumped:** Use AskUserQuestion:
   - RECOMMENDATION: Choose C (Skip) because docs-only changes rarely warrant a version bump
   - A) Bump PATCH (X.Y.Z+1) — if doc changes ship alongside code changes
   - B) Bump MINOR (X.Y+1.0) — if this is a significant standalone release
   - C) Skip — no version bump needed

4. **If VERSION was already bumped:** Check whether the bump still covers the full scope of changes on this branch:
   a. Read the CHANGELOG entry for the current VERSION. What features does it describe?
   b. Read the full diff. Are there significant changes NOT mentioned in the CHANGELOG entry for the current version?
   c. **If the CHANGELOG entry covers everything:** Skip — output "VERSION: Already bumped to vX.Y.Z, covers all changes."
   d. **If there are significant uncovered changes:** Use AskUserQuestion explaining what the current version covers vs what's new, and ask whether to bump to next patch or add changes to the existing entry.

---

## Step 9: Commit & Output

**Empty check first:** Run `git status` (never use `-uall`). If no documentation files were modified, output "All documentation is up to date." and exit without committing.

**Commit:**

1. Stage modified documentation files by name (never `git add -A` or `git add .`).
2. Create a single commit:

```bash
git commit -m "docs: update project documentation for vX.Y.Z"
```

3. Push to the current branch:

```bash
git push
```

**PR/MR body update (idempotent, race-safe):**

1. Read the existing PR/MR body (use the platform detected in Step 0):
   - GitHub: `gh pr view --json body -q .body`
   - GitLab: `glab mr view -F json | python3 -c "import sys,json; print(json.load(sys.stdin).get('description',''))"`

2. If the body already contains a `## Documentation` section, replace that section with updated content. If not, append a `## Documentation` section at the end.

3. The Documentation section should include a **doc diff preview** — for each file modified, describe what specifically changed.

4. Write the updated body back:
   - GitHub: `gh pr edit --body "..."`
   - GitLab: `glab mr update -d "..."`

5. If no PR/MR exists: skip with message "No PR/MR found — skipping body update."

**Structured doc health summary (final output):**

```
Documentation health:
  README.md       [status] ([details])
  ARCHITECTURE.md [status] ([details])
  CONTRIBUTING.md [status] ([details])
  CHANGELOG.md    [status] ([details])
  TODOS.md        [status] ([details])
  VERSION         [status] ([details])
```

Where status is one of:
- Updated — with description of what changed
- Current — no changes needed
- Voice polished — wording adjusted
- Not bumped — user chose to skip
- Already bumped — version was set by ship
- Skipped — file does not exist

---

## Important Rules

- **Read before editing.** Always read the full content of a file before modifying it.
- **Never clobber CHANGELOG.** Polish wording only. Never delete, replace, or regenerate entries.
- **Never bump VERSION silently.** Always ask.
- **Be explicit about what changed.** Every edit gets a one-line summary.
- **Discoverability matters.** Every doc file should be reachable from README or CLAUDE.md.
- **Voice: friendly, user-forward.** Write like you're explaining to a smart person who hasn't seen the code.
