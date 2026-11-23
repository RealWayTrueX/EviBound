# Peer and instructor review protocol / 同伴与教师评审协议

Status: protocol, written 2026-11-10, before any second reviewer has seen an
item. **Post hoc:** the v2 and v3 studies are frozen, so this review cannot
change any rule, label, task, prompt or result. It reports agreement and lists
disagreements; disagreements become reported limitations and inputs to v4.

| Item | Where |
|---|---|
| Review tool | the review desk, `review_desk/` (build: `python3 scripts/build_review_desk.py`) |
| Agreement and sampling script | `scripts/review_agreement.py` (tests: `tests/test_review_agreement.py`) |
| Desk build reviewed | v3 practice desk, run key `v3-a5fffa7a15f2-practice` (the frozen v3 corpus; corpus hashes as in `artifacts/week11_v3_prereg_freeze.json`) |
| Records | `reviews/peer_review/` (git-ignored, local-only) |
| Why this exists | the research contract asks for peer or instructor review of the rules and of representative traces; audit finding H8 in [course_closeout_2026-11-10.md](course_closeout_2026-11-10.md) |

## 中文摘要

- **目的。** 研究合同要求"规则和代表性轨迹"要有同学或老师审过。到今天为止只有负责人自己在每次冻结前签过字（v2 44 行，v3 77 张卡），没有第二个人、也没有一致性统计。本协议补上这一项。
- **事后性质。** v2、v3 都已冻结，这次评审**不能改任何标签或结果**，只报告一致率，分歧写进局限并作为 v4 的输入。
- **谁来审。** 审核人 A = 负责人；审核人 B = 一位同学或任课老师，没有参与过项目。
- **审什么。** 两人都审 6 条规则和 3 条读法约定；B 另外审一个按固定种子抽出的样本：10 句摄像头描述（有人、没人各 5 句）和 12 个 v3 holdout 任务（4 种模态 × 3 种说法，每格 1 个）。时间不够时只审前 8 个任务（"核心样本"）。代表性轨迹卡做好后，B（或老师）再审 8 张核心轨迹卡。
- **独立性。** 两份导出文件都保存之前，A 和 B 不讨论任何条目。B 用自己的电脑和浏览器打开离线文件。
- **统计。** 每类条目、每个问题报告 n、一致率、Gwet AC1 和有分歧的条目编号；缺答单独列出，不补。用 AC1 而不用 Cohen's kappa，是因为几乎所有答案都是"是"，这时 kappa 会失真甚至无定义。
- **时间。** B 审核心样本约一小时（完整样本一到一个半小时），另加约 20 分钟一起过分歧，轨迹卡另约半小时；A 在自己的标注之外只需导出和过分歧，约 35–40 分钟。
- **报告里写什么。** 一段方法说明、一张一致率表、分歧按类别计数，以及一句局限："评审在冻结之后进行，没有改变任何标签或结果。"

## 1. Purpose and limits

**Terms.**

- *Reviewer A* is the owner of the corpus. *Reviewer B* is a second person who
  did not build any part of the project: one classmate or the instructor.
- An *item* is one card on the desk: a rule, a reading convention, a camera
  caption or a task. Each item kind asks fixed yes/no *questions*, then a
  confidence (high / medium / low) and a decision (approve / needs fixing /
  reject).
- An *export* is the JSON file the desk writes when the reviewer presses
  导出 (Export). The *run key* identifies the desk build; exports with
  different run keys or item contents are not compared.

**What the review can show.** Whether a second person reads the rules,
conventions, captions, tasks and, later, traces the way the owner did, and
where the two readings differ.

**What it cannot show.**

- It cannot change a frozen label or result, and it was not part of the
  preregistered protocols.
- Agreement is not correctness: two reviewers can agree on a wrong label.
- One second reviewer and a small sample give descriptive numbers, not
  population estimates.
- Reviewer B may have heard the results in class, and the desk shows its own
  automatic checks on every card. Both can pull B towards agreement. B's cover
  note records what B knew beforehand.
- The desk covers the v3 corpus only (section 3.2).

## 2. Reviewers

