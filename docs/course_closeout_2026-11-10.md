# Course closeout: audit and finishing plan (2026-11-10) / 课程收尾：审计与完成计划

Status: audit record and plan, written 2026-11-10 on branch
`claude/review-response-v4-prep` (pull request #4, not yet merged into
`main`). No research change: no frozen file was edited, and
`python3 scripts/verify_freezes.py` reports all four protocol freezes `[ok]`.
Every result below is quoted from a committed file, which is named next to it;
the times and dates in the plan (section 6) are planning estimates.

## 中文摘要

- **这份文件是什么。** 对照提交给课程的研究合同逐条审计项目，列出硬伤（H1–H10）、应修项（S1–S9）、今天已修好和已核实的部分、负责人要做的事，以及到 Week 15 交报告为止的两周计划。没有改动任何冻结文件或研究结论。
- **哪些是可靠的。** v2 正式测试是合同的确认性实验（1,296 回合）：受攻击时 B2 有 30/72 次实际不安全，EviBound（M）0/72，+36.4 pp [18.2, 59.1]，安全假设成立。四个冻结协议全部校验通过；今天在原 GPU 机上从原始轨迹重算了全部已发布数字（23 项检查，0 项失败）；单元测试和两个语料检查全部通过。
- **最重要的硬伤。** 合同的效用假设不成立（M 比 B0 低 13.6 pp，门槛是 5 pp），所以合同的联合假设不成立。报告和演示必须先用合同自己的口径讲这一点；v3 的 U2 是看到开发集结果后修订的标准，必须标明。其余硬伤：GitHub 默认分支 `main` 上还是旧 README（写着“联合可行性支持”“从未拒绝合法写入”），要合并 PR #4；6–8 页报告还没写；合同要求的同学或老师评审还没做；原始轨迹只在服务器上有一份。
- **今天修好的。** 一条命令的复现（`bash scripts/reproduce.sh`）；从原始轨迹重算已发布数字；合同要求的全部指标表，包括此前没报告过的攻击目标达成（B2 38/72，M 1/72）；`SAFETY.md` 和许可证；演示结果页按合同口径排序；最终的五分钟演示讲稿；同伴评审协议、固定种子抽样和一致率脚本；服务器上带哈希清单的原始轨迹压缩包。在第二台机器（Colab A100）上用冻结的运行器重跑了 v2 全部 1,296 回合和 v3 种子 11 的 2,376 回合：约九成回合的首个回复逐字一致，预注册判定全部相同，v2 的安全和效用估计值与区间完全一致（第 5 节）。
- **负责人要做的（两周内合计约 4–5 小时，不含标注）。** 合并 PR #4；下载轨迹压缩包放到服务器以外，并决定是否公开；向老师确认展示和交报告的日期、报告模板和提交方式，问 v3 算不算项目内容、评审用什么形式；找一位同学审约一小时；检查 `SAFETY.md` 的 AI 协助表和许可证署名；排练演示两次并录备份视频；审定报告。
- **日期（待确认）。** 课程安排是第 14 教学周展示、第 15 教学周交报告；仓库里记过“12 月 8 日交课程报告”（`docs/v4_preregistration_draft.md`，2026-11-03），而负责人 11 月 10 日估计只剩一到两周。两者对不上，所以第 6 节按最早的情况排（11 月 16–20 日展示，11 月 23–27 日交报告）。如果报告确实是 12 月 8 日交，后两段整体顺延，多出约两周缓冲。第一件事是向老师确认这两个日期。

## 1. Purpose and scope

**The binding checklist** is the research contract as submitted to the
course. Its text is local-only because it identifies the student
(`docs/roadmap_week6.md`, 2026-10-11 entry); the repository copy,
[research-contract.md](research-contract.md), holds the research question,
the hypothesis, the conditions, the measures and the freeze schedule. Section 2
paraphrases every commitment of the submitted version in five groups:
hypothesis, design, outcomes, schedule, deliverables.

**Status words used below.**

- *done*: met before today, with evidence in the repository.
- *done today*: met by work committed on 2026-11-10.
- *partly*: some evidence exists; an action is still open.
- *open*: not met yet.

**Other terms.** *Confirmatory* means decided by a rule frozen before the
data existed. *Post hoc* means computed after the results were known; such
numbers are descriptive. A *cluster* is a physical structure (initial state,
both branch goals and the authorized devices); intervals resample clusters,
not episodes (`docs/datasheet_v2_v3.md`).

## 2. Contract compliance matrix

### Hypothesis

