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

**The v3.1 corpus is checked after the run** (owner's decision of 2026-11-24).
`python3 scripts/build_review_desk.py --corpus v3_1` builds its desk: 420 task
cards, of which 84 holdout cards are required (one per stratum and
modality-language cell; four core strata and three attack-battery strata). Each card adds a line and an automatic check for what
the rules and the scope allow at most. There is no sign-off script for v3.1:
the export goes into the sensitivity analysis described in
`docs/v3_1_preregistration.md`. The whole-chain attack cards belong to the v3
desk only.

## Whole-chain attack cards (exploratory)

With `node` installed, the build also runs `demo/attacks/export_chain_cases.js`
and adds two card kinds for the 21 attack forms of
[`docs/chain_attack_surface.md`](../docs/chain_attack_surface.md), one or more
on every hop H0–H11 of the sensor → agent → device chain:

| Kind | Cards | Required | What the annotator checks |
|---|---:|---:|---|
| 攻击形式 / attack form | 21 | all | the hop and its trust status, the real-world counterpart, a clear before → after, the Chinese |
| 攻击 × 任务 / attack x task | 1,444 | 160 | the before → after in this task, the agent's reaction, and the verdict under B0, B2 and M_full with and without the attack |

- **Chain diagram.** Every attack card, every attack x task card and every v3
  task card (as a fold-out, hop H4) draws the whole chain, with the trusted
  base shaded, the attacked hop framed in red and the altered data path drawn
  in red. The guide gained a page on it (nine pages).
- **Required sample.** Per attack, one card for every distinct outcome
  pattern, then spread over sensor kinds and task families, up to eight
  (`CHAIN_SAMPLE_PER_ATTACK`); the remaining 1,284 cards are optional.
- **Scripted agent.** "careful" (follows what it reads, keeps every rule), so
  any harm comes from the attack; "hasty" for forged feedback and the two
  scope attacks, which only bite an agent that makes mistakes. Text
  injections are modelled at their worst case: the injection succeeds and
  the model obeys.
- **Saved verdicts are kept.** The run key and the hashes of the v3 cards do
  not change; `--no-chain` builds the page without these cards.

**Time (planning estimate).** About 1–2 minutes per attack-form card, 45–90
seconds per sampled attack x task card (the first cards of each attack are
slower), and 30–60 seconds per remaining card once an attack is familiar.
Required: about 3–5 hours of attack cards on top of the v3 cards. All 1,444
attack x task cards: about 12–24 hours.

## Quick-start guide

**When it appears.** On every open, a nine-page guide comes up before the
desk. It takes one to two minutes and can be skipped with `Esc`. The 引导
button in the header reopens it.

**The pages:**

1. What is being reviewed and why, with the system diagram.
2. Devices, levels, presence and permission.
3. The six rules, with the legal-state grid and the jump rule.
4. Reading the sensors and the everyday phrases.
5. Tamper, replay and authorization-negative tasks.
6. The whole chain: every hop can be attacked; the trusted base.
7. What each question asks, with examples of failures.
8. How to read a card, and the fastest keys.
9. A warm-up of three questions.

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
