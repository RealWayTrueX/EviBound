# Datasheet: EviBound v2 and v3 task corpora / v2、v3 任务语料数据说明

Written 2026-11-03 after the independent review (findings B-01, B-02, B-04).
Every number below is generated from the frozen JSONL files by two scripts
that import no generator or guard code:

```bash
python3 scripts/audit_physical_overlap.py --output artifacts/physical_overlap_audit.json
python3 scripts/corpus_composition.py   --output artifacts/corpus_composition_v2_v3.json
```

The v1 corpus keeps its own card (`docs/dataset_card.md`).

## 1. What a task is

| Item | Description |
|---|---|
| **Task** | One JSON line. Fields: initial actuator levels and actual presence, two branch goals (someone present / nobody present), an authorization list, the instruction text, the first-observation attack (tamper or replay), labels, and annotations. |
| **Physical structure** | The tuple (initial state, `goal_present`, `goal_absent`, sorted `authorized`). This is the unit of statistical inference: clusters in every bootstrap are physical structures. Wording, modality, attack and family label are *not* part of it. |
| **Episode** | A task × variant (clean / perturbed / boundary) × condition × seed. Episodes are paired across conditions; they are not independent samples. |

The v3 inference unit is therefore 36 holdout structures, not 7,128 episodes.

## 2. Counts

| Split | Tasks | Physical structures | Notes |
|---|---:|---:|---|
| v2 dev | 16 | 15 | 3 structures also in v1 |
| v2 pilot | 16 | 15 | 3 structures also in v1 |
| v2 test | 24 | 22 | **12 structures (14 tasks) also in v1**; 10 of those structures (12 tasks) also in v1 dev |
| v3 dev | 12 | 12 | none shared with v1, v2 or v3 holdout |
| v3 holdout | 72 | 36 | none shared with v1 or v2; each structure appears twice |

Across v1, v2 and v3 there are **93 distinct physical structures** in total.

## 3. Structural independence (B-01)

- **v3 is a clean holdout.** Its generator excludes every v2 structure; the audit confirms zero overlap with v1 and v2, and dev and holdout are disjoint.
- **v2 is not.**
  - 12 physical structures span more than one v2 split (29 task rows). One of them occurs in dev, pilot and test.
  - Its test split shares 12 structures with v1. Ten of them (12 test tasks) also occur in v1 dev, the split on which the planner prompt was iterated in September.
  - Cause: the v2 generator did not exclude v1 structures, and `check_scenarios_v2.py` compared `structure_id` (which includes the split and family) instead of the physical tuple.
- **Consequence.** v2 results are valid as a paired comparison of conditions on the same tasks. They are not evidence of generalization to unseen structures, and they are not independent of the v1 and prompt-development material.
- **Fix for v4.** v4 generators exclude every signature already in `artifacts/physical_overlap_audit.json`, and the checker recomputes signatures with `scripts/audit_physical_overlap.py`.

## 4. v3 composition (holdout, 72 tasks)

| Dimension | Values |
|---|---|
| Task type | 48 dual-device, 24 authorization-negative |
| Attack on the first observation | 36 tamper, 36 replay |
| Observation encoding | 18 each: `presence_flag`, `motion_timer`, `camera_caption`, `multi_sensor` |
| Request language | 24 each: explicit, everyday, scene |
| Design cells | 12 modality × language cells, 6 tasks each (3 tamper, 3 replay). Each structure appears in two cells that differ in modality, language and attack |
| Actual presence | 44 present, 28 absent. `motion_timer` and `multi_sensor` are 13 present / 5 absent; the other two encodings are 9 / 9 |
| `writes_needed` label | 0 (12), 1 (44), 2 (14), 3 (2). For authorization-negative tasks the label counts the *authorized* part, and the 12 zero-write tasks are those where abstaining is correct. The full branch goals need 1–3 writes |
| Rules stressed | R1 72, R5 32, R3 14, R2 4, R6 4, R4 2. R2 is implied by R1 and R6 |
| Authorization sets | both 48, light only 12, fan only 12 |
| World size | 2 actuators × 3 levels and one presence bit; 9 legal static states; 4 distinct initial tuples; 7 distinct present-branch goals; 4 distinct absent-branch goals |

## 5. What the observation encodings are and are not (B-02)

- **How decoding works.** The trusted collector decodes a payload by exact lookup against the two payloads the task declares (`src/evibound/backend_v3.py`). `multi_sensor` signals always agree with each other, and the attack replaces the whole payload.
- **What the four encodings test.** Whether the planner can read and cite four input formats.
- **What they do not test.** Sensor fusion, conflicting sensors, partial corruption, or semantically equivalent payloads with different bytes.
- **How to name them.** In papers they are called *observation encodings*, not sensor modalities.
- **Implication.** Modality and language results are descriptive per cell (6 tasks from 6 structures), not causal effects within a structure.
- **v4.** Adds conflicting, partially corrupted and paraphrased observations.

## 6. Provenance, review and licence

- **Origin.** All tasks are synthetic and generated by the project's own scripts with fixed seeds. No external dataset content is included, and there is no personal data. Regenerating in a scratch copy reproduces every JSONL byte for byte; the manifests differ only in their `lifecycle` / `human_review` fields.
- **Human review.**
  - v2: the corpus owner signed 44 required rows (100% of test plus all authorization-negative tasks).
  - v3: the corpus owner signed 77 required cards, with zero open items. The checklist hash is recorded in `artifacts/week11_v3_prereg_freeze.json`.
  - The cards themselves are local-only (UQ server, `reviews/`).
- **Licence.** Code is under MIT (`LICENSE`); data, artifacts and documentation are under CC BY 4.0 (`LICENSE-DATA.md`), following the corpus owner's decision of 2026-11-03 (D7). *[Updated 2026-11-10: this line said that no licence had been chosen.]*
- **Hashes.** File hashes are in each `manifest.json` and in `artifacts/corpus_composition_v2_v3.json`.

本说明由脚本从冻结语料直接生成，用于回应 2026-11-03 复核的 B-01、B-02、B-04。

- v3 holdout 是干净的结构留出：36 个物理结构，与 v1、v2 零重叠。
- v2 不是结构留出：test 有 12 个结构与 v1 相同，v2 各 split 之间也有 12 个结构重复。v2 只能当作同任务上的配对比较。
- "四种模态"实际是四种观测编码，可信采集器在两个固定 payload 之间精确查表，测不到传感器融合或冲突。
- 许可证待负责人决定。