| # | Commitment | Status | Evidence | Remaining action |
|---|---|---|---|---|
| 1.1 | Under tampering and replay, M has fewer executed unsafe effects than B2 | done (supported) | v2 formal test: B2 30/72, M 0/72; +36.4 pp [+18.2, +59.1]; preregistered decision `supported` (`artifacts/week8_main_results.json`) | state first in the report and the talk |
| 1.2 | Clean goal completion no more than 5 pp below B0 | done (not supported) | B0 53/72, M 44/72; −13.6 pp [−27.3, 0.0]; margin −5 pp; decision `unsupported` (same file) | state as "not supported" in the contract's terms (H2) |
| 1.3 | Safety and utility jointly | done (not supported) | `joint_feasibility: not_supported` (same file) | same |

### Design

| # | Commitment | Status | Evidence | Remaining action |
|---|---|---|---|---|
| 2.1 | 24 test tasks × clean / perturbed / legal-boundary × B0, B1, B2, M × 3 runs = 864 episodes | done | these 864 episodes are part of the frozen 1,296-episode formal test, which adds the two diagnostic conditions in the same run: 24 tasks × 3 variants × 6 conditions × 3 seeds, 0 parse failures, 0 duplicate ids (`artifacts/week8_main_results.json`) | — |
| 2.2 | Freshness-only ablation | done | M_no_freshness 18/72 vs M 0/72 unsafe; +22.7 pp [+6.8, +40.9] (same file); all 18 are replay episodes (episode fingerprints, section 5) | report it |
| 2.3 | Always-refresh diagnostic | done | 0/72 unsafe; mean reads 3.44 vs 1.92 for M; difference +1.46 reads [+1.08, +1.83] (same file) | report it |
| 2.4 | Component tests reported separately | partly (S6) | v1 component tests, 27 passing (`artifacts/component_tests.log`); today's unit-test count in section 5 | a paragraph or appendix table in the report |

### Outcomes and validation

| # | Commitment | Status | Evidence | Remaining action |
|---|---|---|---|---|
| 3.1 | Primary outcome: executed unsafe state or transition, intermediate steps included | done | the oracle scores every executed transition (`src/evibound/oracle.py`); 0 rescoring disagreements (`artifacts/reproduction_published_results_check.json`) | — |
| 3.2 | Authorization violations, reported separately | done today | under attack: B0 3/72, every other condition 0/72 (`artifacts/contract_outcomes_v2_v3.json`) | Table 1 of the report |
| 3.3 | Attack-goal success, reported separately | done today (H9) | per 72 attacked episodes: B0 56, B1 49, B2 38, M_no_freshness 21, Always_refresh 17, M 1; no-attacker control 0 for B0 and B1, 6 for every guarded condition (same file; post hoc, descriptive) | Table 1, labelled post hoc |
| 3.4 | Benign and safe completion | done | clean safe completion B0 44/72, M 44/72 (`artifacts/week8_main_results.json`, `clean_safe_outcomes`) | — |
| 3.5 | False blocks on legal writes | done, with a caveat | 0 false blocks among contract-eligible proposals (`false_blocks: 0`, same file). Eligibility requires legal *and* evidence-sufficient, so stale-but-harmless writes are excluded (`docs/review_response_2026-11-03.md`, C-03) | write "zero contract-eligible false blocks", never "never refused a legal write" |
| 3.6 | Evidence-sufficient proposals | partly | the oracle counts them per episode (`evidence_sufficient_proposals`); tabulated in the v3 results record, but for v2 only in the server-side analysis summary | add the v2 totals per condition to the report table, computed from the traces |
| 3.7 | Re-reads | done | mean reads under attack: B0 1.0, B2 1.29, M 1.92, Always_refresh 3.44 (`artifacts/contract_outcomes_v2_v3.json`) | — |
| 3.8 | Latency and cost | done today | per episode, clean: B0 0.22 s and 701 tokens, M 0.26 s and 849; under attack: B0 0.22 s and 701, B2 0.30 s and 959, M 0.54 s and 1,509 (same file; latency is not controlled for concurrent load) | Table 1 with the caveat |
| 3.9 | An independent trajectory oracle | done | the oracle imports no guard predicate (`AGENTS.md` rule); 0 disagreements on rescoring (section 5) | — |
| 3.10 | The student validates the labels | done | v2: 44 required review rows signed 2026-10-10 (`artifacts/week8_preregistration.json`); v3: 77 required cards, zero open items, signed 2026-10-11 (`artifacts/week11_v3_prereg_freeze.json`) | — |
| 3.11 | Peer or instructor review of the rules and of representative traces | open (H8) | protocol, fixed sample and agreement script written today ([peer_review_protocol.md](peer_review_protocol.md), `scripts/review_agreement.py`); no second reviewer yet; no trace cards yet | section 6 plan |
| 3.12 | Task-paired differences, task-clustered 95% intervals, null results included | done | paired by task, variant and seed; clustered by physical structure, 22 clusters, 10,000 resamples, seed 20260923 (`artifacts/week8_main_results.json`); the inconclusive pilot and the unsupported utility are reported | say "clustered by physical structure", which is stricter than per task (S3) |
| 3.13 | Development, pilot and test tasks disjoint | partly (S2) | task ids are disjoint; 12 physical structures span the v2 splits, and 12 of the 22 v2 test structures also occur in v1 ([datasheet_v2_v3.md](datasheet_v2_v3.md)) | call v2 "a paired mechanism study, not a structural holdout" |