| Role | Who | Conditions |
|---|---|---|
| A | the owner | answers every item during the owner's own desk annotation; does not see B's export before A's own export is saved |
| B | one classmate or the instructor | no part in building the project; uses their own computer and browser; agrees that the answers are used in the report |

**Privacy.** Reviewer B is named in the report only with B's consent;
otherwise the report says "a classmate". No file in the repository holds a
reviewer's name, e-mail address or student number. The agreement report uses
the labels A and B and does not copy the desk's reviewer ids.

## 3. What is reviewed

| Item set | Items | A | B | Questions (desk keys) |
|---|---:|---|---|---|
| Device rules R1–R6 | 6 | all | all | q1 wording clear · q2 rule sensible · q3 diagram correct · q4 Chinese accurate |
| Reading conventions (everyday words, motion timer and multi-sensor, named scenes) | 3 | all | all | q1 convention sensible · q2 Chinese accurate |
| Camera captions | 39 | all | sample of 10 | q1 readable at a glance · q2 matches the label · q3 Chinese accurate |
| v3 holdout tasks | 72 | all | sample of 12 (core: first 8) | q1 instruction clear · q2 goals sensible · q3 perturbation correct · q4 expected behaviour agreed |
| Representative traces | 14 strata | optional | 8 core cards, when the cards exist | section 3.3 |

Every item also takes a confidence, a decision, problem tags and a comment.
Counts come from the desk build (`python3 scripts/build_review_desk.py` prints
132 items: rule 6, convention 3, caption 39, task 84, of which 125 are
required).

### 3.1 Sampling rule, seed and the drawn sample

**Rule.** One `random.Random(20261110)` draws, in this order:

1. every rule and reading-convention item, in desk order;
2. the tasks: for each of the 12 cells of the 72 holdout tasks
   (observation encoding × request language, 6 tasks per cell,
   `docs/datasheet_v2_v3.md`), taken in sorted order of the desk's English
   labels, `rng.sample(sorted task ids, 1)`; then `rng.shuffle` of the 12
   drawn tasks gives the review order;
3. the captions: for each label ("encodes absent", then "encodes present"),
   `rng.sample(sorted caption ids, 5)`; captions are listed in desk order.

The core sample is the 9 rules and conventions, the 10 captions and the first
8 tasks in review order. Because the review order is a random permutation, the
core tasks are still a random sample of the holdout.

**Command.**

```bash
mkdir -p reviews/peer_review
python3 scripts/build_review_desk.py --out reviews/v3/review_desk.html --data-out reviews/peer_review/desk_data.json
python3 scripts/review_agreement.py --draw-sample reviews/peer_review/desk_data.json --seed 20261110 \
    --output reviews/peer_review/sample.json
```

**The drawn sample** (seed 20261110; `tests/test_review_agreement.py` checks
that this list equals the draw). On the desk, open an item by its row in the
left queue, or add `#` and the id with `_` replaced by `-` to the file's
address (for example `review_desk.html#v3-holdout-focus-14`).

<!-- sample:begin -->

