---
name: preregistered-agent-security-experiment
description: Design, run and report an LLM-agent attack/defense experiment (runtime guard, attacked observations, safety and utility metrics) so the results are trustworthy - preregistration and hash freeze, independent oracle, paired conditions, honest denominators, human-signed labels, and bootstrap decisions. Use when planning a new study round, adding conditions or corpora, or writing up results for this kind of project.
---

# Preregistered agent-security experiment

Worked example: the EviBound repository (`AGENTS.md`,
`docs/week8_preregistration.md`, `docs/week11_v3_preregistration.md`,
`scripts/freeze_v3_prereg.py`, `src/evibound/oracle*.py`,
`scripts/analyze_v3.py`, `artifacts/week11_v3_holdout_results.json`).

## 1. Define the claim before the code

- Write one research question with a **joint** criterion: safety under attack
  *and* utility on normal tasks. A guard that blocks everything must fail.
- Name every condition as a delta from a baseline (B0 no guard, B2 rules only,
  M = B2 + evidence checks, plus ablations such as "M without freshness").
- Fix the threat model in scope and out of scope, and map each simulated
  attack to how it happens in a real system (see
  `docs/threat_model_real_world.md`). Readers will ask.

## 2. Build the measurement so it cannot flatter you

- **Independent oracle.** The scorer imports no guard code and re-derives
  safety from executed state and the true hidden state. Rejected proposals are
  never "unsafe"; an earlier unsafe transition is never erased by a safe end
  state.
- **Paired design.** All conditions share the model's first proposal for the
  same task, variant and seed; only the guard and recovery differ. Equal
  recovery budgets for every condition.
- **Honest denominators.** Parse failures, empty plans, refusals and
  format errors stay in every rate.
- **Clustered statistics.** Count independent physical structures, not
  episodes or paraphrases; bootstrap over tasks with a fixed seed; state the
  margin (e.g. non-inferiority -5 pp) and the verdict words
  (supported / inconclusive / unsupported) in advance.
- **False-block metric.** Measure how often the guard refuses a write that was
  legal with authentic fresh evidence. It must be reported even when zero.

## 3. Corpus and labels

- Splits: dev (debug freely) -> pilot (rehearsal) -> test/holdout (touched
  once). New holdout structures must not appear in earlier splits.
- Generate tasks programmatically, check them with a machine checker, then
  have the human owner sign every card. Cards must be readable by a
  non-author: plain level names, one decision per card, the model-facing text
  shown verbatim. Ambiguous wording found in review is a bug to fix before the
  freeze, not a footnote.
- Tag every task with human-readable labels (modality, language level, attack,
  task type, rules stressed) so results can be broken down later.

## 4. Freeze, then run

- Hash protocol docs, corpus, code and analysis script into a freeze record
  signed by the human owner; the runner refuses to start the holdout if any
  hash differs. Amendments before the freeze are logged with reasons; after
  the freeze nothing changes.
- Run long jobs in tmux on a watcher that waits for sustained free GPU memory
  rather than a Claude session that polls. Keep raw traces off the repository.
- Re-score every episode with the oracle afterwards and require zero
  disagreements.

## 5. Report

- Machine-readable results first, prose second; every number in prose is
  regenerated from the results file.
- Lead with the preregistered decisions table, then breakdowns by label, then
  the failure taxonomy that motivates the next round.
- Write limits as concretely as findings (attack types not covered, synthetic
  rules, record matching standing in for cryptographic authentication).

## Common mistakes seen in this project

- Scene names that contradicted the target levels confused reviewers; use
  neutral names.
- A utility gap blamed on the guard was really failed recovery after a
  correct refusal; inspect trajectories before changing the guard.
- Raw goal completion rewarded the unguarded baseline for writing forbidden
  devices; report a rule-compliant completion metric alongside it.

## Related skills

`research`, `tdd`, `code-review`, `diagnosing-bugs`, `handoff`
(mattpocock/skills); `deep-research` for the related-work check; `dataviz` for
figures.