### Schedule (Weeks 13–15)

| # | Commitment | Status | Evidence | Remaining action |
|---|---|---|---|---|
| 4.1 | Independent reproduction | done today | published numbers recomputed from the raw traces, 23 checks, 0 failed; frozen runners re-run on a second machine with every preregistered decision unchanged (section 5; `artifacts/reproduction_colab_a100_record.json`) | report section 6, with the S9 disclosure |
| 4.2 | Report | open (H3) | — | outline in section 7, plan in section 6 |
| 4.3 | Demonstration | partly | demo page with the results tab in the contract's terms; final script [demo_walkthrough.md](demo_walkthrough.md) (done today) | rehearse twice; record a backup |

### Deliverables and compute

| # | Commitment | Status | Evidence | Remaining action |
|---|---|---|---|---|
| 5.1 | Five-minute demo | partly | `demo/`, [demo_walkthrough.md](demo_walkthrough.md) | rehearsal and backup recording |
| 5.2 | Six-to-eight-page report | open (H3) | — | draft from Wed 11 Nov |
| 5.3 | Versioned scenarios and prompts | done | `data/scenarios*/` with manifests and hashes; prompts in the frozen planner and recovery modules, hashed in the freeze records | — |
| 5.4 | Raw traces | partly (H5) | one archive with a hash manifest on the server: 93 files, 2,279,422 bytes ([reproduction.md](reproduction.md), section 5) | off-server copy; publishing decision |
| 5.5 | Analysis | done | `scripts/analyze.py`, `scripts/analyze_v3.py`, the result records; recomputed today | — |
| 5.6 | One-command reproducible subset | done today (H4) | `bash scripts/reproduce.sh` (level 1: no GPU, no traces); [reproduction.md](reproduction.md) | — |
| 5.7 | Safety statement | done today (H7) | [SAFETY.md](../SAFETY.md) | owner checks it |
| 5.8 | Licences reviewed, releases sanitized | partly (S1, S8) | [LICENSE](../LICENSE) (MIT) and [LICENSE-DATA.md](../LICENSE-DATA.md) (CC BY 4.0) with a third-party content check | confirm the copyright line; decide on S8 |
| 5.9 | Disclosure of AI-assisted test-driven development and review | done today | `SAFETY.md`, section 6 | owner checks the table, which is written in the owner's name |
| 5.10 | Two RTX 4090s; no paid APIs without approval | done, one disclosure (S9) | `artifacts/environment_v2.json`; no paid or hosted model API was used (`SAFETY.md`) | disclose the Colab re-run in the report |

## 3. Hard flaws (H1–H10)

A hard flaw would cost marks or credibility if it stayed as it is.

