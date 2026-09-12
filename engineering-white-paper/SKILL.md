---
name: engineering-white-paper
description: Write a practitioner white paper explaining an engineering practice — what it is, when to use it, its benefits, its drawbacks and mitigations, and how to adopt it — in the house structure used across this collection's practice papers. Use when asked to write a white paper, explain or document an engineering practice, produce a facilitation guide or kata brief, make the case for a way of working, or turn hard-won project experience into something reusable by other teams. Covers the section skeleton, the honesty requirements, and the difference between a white paper and a skill.
license: MIT
metadata:
  version: "1.0.0"
---

# Writing an engineering practice white paper

A practice white paper explains *one* way of working to a practitioner who might adopt it: what it is, when it applies, what it costs, and how to start. It is not marketing, not a literature review, and not a tutorial.

The test it must pass: **a reader who finishes it can decide whether to adopt the practice, and knows what the first week looks like.** A paper that leaves the reader persuaded but with no idea where to begin has failed, and so has one that describes mechanics without ever saying when the practice is a bad idea.

## What a white paper is, versus a skill

These are different artefacts, and conflating them produces something that serves neither.

| | White paper | Skill |
|---|---|---|
| Reader | A human deciding whether to adopt | An agent doing the task now |
| Answers | *Why*, *when*, *what it costs* | *How*, in this situation |
| Register | Prose, argued, with analogies | Imperative, checklist-driven |
| Length | 1,500–3,000 words | As short as possible |
| Success | The reader can decide and start | The task is done correctly |

If you are writing a checklist, write a skill. If you are making a case, write the paper. A good pairing does both, and cross-references — several skills in this collection are the operational half of a paper.

## The structure

The house structure, in order. Skip a section only when it genuinely does not apply, and never skip section 4.

```markdown
### White Paper: <Practice>: <the promise, stated concretely>

<Opening: the problem in the reader's world, in two or three paragraphs.
Name the failure mode they will recognise from their own project.
End by stating what this paper will provide.>

### 1. What is <practice>?

<Definition. Attribute the origin if it has one. Then "The Core Tenets" as a
short bulleted list — the three or four properties that make it this practice
and not a neighbouring one. Close with one analogy.>

### 2. When to Use It

<Bulleted scenarios where it earns its cost. Be specific about the conditions.>

### 3. Core Benefits

<Two to four subsections, each naming a mechanism, not an adjective.
Not "improves quality" — "converts estimation from guesswork to grounded
data, because the team has built the real thing once".>

### 4. Drawbacks and Mitigations

<Every drawback paired with its mitigation. This section is mandatory and
is what makes the paper credible.>

### 5. How to Adopt It

<A concrete sequence. Week one, week two. What to measure. Where to start
in a legacy codebase.>

### 6. Conclusion

<What changes for a team that does this. One paragraph, no new claims.>
```

## What makes it good

**Open in the reader's world, not with the practice.** "Traditional approaches, where teams work in silos on detailed specifications for months, frequently lead to wasted effort, architectural dead ends, and products that fail to meet market needs" — the reader recognises that before they have heard of the practice. Then introduce it as the response.

**Define by exclusion.** State what the practice is *not*, because that is where the reader's existing misconception lives. "It is not a prototype or a mock-up" does more definitional work than a paragraph of positive description.

**One analogy, concrete and mechanical.** The go-kart: a frame, an engine, wheels and steering; it cannot do much, but it proves the concept end to end, and you add the chassis and the seats iteratively. It works because it maps onto the tenets one-for-one. One good analogy beats three loose ones — and a second analogy usually contradicts the first.

**Name mechanisms, not adjectives.** Every benefit should answer "by what means?" A claim that survives the question is worth making; one that does not is filler.

**Be honest about cost.** The drawbacks section is where a paper earns its authority, and it is the first thing an experienced reader looks for. Real ones, named plainly:

- *Risk of over-engineering* → relentlessly do the simplest thing that could work; YAGNI; refactor later.
- *Perception of slow initial progress* → set the expectation with stakeholders before starting; show the deployed skeleton, not the code.
- *It does not fit every context* → say which contexts, and what to do there instead.

A paper with no drawbacks section reads as advocacy and gets discounted entirely.

**Make it actionable.** Commands, file layouts, a first-week sequence, what to measure. A practice the reader cannot start on Monday is a practice they will not start.

**Attribute.** Name the originator where there is one (Cockburn for the walking skeleton, Beck for TDD, Adzic for specification by example), and link the primary source. Borrowed ideas presented as your own are the fastest way to lose a technical reader.

## What to avoid

- **Straw-manning the alternative.** The reader may currently be doing the thing you are arguing against, and for reasons. Describe it fairly, then say where it breaks down.
- **Unfalsifiable claims.** "Dramatically improves delivery" says nothing. Give a mechanism, or a number with its context, or cut it.
- **Numbers without provenance.** No invented percentages. If a figure comes from a study or from your own project, say which and say the sample.
- **Tooling as practice.** A paper about Cucumber is a tooling guide; a paper about specification by example is a practice paper that mentions Cucumber. Know which you are writing.
- **Real client or colleague identities** in an example drawn from experience. Anonymise the context, keep the mechanics. See `synthetic-test-data`.
- **Ending on a summary of the paper.** End on what changes for the team.

## Companion formats

Several of these practices are better taught than read. Where that applies, pair the paper with one of:

- **A kata** — a repeatable exercise with a starting codebase, in more than one language where possible, so a reader can practise the mechanics rather than agree with them. Give it a clear finish condition.
- **A facilitation guide** — timings, group sizes, materials, the debrief questions, and the failure modes a facilitator should watch for. This is what makes a workshop repeatable by someone who did not design it.
- **A worked example repository** — the practice applied to one small domain, with the commit history as the teaching artefact. See `outside-in-tdd`; a history that shows red-then-green teaches more than any prose about it.
- **A skill** — the operational checklist for an agent or a practitioner mid-task.

## Before publishing

- [ ] Opens with the reader's problem, not the practice
- [ ] Defines the practice, including what it is *not*, with tenets and one analogy
- [ ] Origin attributed and primary source linked
- [ ] "When to use" names conditions, not vague suitability
- [ ] Every benefit names a mechanism
- [ ] Drawbacks section present, honest, each with a mitigation
- [ ] Adoption section is concrete enough to start on Monday
- [ ] No invented numbers; every figure has provenance
- [ ] Alternatives described fairly
- [ ] No real client, colleague or customer identities
- [ ] Cross-references the companion kata, guide or skill where one exists

## Related skills

- `spec-by-example-issue` — the operational half of a specification-by-example paper
- `outside-in-tdd` — the operational half of a TDD paper
- `deliberate-decisions` — recording a decision at project scale rather than practice scale
- `docs-drift-guard` — keeping a published paper's code examples from rotting