| Order | Item | Desk title | Stratum | Core |
|---:|---|---|---|---|
| 1 | `rule-R1` | Rule R1 | rules | yes |
| 2 | `rule-R2` | Rule R2 | rules | yes |
| 3 | `rule-R3` | Rule R3 | rules | yes |
| 4 | `rule-R4` | Rule R4 | rules | yes |
| 5 | `rule-R5` | Rule R5 | rules | yes |
| 6 | `rule-R6` | Rule R6 | rules | yes |
| 7 | `conv-everyday` | Convention: everyday words → levels | conventions | yes |
| 8 | `conv-motion` | Convention: motion timer and multi-sensor | conventions | yes |
| 9 | `conv-scenes` | Convention: named scenes | conventions | yes |
| 10 | `cap-bd010e63f6` | Camera caption 2 | encodes present | yes |
| 11 | `cap-43954b75ac` | Camera caption 4 | encodes present | yes |
| 12 | `cap-21a586f5c8` | Camera caption 10 | encodes present | yes |
| 13 | `cap-3d02193e77` | Camera caption 11 | encodes present | yes |
| 14 | `cap-7682318114` | Camera caption 16 | encodes absent | yes |
| 15 | `cap-63a6b7b85b` | Camera caption 18 | encodes absent | yes |
| 16 | `cap-386a98d705` | Camera caption 19 | encodes absent | yes |
| 17 | `cap-534b1ce2e0` | Camera caption 28 | encodes present | yes |
| 18 | `cap-c97e6c34df` | Camera caption 34 | encodes absent | yes |
| 19 | `cap-730931f0e0` | Camera caption 38 | encodes absent | yes |
| 20 | `v3_holdout_focus_14` | hallway · soft lighting | camera caption × everyday phrasing | yes |
| 21 | `v3_holdout_focus_04` | kitchen · soft lighting | presence flag × named scene | yes |
| 22 | `v3_holdout_vent_only_06` | hallway · air circulation (light not authorized) | multi-sensor × explicit levels | yes |
| 23 | `v3_holdout_focus_13` | bedroom · soft lighting | presence flag × everyday phrasing | yes |
| 24 | `v3_holdout_focus_03` | garage · soft lighting | camera caption × named scene | yes |
| 25 | `v3_holdout_vent_only_00` | kitchen · air circulation (light not authorized) | camera caption × explicit levels | yes |
| 26 | `v3_holdout_vent_only_11` | garage · air circulation (light not authorized) | motion timer × explicit levels | yes |
| 27 | `v3_holdout_task_lighting_02` | hallway · bright lighting | multi-sensor × everyday phrasing | yes |
| 28 | `v3_holdout_focus_17` | bedroom · soft lighting | presence flag × explicit levels | no |
| 29 | `v3_holdout_task_lighting_14` | hallway · bright lighting | motion timer × everyday phrasing | no |
| 30 | `v3_holdout_vent_only_09` | bedroom · air circulation (light not authorized) | motion timer × named scene | no |
| 31 | `v3_holdout_vent_only_10` | hallway · air circulation (light not authorized) | multi-sensor × named scene | no |

<!-- sample:end -->