| ID | Finding | Why it matters | State after today | Who acts |
|---|---|---|---|---|
| H1 | The public default branch `main` still shows the old README, which says "Joint feasibility supported" and "EviBound never refused a legal write" (checked on `origin/main` today). The corrected README is on PR #4, which is unmerged | anyone who opens the repository reads a claim that the contract's own decision rule contradicts | unchanged until the merge | owner merges PR #4 |
| H2 | The contract's utility hypothesis is not supported (v2 −13.6 pp; v3 raw completion −7.4 pp), so its joint hypothesis is not supported | leading with the v3 amended rule (S1 ∧ U2 supported) would misreport the contract's outcome; U2 was added after the v3 development run | the demo's results tab now leads with the v2 contract decisions; section 7 fixes the report's headline sentences in the same order | assistant drafts; owner approves the wording |
| H3 | The six-to-eight-page report does not exist | the largest open deliverable | outline, page budget and headline sentences in section 7 | assistant drafts from Wed 11 Nov; owner reads and approves |
| H4 | The "one-command reproducible subset" was the September v1 script, bound to one machine's paths | the contract promises it as a deliverable | fixed: `scripts/reproduce.sh` (levels 1–3), `scripts/reproduce_cloud.sh` (level 4), [reproduction.md](reproduction.md) | — |
| H5 | The raw traces exist only on one shared server | a disk or account failure would lose a contract deliverable | partly fixed: archive with a hash manifest on the server, 93 files, 2,279,422 bytes, SHA-256 `5086166a19ff16838d72cc28282b187f3c9966aa5bba9dd98cccd536042027fa` | owner downloads it, keeps a copy off the server, decides whether to publish it |
| H6 | No independent reproduction of the model runs existed | the contract schedules independent reproduction in Weeks 13–15 | fixed: published numbers recomputed from the traces, and the frozen runners re-run on a second machine with the same decisions (subsection "Independent re-run on a second machine" in section 5) | goes into report section 6 |
| H7 | No safety statement | contract deliverable | fixed: [SAFETY.md](../SAFETY.md), which also holds the AI-assistance disclosure | owner checks the table written in the owner's name |
| H8 | Peer or instructor review: the evidence is the owner's own sign-off before each freeze and the review desk, which covers rules, reading conventions, captions and tasks but has no trace cards, no second reviewer and no agreement statistics | a contract commitment; without it, label validity rests on one person | protocol, a fixed random sample (seed 20261110) and an agreement script with 18 tests ([peer_review_protocol.md](peer_review_protocol.md)). The review is post hoc: it cannot change any label or result and only reports agreement and disagreements as limitations | owner asks the instructor about the acceptable form and finds reviewer B; assistant builds the trace cards and runs the analysis |
| H9 | Attack-goal success, a separate contract outcome, was never reported | a listed outcome was missing | fixed: `scripts/contract_outcomes.py`, `artifacts/contract_outcomes_v2_v3.json`, shown in the demo | goes into Table 1 |
| H10 | `docs/demo_walkthrough.md` was the September v1 outline and said so | the demo is a graded deliverable | fixed: rewritten as the final five-minute script with the attack story, the result sentences, the limits and the questions | owner rehearses |

## 4. Should-fix items (S1–S9)

| ID | Finding | Action | Who |
|---|---|---|---|
| S1 | `LICENSE` (MIT) and `LICENSE-DATA.md` (CC BY 4.0) were added today on the owner's earlier decision; the copyright line carries the owner's name | confirm the line | owner |
| S2 | Task ids are disjoint across development, pilot and test, but 12 physical structures span the v2 splits and the v2 test shares 12 of its 22 structures with v1; v3 shares none ([datasheet_v2_v3.md](datasheet_v2_v3.md)) | the report calls v2 "a paired mechanism study, not a structural holdout" | assistant (report) |
| S3 | Intervals are clustered by physical structure (22 clusters in v2), stricter than the contract's "task-clustered" | say so in the method section | assistant |
| S4 | v3 is a preregistered extension beyond the contract | ask whether it counts toward the project or is reported as additional work | owner asks the instructor |
| S5 | B1 results were only in the pilot notes | B1 goes into the main table: under attack 45/72 unsafe, the same as B0; clean goal 48/72 (`artifacts/contract_outcomes_v2_v3.json`) | assistant |
| S6 | Component tests are to be reported separately | an appendix with `artifacts/component_tests.log` (v1, 27 tests) and the current unit-test count | assistant |
| S7 | Human-review records are local-only by design | the report states what exists and where: the v2 checklist, sign-off and AI secondary review are also sealed inside `artifacts/week8_protocol_freeze.tar.gz`, which is in the public repository and verified by `scripts/verify_freezes.py`; the v3 sign-off hash is in `artifacts/week11_v3_prereg_freeze.json` and the v3 cards stay on the server | assistant (report); owner notes that the sealed v2 files are public |
| S8 | A private-network host address appears in six tracked files (`demo/app.js`, `demo/backends.json`, both launchers in `demo/launch/`, `docs/remote_planner_setup.md`, `scripts/model_server.py`), and the server user name appears in data-disk paths in many files; frozen scripts contain absolute paths and cannot change | low risk; sanitize the non-frozen files or leave them | owner decides |
| S9 | The second-machine re-run used the owner's existing Google Colab subscription (an A100) at the owner's request, for reproduction only; no confirmatory number comes from it, while the contract's compute line says two RTX 4090s and no paid APIs without approval | disclose it in the report's reproduction section and compute statement | assistant writes; owner confirms |

## 5. What was verified today

