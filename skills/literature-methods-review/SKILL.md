---
name: literature-methods-review
description: Choose the most relevant recent paper for a course presentation, verify every venue/title/claim directly against primary sources, and build a mechanism-level related-work map connecting compared papers to concrete project next steps. Use when selecting a presentation paper, auditing citations before report submission, or positioning a research project against recent literature.
---

# Literature & Methods Review

Worked example in EviBound:
- Related-work audit & reference verification: `docs/related_work_2026-11.md` (Section 5 records primary-source re-checks for every cited paper)
- Presentation pick: *SimuHome: A Temporal- and Environment-Aware Benchmark for Smart Home LLM Agents* (Seo et al., ICLR 2026), mapped directly to EviBound-T v4 (`docs/v4_formal_model.md`, `docs/v4_preregistration_draft.md`).

## 1. Collect constraints first

- Read the repository's current state (research question, latest results, known limitations, next steps) — never rely on stale memory.
- Record hard constraints: venue tier, recency window, and the **exclusion list** (papers already presented by classmates or the author). Normalize titles before matching, since papers often circulate under short acronyms.

## 2. Search by mechanism & verify primary sources

- **Search across pipeline hops**, not just one keyword: domain/simulator, threat model (tampering/replay/TOCTOU), defense mechanism (provenance, commit-time freshness, runtime shielding), and evaluation (refusal feedback, side-effect metrics).
- **Verify every claim directly at the primary source** (proceedings page, arXiv abstract/PDF, or official repository):
  - Check exact title, author list, year, and venue tier — preprint titles and claims frequently change across versions (e.g., in EviBound we caught a title change on `arXiv:2609.29522` and corrected an inaccurate claim about *Environment Steering*, which *does* compare three feedback types on task/attack success, though not on unrequested side effects).
  - Never propagate unverified venue tags (such as "Oral") unless confirmed on the official proceedings/OpenReview record.

## 3. Map methods to concrete project actions

- Group compared papers into mechanism families. For each paper, record: one-line mechanism, evaluation setup + headline numbers, and a concrete **"what our project can borrow / where we differ"** note pointing to specific files, metrics, or experiments.
- Keep excluded papers in the methods map (marked as excluded from presentation) so comparative insight is never lost.
- Close the loop: for a presentation deck, pair the paper's key limitation directly with the project's latest experimental evidence (e.g., SimuHome's finding that timely feedback lifts scheduling recovery to 55–67% paired with EviBound Study 3's warning that open legal-write menus double unrequested changes).

## Verification checklist

- [ ] No selected or highlighted paper appears on the exclusion list.
- [ ] Every title, author list, venue, and date was checked directly against the PDF or official proceedings/arXiv page.
- [ ] Every quantitative claim attributed to a cited paper matches its actual table/figure (no paraphrased drift).
- [ ] Every "connection to our project" row names an actual up-to-date result or module in this repository.

## Related skills

`deep-research`, `evidence-bound-report-pipeline`, `pptx`.
