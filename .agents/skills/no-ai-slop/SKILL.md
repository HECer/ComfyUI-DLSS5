---
name: no-ai-slop
description: Edit prose into clearer, more direct writing while preserving the writer's voice, or detect named AI-slop patterns without rewriting or guessing authorship. Use for documentation, release notes, product copy, or prose audits; do not trigger for code-only work.
---

# No AI slop

Preserve the writer's point and voice while making the prose clearer and more alive. Remove observed
patterns without turning distinctive writing into generic polished copy.

## Choose the job

**Edit (default).** Make the minimum effective edit. Return the full edited draft and a short
**What changed** section.

**Detect.** Name every pattern from this skill that appears, quote the affected line, and give a
short fix. Do not rewrite, score the draft, or guess whether AI wrote it. Offer an edit after the
report.

If no draft was provided, ask for it. Ask one audience/format question only when the answer would
materially change the edit. If the goal is unclear, ask what the reader should think, feel, or do.

## Editing principles

- Read the full draft first and identify its point plus the vocabulary, cadence, bluntness, humor,
  uncertainty, digressions, and polish level worth preserving.
- Make the minimum effective change. Fix observed patterns, errors, repetition, and unclear
  passages. Leave strong sentences alone.
- Keep the writer's meaning. Do not invent claims, examples, statistics, sources, or opinions.
- Lead with the point when setup adds nothing. Keep setup that adds context, tension, or character.
- Open up tangled prose without flattening its cadence. Keep clear fragments and changes in pace.
- Prefer concrete facts, mechanisms, consequences, and judgments over abstract importance.
- Use the portability test: a sentence that could move unchanged to another product or company is
  probably filler unless it carries a necessary general rule.
- Let facts and examples carry emphasis. Remove commentary that tells the reader what is important
  when the prose already shows it.
- Prefer direct verbs and active voice when they are clearer.
- Preserve useful edge, strong opinions, humor, and honest uncertainty.
- Keep the existing structure unless it hurts the piece. Report any meaningful reorganization.
- Preserve precise technical and domain terms. A word that is empty in marketing copy can still be
  correct in a product vocabulary. In Yoke, **coding harness** is an established, precise term; do
  not replace it merely because "harness" is often vague elsewhere.

## Words and phrases to inspect

Remove these when they add no precise meaning: delve, foster, leverage, utilize, facilitate,
empower, streamline, robust, cutting-edge, paradigm shift, game changer, tapestry, realm, beacon,
multifaceted, meticulous, intricate, paramount, transformative, elevate, embark, supercharge,
harness, ever-evolving.

Inspect often-empty adverbs such as just, literally, honestly, simply, actually, truly,
fundamentally, importantly, crucially, inherently, and inevitably. Keep one when it carries real
emphasis, uncertainty, contrast, or spoken rhythm.

Inspect filler such as "it's worth noting," "at the end of the day," "when it comes to," "at its
core," "in today's world," "the reality is," "in terms of," "going forward," and "let's dive in."
Cut it when it delays the point.

The lists above are prompts for judgment, not blind replacements. Quoted examples, precise domain
language, and the writer's recognizable voice take precedence.

## Patterns to cut

- **Binary contrasts:** "This is not X. It's Y." State Y directly.
- **Throat-clearing:** "Here's the thing," "Let me be clear," or "The truth is." Start with the
  point.
- **Faux-insight setups:** "What most people get wrong" or "The part everyone misses." Make the
  claim stand on evidence.
- **Colon reveals:** a dramatic noun phrase followed by a lowercase reveal. Use a plain sentence;
  reserve colons for lists, labels, and quotations.
- **Superficial analysis:** trailing clauses such as "highlighting" or "underscoring" that label
  significance instead of explaining a mechanism or consequence.
- **Importance puffery:** "marks a pivotal moment," "plays a vital role," or "stands as a
  testament." State the fact.
- **Interpretive metadiscourse:** "The key point is," "As you can see," "This distinction matters,"
  or a redundant "In other words." Delete it or add the missing support.
- **Weasel attribution:** "experts agree," "studies show," or "widely regarded as." Name the source
  or flag the unsupported claim.
- **Fake-strong verbs:** prefer "is" or "has" when they are clearer; otherwise name what the thing
  actually does.
- **Synonym cycling:** repeat the correct term instead of rotating agent, assistant, and tool for
  style.
- **Negative listing:** "Not X. Not Y. Z." State Z.
- **Dramatic fragmentation:** stacked punchy fragments or "That's it. That's the whole thing."
- **Robotic rhythm:** repeated sentence shapes, identical paragraph structures, or forced symmetry.
- **Rhetorical setups:** "What if I told you," "Plot twist," and self-answered question/answer pairs.
- **Fake-profound kickers:** delete the decorative final metaphor or mic-drop line. End on the last
  concrete point or next action.
- **Summary-recap endings:** remove a final paragraph that merely repeats the piece.
- **Formatting slop:** emoji headings, decorative bold, bullets that should be sentences, and
  headings over tiny sections.
- **Em-dash clusters:** use a comma, period, or parentheses unless the dash clearly improves the
  sentence. Short copy usually needs none.

## Workflow

1. Read the whole draft and identify the point plus three to five voice signals internally.
2. In Detect mode, return named findings with quoted lines and short fixes, then stop.
3. In Edit mode, make the minimum useful changes.
4. Read [eval.md](eval.md) and check the result directly. Fix each failed check.
5. Return the full edited draft and **What changed**.

This skill reports observable prose patterns. It never classifies authorship.