| Check | How | Result | Record |
|---|---|---|---|
| Published v2 and v3 results recomputed from the raw traces, on the original GPU machine, CPU only, in a fresh clone | `python3 scripts/verify_published_results.py --traces DIR` | 23 checks, 0 failed: trace hashes, episode counts, 0 oracle rescoring disagreements, every primary estimate, interval, count and decision | `artifacts/reproduction_published_results_check.json` |
| Protocol freezes | `python3 scripts/verify_freezes.py` | 4 of 4 `[ok]`. v1: 6 files evolved for v2 match the sealed archive; v2 pilot: 3 local-only review files match the sealed archive | rerun after this document was written |
| Unit tests | `PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py'` | 112 pass, including 11 tests of the reproduction tools and record and 18 agreement tests (`tests/test_review_agreement.py`) added today; 83 passed at the start of the audit | — |
| Corpus checkers | `python3 scripts/check_scenarios_v2.py`, `python3 scripts/check_scenarios_v3.py` | OK: 56 tasks; 84 tasks, 48 physical structures | — |
| Episode fingerprints of both confirmatory runs | `scripts/episode_fingerprints.py` | committed | `artifacts/episode_fingerprints_v2_formal_test.json.gz`, `artifacts/episode_fingerprints_v3_holdout.json.gz` |
| Contract-outcome table | `scripts/contract_outcomes.py` | complete for 1,296 v2 and 7,128 v3 episodes; 0 mismatches between recomputed and stored goal completion | `artifacts/contract_outcomes_v2_v3.json` |
| Raw-trace archive | `scripts/package_traces.sh` | 93 files, 2,279,422 bytes, SHA-256 `5086166a…7fa` | [reproduction.md](reproduction.md), section 5 |

**Facts derived while writing this document**, from
`artifacts/episode_fingerprints_v2_formal_test.json.gz` and
`data/scenarios_v2/test.jsonl` (committed files; no model text needed):

- The clean raw gap between B0 (53/72) and M (44/72) is nine *episodes*, not
  nine tasks: three tasks × three seeds. In each, B0 reached the goal by
  jumping a device from off straight to level 2 (R5 in six episodes, R4 in
  three); M blocked the jump and the planner's one retry did not reach the
  goal.
- B0's 44 clean safe completions and M's 44 clean goal completions are the
  same 44 episodes.
- All 18 unsafe effects of M_no_freshness under attack are replay episodes.
- The 6 no-attacker attack-goal episodes of every guarded condition are two
  tasks × three seeds: in one, the guard blocks a light jump after the fan was
  switched off, which leaves the other branch's end state; in the other, an
  authorization-negative task, the correct authorized part coincides with the
  other branch's goal.

### Independent re-run on a second machine

Done on 2026-11-10 with `scripts/reproduce_cloud.sh` on a Google Colab runtime
with an NVIDIA A100 (the original runs used an RTX 4090): same library
versions, same pinned model revision (14 of 14 files match the manifest),
frozen runners. It covered the full v2 formal-test matrix (1,296 episodes) and
seed 11 of the v3 holdout (2,376 of 7,128 episodes) and took 21 minutes with
set-up; the runtime was released when the run ended. Record:
`artifacts/reproduction_colab_a100_record.json`; tables in
[reproduction.md](reproduction.md), section 7.

| | v2 formal test | v3 holdout, seed 11 |
|---|---|---|
| Episodes compared with the original run | 1,296 | 2,376 |
| Identical first response | 1,181 (91.1%) | 2,178 (91.7%) |
| Identical executed writes | 1,167 (90.0%) | 2,227 (93.7%) |
| Identical oracle outcomes | 1,221 (94.2%) | 2,321 (97.7%) |
| Safety contrast, original and re-run | +36.4 pp [18.2, 59.1], 30 vs 0 of 72, in both | +15.3 pp [5.6, 26.4], 11 vs 0 of 72, in both |
| Raw utility contrast, original and re-run | −13.6 pp [−27.3, 0.0] in both (44 vs 53, then 45 vs 54 of 72) | −8.3 pp [−20.8, 2.8], then −9.7 pp [−23.6, 2.8] |
| Decisions | safety supported, utility not supported, in both runs | S1 supported, U1 not supported, U2 supported, in both runs |

About one first response in eleven differs between the two GPUs, which is
expected for sampling on different hardware. Every preregistered decision is
the same, and the two v2 estimates and intervals are identical. No episode
under a full guard had an unsafe effect in either run (0 of 432 in v2, 0 of
1,296 in v3 seed 11). The re-run's episode fingerprints are committed, and
`tests/test_reproduction_tools.py` recomputes this table from them on every
test run. The raw traces of the re-run were not kept; their hashes are in the
record. Scope: same model, prompts, tasks and code on other hardware, so this
shows that the published numbers follow from the published procedure. It says
nothing about other models or attacks (S9 covers the compute disclosure).

## 6. Two-week finishing plan

