---
name: literature-methods-review
description: Choose the most relevant recent paper for a course presentation and write a methods map of all related work compared along the way, with verified venues and an exclusion list. Use when asked to find, compare or present papers related to a research project, or to write a related-work survey that maps borrowed methods to the project's next steps.
---

# Literature methods review

Worked example: the EviBound "second-round presentation" research (final pick
SimuHome, ICLR 2026 Oral; 29 compared papers in six method families) and
`docs/week12_direction_review.md`.

## Inputs to collect first

- The project's own state: research question, latest results, known weak
  points, planned next steps. Read the repository, not memory.
- Constraints from the person: venue tier ("top conference or journal"),
  recency window ("last year"), and the **exclusion list** (papers already
  presented by classmates or by the person). Normalise titles before matching;
  a paper can appear under a short name (e.g. VIRF = "Grounding Generative
  Planners in Verifiable Logic").

## Procedure

1. **Search wide, by mechanism.** Query for each part of the project's
   pipeline (the domain, the attack, the defense, the evaluation method), not
   just the topic. Use `deep-research` for breadth.
2. **Verify every venue claim** on the venue's own page or proceedings, not a
   preprint footer. Record tier (top venue / journal / workshop / preprint)
   and date. Re-check any venue an earlier document asserted.
3. **Score candidates** on: domain match, same pipeline shape, a method the
   project can borrow, a limitation the project fills, venue tier, recency.
   The final pick must satisfy the hard constraints; strong papers that miss a
   constraint become highlighted comparisons instead of being dropped.
4. **Keep everything compared.** Group papers into method families. For each:
   one-line method, evaluation setup and headline numbers, and "what EviBound
   can use". Mark excluded papers as "not a presentation candidate" rather than
   deleting them.
5. **Close the loop to the project.** A final table maps each borrowable
   method to a concrete next step in the roadmap.

## Output

- A short recommendation message: the pick, why it is closest, three methods
  to borrow, differences to point out in the talk, and one or two backups.
- A methods-map page (HTML artifact or document) with a filter for "recent
  top venue only", a property comparison table, per-paper cards and the
  method-to-next-step table. Cite with links.

## Checks

- [ ] No pick or highlighted paper is on the exclusion list.
- [ ] Every venue and date was verified at the source.
- [ ] Numbers quoted from papers are attributed and short; no long quotations.
- [ ] Each "useful for us" line names a specific project file, metric or step.

## Related skills

`deep-research`, `artifact-design`, `docs`, `pptx` (for the talk itself).
