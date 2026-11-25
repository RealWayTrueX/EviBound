# Course release notes (draft, 2026-11-18; updated 2026-11-25 for v3.1) / 课程版本发布说明（草稿）

Status: draft for the corpus owner. Tagging, merging and publishing the trace
archive are release decisions and stay with the owner (`AGENTS.md`). Nothing
here changes a frozen file.

本文是给语料负责人的发布说明草稿。合并、打标签、是否公开轨迹压缩包都由负责人决定。

## What the release contains

| Deliverable of the research contract | Where |
|---|---|
| Report, eight pages with references and appendix (updated 2026-11-25 with a section on v3.1) | kept locally, not in the public repository |
| Five-minute demo and its script | [demo/](../demo/README.md), [demo_walkthrough.md](demo_walkthrough.md) |
| Versioned scenarios and prompts | `data/scenarios*/`, the frozen planner and recovery modules under `src/evibound/` |
| Raw traces | one archive with a hash manifest on the data disk ([reproduction.md](reproduction.md), section 5); the episode fingerprints of both confirmatory runs are in `artifacts/` |
| Analysis | `scripts/analyze.py`, `scripts/analyze_v3.py`, the result records in `artifacts/` |
| One-command reproducible subset | `bash scripts/reproduce.sh` |
| Safety statement, AI-assistance disclosure, licences | [SAFETY.md](../SAFETY.md), [LICENSE](../LICENSE), [LICENSE-DATA.md](../LICENSE-DATA.md) |

## Results in three lines

1. **Safety, supported.** Under fixed tampering and replay, EviBound (M) had
   an unsafe effect in 0 of 72 attacked episodes and the identical-rule guard
   B2 in 30 of 72: +36.4 points, 95% interval [+18.2, +59.1].
2. **Utility, not supported.** On clean tasks M reached the goal in 44 of 72
   episodes and the unguarded baseline B0 in 53: −13.6 points [−27.3, 0.0]
   against a margin of −5. The joint hypothesis is therefore not supported.
3. **Why.** The nine missing completions broke a device rule without a guard;
   the planner did not repair a blocked plan in its one retry. A preregistered
   extension (v3) reproduces the safety result and improves recovery; its
   utility conclusion depends on the criterion, and the original criterion is
   not met.

Every number above is in `artifacts/week8_main_results.json`.

Added on 2026-11-25: a second extension (v3.1), outside the contract's
hypothesis, varies only the message the guard sends after a refusal. Five of
its six preregistered claims are supported; a list of legal writes makes the
planner change things nobody asked for, and naming the broken rule or
reviewing the rejected plan does not ([v3_1_results.md](v3_1_results.md)).
Its corpus is machine-generated, and its human review follows the run.

## How to check the release

```bash
bash scripts/reproduce.sh                          # tests, corpus checkers, five freezes, scripted pipeline, v3.1 records
python3 scripts/build_report_numbers.py --check    # with a local copy of report/: the report's numbers match the records
bash scripts/reproduce.sh --traces DIR             # recompute the published numbers from the raw traces
```

On 2026-11-18: 128 tests pass, both corpus checkers pass,
`python3 scripts/verify_freezes.py` reports 4 of 4 `[ok]`. On 2026-11-25, with
v3.1: 203 tests pass, the three corpus checkers pass, the same four freezes
and the v3.1 freeze verify. Later the same day, with the tests for the
report's figures: 217 tests (15 of them need the local report and are skipped
without it).

## Known issues

- One secondary field of the frozen v2 record is wrong
  (`secondary_results.a3.clean.B0_authorization_violations` is 3; the traces
  show 0). The file is frozen and unchanged; see
  [reproduction.md](reproduction.md), section 7.1. No primary result is
  affected.
- The post hoc second review of the labels has no filed exports yet, so the
  report gives no agreement statistic
  ([peer_review_protocol.md](peer_review_protocol.md)).
- The limits of the study are listed in section 9 of the report and in
  `SAFETY.md`.

## Steps for the owner

These commands change the public repository. They are listed for the owner
and have not been run.

```bash
# 1. merge pull request #4 into main (or use the button on GitHub)
gh pr merge 4 --merge

# 2. tag the merged commit; the report can then cite the tag
git checkout main && git pull
git tag -a v1.0-course -m "EviBound: course report, frozen v1-v3 studies, reproduction package"
git push origin v1.0-course

# 3. optional: publish the trace archive with the release (owner's decision)
#    first check it: sha256sum evibound_raw_traces_20261110.tar.gz
#    expected 5086166a19ff16838d72cc28282b187f3c9966aa5bba9dd98cccd536042027fa
gh release create v1.0-course --title "EviBound course release" --notes-file docs/release_notes_course.md \
    evibound_raw_traces_20261110.tar.gz
```

Before step 2, read the report: its last paragraph states that the text was
drafted with AI assistance and checked by the author.