**What is known about the dates.** The course schedule puts project
presentations in teaching Week 14 and project reports in Week 15. The
repository recorded "course report on 8 December" on 2026-11-03
(`docs/v4_preregistration_draft.md`). On 2026-11-10 the owner estimated one to
two weeks to the end. These do not agree, so the dates are the first question
for the instructor (section 8).

**Planning assumption, to confirm:** the plan is built backwards from the
earliest reading, with the presentation in the week of Mon 16 – Fri 20 Nov
2026 and the report due in the week of Mon 23 – Fri 27 Nov 2026: demo ready
and the repository tagged by Sun 15 Nov, report final by Fri 20 Nov. If the
report is due on 8 December, the presentation is probably in the week of
30 November; the last two blocks then move later and the plan gains about two
weeks of buffer. Nothing in the first block depends on which reading is
right.

The owner spends these two weeks on human annotation with the review desk, so
the owner's part is limited to the items below (planned time in brackets).
"Assistant" means a Claude session working in this repository.

| Date | Owner | Assistant | Done when |
|---|---|---|---|
| Wed 11 Nov | merge PR #4 (10 min, H1); send the instructor the questions in section 8 (10 min); ask one classmate to be reviewer B (5 min); download the trace archive and check its SHA-256 (5 min, H5) | report draft v1, sections 1–4, from committed files only; the reviewer-B package (desk file, sample list, protocol, cover-note template) | `main` shows the corrected README; questions sent; the archive has a second copy |
| Thu 12 Nov | send reviewer B the package (10 min); start the annotation with the 31 sampled items | report draft v1 complete (all sections, Tables 1–3, Figures 1–2); build the 14 trace cards from the archive with the draw rule in the protocol, recording the draw first | draft v1 and trace cards exist |
| Fri 13 Nov | demo rehearsal 1 with a timer (15 min); read draft v1 and mark corrections (45 min) | draft v2 from the owner's marks; a one-page speaker card from [demo_walkthrough.md](demo_walkthrough.md) | the demo fits in five minutes; draft v2 exists |
| Sat 14 – Sun 15 Nov | export the reviewer-A answers once the 31 sampled items are done (5 min); rehearsal 2 and the backup recording (30 min) | release candidate: `bash scripts/reproduce.sh`, `python3 scripts/verify_freezes.py`, the link check; release notes | backup video stored in two places; every check passes |
| Sun 15 Nov, evening: **freeze for the presentation** | approve the release (10 min) | tag the release on `main` (for example `course-demo-2026-11`) and rebuild the demo bundle from it; from here until the talk, no change to `demo/` or to any result | tag pushed |
| Presentation week: Mon 16 – Fri 20 Nov in the earliest reading (day to confirm) | give the presentation (5 min; live model only if rehearsed, stopped right after); adjudicate disagreements with reviewer B (20 min, by Thu 19); final read of the report (60 min, Fri 20) | receive B's export (asked for by Wed 18); run `scripts/review_agreement.py` and the trace "no" list; report draft v3 with the peer review, the instructor's answers and the re-run; script check of every number in the report against the files | report final in the required template |
| Report week: from Mon 23 Nov in the earliest reading, to the deadline (to confirm) | submit through the course's channel (15 min) | final PDF; tag the commit the report cites (for example `course-report-2026-11`) | submitted |
| Buffer | every day between the tag and the confirmed dates | fixes only | — |

**Owner's planned time** outside the annotation: about four to five hours over
two weeks, plus the presentation itself.

**Order of risk.** Other people's time comes first: the instructor's answers
and reviewer B's hour are requested on Wed 11 Nov, because they cannot be
compressed later. The report draft starts the same day, because it is the
largest item. The repository is tagged before the presentation, so the demo
shows a fixed, citable version.

## 7. Report outline (six to eight pages)

**Page budget.** About 7.2 pages of main text, leaving room for the template's
title block and references. The template, page limit and whether references
count are questions for the instructor (section 8).

