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
  - On the published page, verdicts go to the artifact's store, under each
    annotator's own record (see "Several annotators"), where Claude can read
    them.
  - In a local file, they stay in that browser; use **导出** to save them.

**The v3 corpus is frozen.** Its desk is a practice run. Do not overwrite
`reviews/v3/checklist.csv` with its export, and do not run `--signoff` for v3.

## Quick-start guide

**When it appears.** On every open, an eight-page guide comes up before the
desk. It takes one to two minutes and can be skipped with `Esc`. The 引导
button in the header reopens it.

**The pages:**

1. What is being reviewed and why, with the system diagram.
2. Devices, levels, presence and permission.
3. The six rules, with the legal-state grid and the jump rule.
4. Reading the sensors and the everyday phrases.
5. Tamper, replay and authorization-negative tasks.
6. What each question asks, with examples of failures.
7. How to read a card, and the fastest keys.
8. A warm-up of three questions.

**The warm-up.**

- **Rule question.** One question is generated from the rule table, so it is
  always correct and different each time.
- **Other questions.** The other two come from a pool on sensors, attacks and
  judgement.
- **Wrong answers.** A wrong answer shows the reason and a link back to the
  page that covers it.

**What is recorded.** On the published page, each annotator's last guide run
is written to their own record:

- pages seen;
- time taken;
- quiz score, by topic.

## Several annotators

**Storage.** On the published page every annotator writes only their own
subtree: `reviewers/<id>/runs/<run_key>/verdicts/<item>`, plus a profile
document `reviewers/<id>`.

| Path | Read | Write |
|---|---|---|
| `reviewers` | `admin` (owner and Editors read everyone) | `self` |
| `reviewers/{self}` | `interact` | `interact` |

Annotators therefore cannot read or overwrite each other's verdicts, and the
owner (or Claude, reading as the owner) can compare them.

**Sharing.**

- Inside the organization: share as Contributor.
- Outside the organization: annotators can only view a shared artifact, so
  they use the offline file and send back the exported JSON.

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
