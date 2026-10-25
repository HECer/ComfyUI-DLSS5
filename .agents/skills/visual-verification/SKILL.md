---
name: visual-verification
description: Use for UI or web changes that need browser-level checks in addition to code-level verification.
---

# Visual verification

Unit tests can miss a blank page, a broken route, a runtime console error, or a visual regression.
Use the project's existing tools to check affected user flows when browser verification is
requested or required by the project.

## 1. Use configured checks

Inspect the project scripts and existing browser-test setup. Reuse configured type, unit, design,
accessibility, and browser-flow checks that apply to the change. Do not invent command names or add
test dependencies as part of this skill.

## 2. Check affected flows

If browser automation is already configured, start the app and verify the changed routes and key
interactions. Check that the page renders, expected landmarks are visible, and the browser console
has no new errors.

## 3. Capture useful evidence

Capture a screenshot or short recording when it helps explain a visual result or reproduce a
failure. Save it to the project's established evidence location; otherwise use a temporary folder.

## Rule

Report which configured checks ran, which flows were inspected, and any remaining visual or runtime
issues. Do not claim browser verification when no browser check ran.