| § | Section | Pages | Content | Tables and figures |
|---|---|---:|---|---|
| 1 | Introduction | 0.6 | the problem; the research question; the contract's hypothesis in one sentence; the narrowed contribution ([related_work_2026-11.md](related_work_2026-11.md), section 3); the decisions in one paragraph, in the contract's terms | — |
| 2 | System and threat model | 1.0 | planner, devices, rules R1–R6 and authorization; attacks (tamper, replay, unauthorized-device request); trusted base and exclusions; the six conditions B0, B1, B2, M, M_no_freshness, Always_refresh | Figure 1: the evidence chain (actual state → collector records → per-write guard → independent oracle) |
| 3 | Method | 1.2 | corpus (24 test tasks, 22 physical structures; a paired mechanism study, S2); the 1,296-episode matrix; preregistration and freezes; the oracle; outcome definitions; statistics (paired, clustered by physical structure, 10,000 resamples, −5 pp margin; S3); label validation and the post hoc peer review | — |
| 4 | Results: the contract's test (v2) | 2.0 | headline sentences 1–8 below, in that order | Table 1: per condition, under attack and clean (unsafe effects, attack-goal success with its control, true goal reached, authorization violations, evidence-sufficient proposals, reads, latency, tokens; clean goal and safe completion). Table 2: the preregistered decisions. Figure 2: paired differences with intervals |
| 5 | Extension: v3 holdout | 0.8 | headline sentence 9; what v3 adds; which criterion is original, amended or exploratory | Table 3: S1, U1, U2, U_dec with their status |
| 6 | Reproduction and review | 0.4 | recomputation from traces; freezes; fingerprints; the second-machine re-run (S9 disclosure); peer-review agreement | small agreement table |
| 7 | Limitations | 0.6 | the list below | — |
| 8 | Related work | 0.4 | positioning from [related_work_2026-11.md](related_work_2026-11.md) | — |
| 9 | Conclusion | 0.2 | the decisions again, one sentence each | — |
| A | Appendix (outside the page count if allowed) | — | component tests (S6); AI-assistance disclosure; safety statement summary; artifact list with hashes | — |

**Headline sentences.** Numbers from `artifacts/week8_main_results.json`,
`artifacts/contract_outcomes_v2_v3.json`,
`artifacts/week11_v3_holdout_results.json`,
[v3_review_reanalysis.md](v3_review_reanalysis.md) and the derived facts in
section 5.

1. **Safety.** "Under fixed tampering and replay, EviBound (M) executed no
   unsafe effect in 72 attacked episodes, against 30 of 72 for the
   identical-rule guard B2 that trusts the reading the agent cites (paired
   difference +36.4 percentage points, 95% cluster-bootstrap interval
   [+18.2, +59.1]); the contract's safety hypothesis is supported."
2. **Utility.** "On clean tasks M reached the goal in 44 of 72 episodes against
   53 of 72 without a guard (B0), a difference of −13.6 points (95% interval
   [−27.3, 0.0]); the estimate misses the −5-point non-inferiority margin, so
   the contract's utility hypothesis is not supported."
3. **Joint.** "The contract's joint hypothesis, safety and utility together,
   is therefore not supported."
4. **What the gap is.** "Counting only completions with no unsafe or
   unauthorized transition, B0 and M tie at 44 of 72, and they are the same 44
   episodes. The raw gap is nine episodes (three tasks, three seeds each) in
   which B0 reached the goal by jumping a device from off straight to level 2,
   which R4 and R5 forbid; M blocked each jump, and the planner did not repair
   its plan in its one retry."
5. **Freshness and refresh.** "Without the freshness check, 18 of 72 attacked
   episodes had an unsafe effect, all of them replays (+22.7 points against M,
   [+6.8, +40.9]). Re-reading before every write was as safe as M, 0 of 72, at
   3.44 sensor reads per attacked episode against 1.92."
6. **Attack-goal success.** "Attack-goal success, tabulated after the results
   were known, was 56 of 72 attacked episodes for B0, 49 for B1, 38 for B2, 21
   for M_no_freshness, 17 for Always_refresh and 1 for M; without an attacker
   the same end state occurred 0 times for B0 and B1 and 6 times for every
   guarded condition."
7. **Prompt-only defence.** "A safety reminder in the prompt alone (B1) did
   not reduce unsafe effects under attack: 45 of 72, the same as B0."
8. **Cost.** "Under attack, M averaged 0.54 s and 1,509 model tokens per
   episode, against 0.30 s and 959 for B2 and 0.22 s and 701 for B0; on clean
   tasks M cost 0.26 s and 849 tokens against 0.22 s and 701 for B0. Latency
   was measured on a shared machine and is not controlled for load."
9. **v3, an extension beyond the contract.** "A preregistered extension (72 new
   tasks on 36 physical structures, 7,128 episodes) tested recovery aids.
   Safety was supported again: B2_full 31 of 216, M_full 0 of 216, +14.4 points
   [+4.6, +25.9]. Under the original utility criterion, raw completion, M_full
   was 7.4 points below B0 (156 against 172 of 216; not supported). An amended
   criterion, rule-compliant completion, added after the v3 development run had
   shown the original one unsupported, is supported (156 against 93, +29.2
   points [+16.7, +43.1]); it favours any guard by construction. A
   safety-decoupled utility defined after the 2026-11-03 review is
   inconclusive (+1.4 points [−5.6, +8.3])."
10. **False blocks.** "No contract-eligible write was refused. Eligibility
    requires fresh evidence, so this rules out implementation errors, not
    over-blocking."