Five of the 12 drawn tasks are authorization-negative ("light not
authorized"); the holdout has 24 such tasks in 72. That is the draw, not a
choice, and it is reported as it is.

### 3.2 Why v3 tasks and not v2 tasks

- The desk is built for the v3 corpus only (`CORPORA` in
  `scripts/build_review_desk.py`), in practice mode: its export must not
  replace `reviews/v3/checklist.csv` and must not be signed off.
- The six rules are the same in v2 and v3, so the rule review covers the
  contract's confirmatory study (v2) as well.
- The v2 task labels were validated by the owner before the Week-8 freeze
  (44 required rows, all approved; the signed checklist is sealed inside
  `artifacts/week8_protocol_freeze.tar.gz`).
- If the instructor asks for v2 tasks specifically, build the v2 cards in a
  scratch clone only: `scripts/build_review_bundle.py` rewrites
  `reviews/v2/checklist.csv`. The agreement script reads desk JSON exports, not
  the CSV checklist, so a v2 comparison also needs a small CSV reader.

### 3.3 Representative traces (when the trace cards exist)

The contract asks for review of representative traces. No trace cards exist
yet; they are built from the raw traces (the archive described in
`docs/reproduction.md`, section 5). Strata are defined on the committed
episode fingerprints (`artifacts/episode_fingerprints_v2_formal_test.json.gz`,
`artifacts/episode_fingerprints_v3_holdout.json.gz`), which hold each
episode's task, variant, condition, seed, executed writes and four oracle
outcomes. Stratum sizes below are counted from those files.

| ID | Study | Condition | Variant | Episodes in the stratum | Size | What the card lets the reviewer check |
|---|---|---|---|---|---:|---|
| C1 | v2 | B2 | perturbed | unsafe effect | 30 | the attacked reading leads to an executed unsafe write when the guard trusts the cited value |
| C2 | v2 | M | perturbed | same task and seed as C1 | paired | the block, the re-read and the second plan on the same first proposal |
| C3 | v2 | B0 | clean | goal reached, not a safe completion | 9 | a rule-breaking completion behind the raw utility gap |
| C4 | v2 | M | clean | same task and seed as C3 | paired | the correct refusal and the failed repair |
| C5 | v2 | M_no_freshness | perturbed | unsafe effect | 18 | a replayed record passes provenance when the age check is removed |
| C6 | v2 | M | boundary | two proposals (a refusal, then a retry) | 44 | whether a refusal is justified when the evidence starts exactly at the age limit, including stale-but-harmless refusals that the false-block definition excludes |
| C7 | v3 | B2_full | perturbed | unsafe effect | 31 | the extension's safety contrast (S1) |
| C8 | v3 | M_full | perturbed | same task and seed as C7 | paired | the recovery aids after a block |
| O1 | v2 | M | perturbed | two proposals, goal not reached | 43 | a safe abandonment |
| O2 | v2 | Always_refresh | perturbed | any | 72 | the refresh diagnostic |
| O3 | v2 | B1 | perturbed | unsafe effect | 45 | the safety prompt alone does not stop the attack |
| O4 | v2 | B0 | perturbed | authorization violation | 3 | a write to a device the task does not authorize |
| O5 | v3 | B0 | clean | authorization violation | 28 | the source of the raw-completion deficit (U1) |
| O6 | v3 | M_full | clean | two proposals, goal reached | 63 | a repair after a refusal |

**Draw rule.** One `random.Random(20261110)`; for C1, C3, C5, C6, C7, O1–O6 in
this order, sort the stratum's episodes by (task id, seed) and take
`rng.choice`; C2, C4 and C8 take the episode of the paired condition with the
same task, variant and seed. Whoever builds the cards records the draw in the
card file before opening any drawn trace.

**Questions on each trace card** (keys q1–q4, so that the agreement script
handles a `trace` item kind without change):

- q1: the oracle's unsafe-effect label is correct, judged from the executed
  writes, the true presence and the written rules;
- q2: the goal and safe-completion labels are correct;
- q3: every guard decision (accepted or blocked, with its reason) follows the
  written rules and the evidence check of the condition;
- q4: the card's plain-language summary matches the raw trace.

Reviewer B (or the instructor) answers the 8 core cards (C1–C8); O1–O6 are
optional. Reviewer A does not need to answer trace cards: every "no" from B is
adjudicated (section 8), and the report gives the number of "no" answers per
question. If A also answers them, the agreement script compares A and B as for
the desk items.

## 4. Training

- **The desk's guide.** Every open of the desk starts an eight-page guide
  (purpose, devices and permission, the six rules with the legal-state grid,
  sensors and everyday phrases, attacks and authorization-negative tasks, what
  each question asks, card anatomy and keys) and a three-question warm-up
  (`review_desk/README.md`). Both reviewers complete it once before the first
  item. The warm-up items are generated, so they are not sample items.
- **Language.** The desk is written in Chinese first; the EN button in the
  header adds English helper text to questions, hints and summaries, and every
  guide page has an English title. A reviewer B who does not read Chinese
  first reads the English half of [reading_guide.md](reading_guide.md)
  (devices, levels, rules, attacks, conditions), uses the EN button, and leaves
  the three "Chinese accurate" questions out; they are excluded in the
  analysis with `--exclude rule:q4 --exclude convention:q2 --exclude caption:q3`.
- **How answers are entered.** `A` approves and marks every question "yes";
  `1`–`4` mark a question "no", which turns an approval into "needs fixing";
  `F` and `R` fill any unanswered question with "yes". A "no", a fix or a
  reject needs a one-line comment. A "yes" is therefore partly a consequence of
  the decision, which the analysis reports as it is.
- **Training record.** On a local file the guide record (pages seen, time,
  warm-up score) stays in the browser and is not in the export. B writes the
  warm-up score in the cover note.

## 5. Independence

1. A and B do not discuss any item, rule or answer until both exports are
   saved and their SHA-256 hashes are written in the adjudication note.
2. B receives only the desk file (`reviews/v3/review_desk.html`, built by the
   command in section 3.1), this protocol and the item list. B does not receive
   A's export, the results or the review cards of v2.
3. B opens the file on B's own computer, or in a private browser window: a
   local desk keeps its answers in the browser, so two reviewers in one browser
   profile would see each other's work.
4. A saves A's export before opening B's.
5. B returns the JSON export by a private channel. A reviewer outside the
   project's organization cannot write to the published desk, so the offline
   file is the route for B.

## 6. What is recorded

**The JSON export** (`jsonText()` in `review_desk/template.html`) is the
input of the analysis. Fields: `tool`, `version`, `mode`, `corpus`, `run_key`,
`corpus_files`, `corpus_sha256`, `exported_at`, `reviewer_id` (empty for a
local file), `summary`, and `items`, one per desk item with `id`, `kind`,
`required`, `item_hash`, `stale` and `verdict`. A verdict holds the question
answers `q1`… (`Y` or `N`), `decision` (`approve`, `fix`, `reject`), `conf`
(`high`, `med`, `low`), `tags`, `comment`, and bookkeeping fields (`kind`,
`item_hash`, `updated_at`, and `by` on the published desk). A verdict given on
older item content is exported as `null` with `stale: true`.

**The CSV checklist** (`csvText()`) has one row per task with the columns
`task_id, split, family, perturbation, required, q1_instruction_clear,
q2_goals_sensible, q3_perturbation_correct, q4_expected_behavior_agree,
q5_label_confidence, decision, comment`. It covers tasks only and carries no
run key or item hash, so it cannot prove that two reviewers saw the same
build. It is kept for the record but not used for agreement.

**Files kept** in `reviews/peer_review/` (git-ignored): `desk_data.json`,
`sample.json`, `A_review.json`, `B_review.json`, `agreement.json`, and
`adjudication.md` (hashes of both exports; one line per disagreement with
item, question, both answers, class and resolution; the date).

**Cover note** from each reviewer: date, time spent, warm-up score, language
used, questions skipped, and whether the reviewer knew the study's results.

## 7. Agreement measures

```bash
python3 scripts/review_agreement.py reviews/peer_review/A_review.json reviews/peer_review/B_review.json \
    --labels A B --items reviews/peer_review/sample.json --output reviews/peer_review/agreement.json
```

For every item kind and every question (q1–q4, confidence and decision; the
decision and confidence are also pooled over all kinds) the script reports:

- `n`: items answered by both reviewers (by at least two, with more reviewers);
- percent agreement: the share of those items with identical answers;
- Gwet's AC1 with its observed and chance agreement;
- the ids of the disagreeing items and both answers;
- missing answers per reviewer: items not reviewed, verdicts discarded as
  stale, and questions left blank on reviewed items. Nothing is imputed.

It exits with status 2 if the exports come from different desk builds (tool
version, run key, corpus hashes, item ids or item hashes differ) and with
status 1 for other input errors.

**Formula.** With n items answered by at least two reviewers, r_i answers on
item i, r_ik of them in category k, and q categories fixed by the question
(yes/no: 2; decision and confidence: 3):

```text
p_a  = (1/n) Σ_i Σ_k r_ik (r_ik − 1) / (r_i (r_i − 1))     observed agreement
π_k  = (1/n) Σ_i r_ik / r_i                                 share of category k
p_e  = (1/(q − 1)) Σ_k π_k (1 − π_k)                        chance agreement
AC1  = (p_a − p_e) / (1 − p_e)
```

For two reviewers p_a is the share of items with the same answer and π_k is
the mean of the two reviewers' shares of category k. Items with a single
answer enter neither p_a nor π_k.

**Why AC1 and not Cohen's kappa.** Kappa's chance agreement is Σ_k p_Ak p_Bk,
built from each reviewer's own answer shares. When nearly every answer is
"yes", that term approaches 1, so kappa can be small or undefined although the
reviewers agree on almost every item (the high-agreement, low-kappa paradox
described by Feinstein and Cicchetti, 1990). A high "yes" share is expected
here: the corpus passed machine checks and the owner's sign-off before the
freezes, and the owner's sealed v2 checklist approved all 44 required rows. In
AC1 the chance term is at most 1/q and shrinks as one answer dominates, so the
coefficient stays interpretable (Gwet, 2008). Worked example, taken from the
unit tests: 10 tasks, the reviewers agree on 9, A says "no" once and B twice.
Percent agreement is 90%, AC1 is 0.866, Cohen's kappa would be 0.615. When
every answer is "yes", AC1 is 1 and kappa is 0/0.

**Reading the numbers.** With 6 to 12 items per kind, one disagreement moves
percent agreement by roughly 8 to 17 points. The coefficients are descriptive;
no significance test is run. The list of disagreements matters more than the
coefficient.

## 8. Adjudication and reporting

After both exports exist, A and B go through every disagreement together
(about 20 minutes; a call is enough). Each disagreement gets one class:

| Class | Meaning | Consequence |
|---|---|---|
| R | one reviewer misread the item or the guide; both agree once it is pointed out | none beyond the count |
| A | the item is ambiguous: both readings are defensible | reported limitation, item listed |
| E | the item is wrong: a label, diagram, translation or expected behaviour is incorrect | reported limitation with the affected task ids; input to v4 |
| P | the reviewer disputes a synthetic rule or convention as a policy | reported as a design limitation (the rules are illustrative policies, not safety codes) |

**Rules.**

- Original answers are never edited. Agreement is computed on the original
  exports; adjudication only adds the class and a note.
- For each class E, the report names the task and states which frozen
  episodes use it (task id × 3 variants × every condition × 3 seeds); it does
  not rescore or rerun them.
- Every "no" on a trace card is adjudicated the same way.

## 9. What happens to the frozen results

Nothing. No rule, label, task, prompt, model output, oracle outcome or
decision of v1, v2 or v3 changes, whatever the review finds. The desk stays in
practice mode: do not overwrite `reviews/v3/checklist.csv` and do not run
`--signoff`. Disagreements of class A, E or P are reported as limitations in
the course report and carried into the v4 design
([v4_preregistration_draft.md](v4_preregistration_draft.md), section 4.2,
stratified human review before the v4 freeze).

## 10. Time estimate

Planning estimates, not measurements. The desk shows each reviewer's own pace
("每条约 N 秒") after a few items; A's pace from the owner's annotation can
be used to adjust B's sample before it is sent.

| Step | Reviewer A (owner) | Reviewer B |
|---|---|---|
| Guide and warm-up | already done; about 5 min to repeat | about 10 min (the guide itself takes one to two minutes, `review_desk/README.md`; reading the English reading guide takes longer) |
| 6 rules and 3 conventions | part of the owner's annotation | about 10 min |
| 10 captions | part of the owner's annotation | about 5 min |
| Tasks: core 8, full 12 | part of the owner's annotation | 25–40 min for 8, 35–60 min for 12 (3–5 min per task; the v2 review guide planned about 5 min per card, `docs/review_guide_v2.md`) |
| Export and cover note | about 5 min | about 5 min |
| Adjudication | about 20 min | about 20 min |
| Trace cards, second session (8 core) | adjudicates B's "no" answers, about 10 min | about 30–40 min |
| **Total** | **about 35–40 min beyond the annotation** | **about 1 hour for the core sample (1 to 1.5 hours for the full sample), plus 20 min of adjudication and the trace session** |

If B can give only one hour, B reviews the core sample (items 1–27) and the
trace cards go to the instructor.

## 11. What goes into the report

1. **Method, one paragraph.** Who reviewed (A, and B as "a classmate" or "the
   instructor"), what (the item counts above, the sampling rule and seed),
   when (after the freezes), with which tool, and that the review was post hoc
   and changed nothing.
2. **One table.** Per item kind: n, percent agreement and AC1 for each
   question, with the decision row pooled over all kinds.
3. **Disagreements.** Their number by class (R, A, E, P), and each class-E
   item named with the affected task ids.
4. **Trace review.** The number of "no" answers per trace question, with the
   strata involved.
5. **Limitation sentence.** "The peer review took place after the protocols
   were frozen, used one second reviewer on a sample, and changed no label or
   result; its disagreements are listed as limitations."
6. **Where the records are.** The agreement report may be published (it holds
   labels A and B and no comments); the exports, comments and adjudication
   note stay local unless the owner decides otherwise.

**References.** Feinstein, A. R. and Cicchetti, D. V. (1990), "High agreement
but low kappa: I. The problems of two paradoxes", *Journal of Clinical
Epidemiology*. Gwet, K. L. (2008), "Computing inter-rater reliability and its
variance in the presence of high agreement", *British Journal of Mathematical
and Statistical Psychology*.
