# Review desk / 审核台

A single-page tool for the human corpus review: one item at a time, with a
Chinese translation, a state diagram, task-specific hints for every review
question and automatic checks. It replaces the all-cards-on-one-page
`reviews/v3/review.html` for future corpora, and it exports the same
`checklist.csv` that the sign-off scripts read.

## Build

```bash
python3 scripts/build_review_desk.py          # writes reviews/v3/review_desk.html (git-ignored)
```

**Outputs.**

- **The page.** It is self-contained and can be opened by double-clicking.
  Its only external request is Google Fonts, which falls back to system
  fonts offline.
- **`--artifact-out PATH`.** Also writes the body-only page that is published
  as a claude.ai artifact.
- **Where results go.**
  - On the published page, verdicts go to the artifact's shared store
    (`runs/<run_key>/verdicts`), where Claude can read them.
  - In a local file, they stay in that browser; use **导出** to save them.

**The v3 corpus is frozen.** Its desk is a practice run. Do not overwrite
`reviews/v3/checklist.csv` with its export, and do not run `--signoff` for v3.

## What is reviewed

| Kind | Items (v3) | Questions |
|---|---|---|
| Rules and conventions | R1–R6 and three reading conventions | wording clear; rule sensible; diagram correct; Chinese accurate |
| Camera captions | 39 distinct sentences | readable at a glance; matches its label; Chinese accurate |
| Tasks | 84 (77 REQUIRED, as in the v3 bundle) | the four checklist questions (q1–q4), confidence (q5), decision, comment |

## Where the hints come from

**Automatic checks are a second implementation.** The builder imports no
project code (review B-03). It re-implements from their written definitions:

- the rules;
- the shortest-plan search;
- the observation reader;
- the instruction parser.

A check that disagrees with the corpus therefore points at a real
inconsistency. On the frozen v3 corpus all checks agree.

**Translations come from the English words.** A phrase table parses each
English sentence. It never translates from the goal fields, so a wrong
instruction gets a faithful, and visibly wrong, translation. A sentence the
table does not know is a build error.

## Keys

| Key | Action |
|---|---|
| `A` | Approve: all questions yes, then the next unreviewed item |
| `F` / `R` | Needs fixing / reject; a one-line reason is required |
| `1`–`4` | Mark question 1–4 as no (press again for yes) |
| `H` `M` `L` | Confidence: high / medium / low |
| `C` | Write the comment; `Ctrl/⌘+Enter` saves and moves to the next item |
| `←` `→`, `U` | Previous / next item; next unreviewed item |
| `E`, `?` | Export; help |

**Systematic problems.** When one problem tag reaches three items, the desk
suggests stopping, so the generator can be fixed once instead of item by item
(`docs/review_guide_v2.md`).

## v4

The v4 generator should emit the Chinese text for every template string
itself. The builder then needs:

- a v4 adapter (new devices, multi-fact citations, guest windows);
- the v4 sampling rule (`docs/v4_preregistration_draft.md` §4.2: 100% of
  rules, pools, A3 and rule-boundary tasks, at least 30% of the other
  structures);
- `mode: "signoff"`.