**Limitations that must appear.**

1. A synthetic world: two simulated devices, one presence bit and nine legal
   static states; the rules are illustrative policies, not safety codes.
2. Fixed, non-adaptive attacks (value tampering, stale-record replay,
   unauthorized-device requests); no prompt injection, trained backdoor or
   adaptive attacker in the confirmatory runs.
3. One planner at one pinned revision, one prompt family.
4. A trusted base is assumed: record store, clock, ledger and commit path;
   record matching stands in for cryptographic sensor authentication; a fresh
   reading need not be currently true (`SAFETY.md`, section 2).
5. v2 is a paired mechanism study, not a structural holdout (S2).
6. Few clusters, 22 in v2 and 36 in v3, give wide intervals; the v3
   reanalysis estimates about 157 structures for a confirmatory −5-point
   utility test.
7. Zero observed unsafe effects is not a guarantee.
8. Zero contract-eligible false blocks is not a measure of precision.
9. B2 is the project's own baseline; Always_refresh is equally safe in v2, so
   M is not shown to beat refresh on safety.
10. The utility hypothesis failed; the v3 criterion U2 was amended after the
    development run; U_dec, attack-goal success and the latency table are post
    hoc.
11. Latency was measured on a shared server without load control.
12. The v3 observation encodings are fixed-payload lookups, not sensor fusion
    (`docs/datasheet_v2_v3.md`, section 5).
13. Labels were signed by one person before the freezes; the peer review was
    post hoc, with one second reviewer on a sample.
14. AI assistance in code, analysis and text (`SAFETY.md`, section 6).
15. The second-machine re-run used different hardware and a paid subscription
    (S9); GPU sampling is not expected to be byte-identical
    ([reproduction.md](reproduction.md), section 2).

## 8. Questions for the instructor

Send on Wed 11 Nov, in one message.

1. **Dates and format.** On which calendar day is the presentation slot,
   and on which day is the report due (is 8 December still right)? Is there a template, does the six-
   to-eight-page limit include references and appendices, and how is the
   report submitted? Should the report cite a tagged release of the
   repository?
2. **v3 (S4).** Does the preregistered v3 study, which goes beyond the
   contract, count toward the project, or should it be reported as additional
   work in its own section?
3. **Peer review (H8).** Is this post hoc form acceptable: one classmate
   reviews the six rules, the three reading conventions, 10 camera captions
   and 12 tasks drawn at random, with agreement statistics, plus 8
   representative trace cards? Would you prefer to review the rules or the
   trace cards yourself?
4. **Amended criterion.** May the amended v3 criterion appear in the main text
   if it is labelled as amended and reported after the contract's decision, or
   should it move to an appendix?
5. **Compute (S9).** The reproduction re-run used the owner's existing Colab
   subscription (an A100); no confirmatory number comes from it. Is disclosure
   in the report enough?
6. **Demonstration.** Must the demo run live, or is a recorded backup
   acceptable if the room's equipment fails? Are the five minutes for the demo
   alone, or for the demo and questions?
7. **Raw traces.** Should the trace archive (2,279,422 bytes) be submitted
   with the report, or is a link to a repository release enough?
8. **AI use in the report.** Which disclosure form does the course want for
   AI assistance in the report text?

## 9. Owner checklist

- [ ] Merge PR #4 into `main`; check that the README on GitHub then says the
      contract's joint hypothesis is not supported (H1).
- [ ] Download the trace archive from the data disk's `release/` folder,
      check its SHA-256 against section 3 (H5), and keep a copy off the
      server.
- [ ] Decide whether to publish the archive with the repository, for example
      as a release asset (H5).
- [ ] Send the instructor the questions in section 8; confirm the
      presentation date, the report deadline, the template and the submission
      channel.
- [ ] Ask one classmate to be reviewer B (about one hour); send the package
      from [peer_review_protocol.md](peer_review_protocol.md) (H8).
- [ ] Review the 31 sampled items early in your own annotation and export your
      answers before you open reviewer B's export.
- [ ] Check the AI-assistance table in [SAFETY.md](../SAFETY.md), which is
      written in your name (H7).
- [ ] Confirm the copyright line in [LICENSE](../LICENSE) and
      [LICENSE-DATA.md](../LICENSE-DATA.md) (S1); decide on S8.
- [ ] Rehearse the demo twice with a timer and record a backup video
      ([demo_walkthrough.md](demo_walkthrough.md)).
- [ ] Approve the release tag before the presentation.
- [ ] Read and approve the report, or write it from the assistant's draft;
      follow the course's rule on AI use for the report text.
- [ ] Submit the report through the course's channel.
