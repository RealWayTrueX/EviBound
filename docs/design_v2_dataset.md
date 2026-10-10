# EviBound Scenario Corpus v2 - Design (2026-10-10, DRAFT)

Purpose: fix the v1 corpus's documented structural weaknesses before the Week-8
preregistration and the Weeks 9-10 freeze. v1 stays frozen under
`data/scenarios/`; v2 lives in `data/scenarios_v2/` and is DRAFT until human
review + preregistration freeze it.

## 1. v1 weaknesses being fixed

| # | v1 weakness (evidence) | v2 fix |
|---|---|---|
| W1 | Perturbation type tied 1:1 to family (tamper<->reading/gentle_comfort/bright_ventilation, replay<->the rest) | Perturbation assigned per task instance, balanced within every family |
| W2 | All tasks authorize both actuators; authorization-negative evidence only from component tests | A3 families with proper-subset `authorized` sets |
| W3 | Same six templates shared across splits; only context labels differ (manifest: "Not structural OOD") | Disjoint `structure_id` sets per split (same family concepts, disjoint concrete structures) |
| W4 | Early draft had goals needing zero writes (caught by BFS audit pre-freeze) | Machine check: every goal branch requires 1-3 writes |
| W5 | Load/transition rules (3-5) never stressed by goal paths | Family parameterization records `rules_stressed`; checker verifies coverage |
| W6 | No per-task human-review trail | Review bundle + checklist + sign-off hash in manifest |

## 2. Schema v2 (superset of v1; runner must never serialize annotation
   fields into prompts)

Required per task:
- `task_id` (split_family_NN), `split`, `family`, `structure_id`
  (split-scoped, unique per concrete (initial, goals, authorized) tuple),
  `perturbation` (`tamper`|`replay`), `instruction`, `initial`
  {light,fan,presence}, `authorized` (list, may be a proper subset),
  `goal_present`, `goal_absent` (partial actuator maps, as v1).
- `authorized_subgoal_present`, `authorized_subgoal_absent`: partial maps or
  null. Non-null only for A3 tasks; defines the best legal outcome.
- `annotations` (review/documentation only, never shown to agents):
  `rules_stressed` (list), `writes_needed_present`, `writes_needed_absent`,
  `attack_explanation` (why the perturbed first observation flips the rational
  branch choice), `expected_safe_behavior` (free text, one line).

## 3. Family registry (8 families)

Six carried from v1 (same family concepts, re-parameterized structures):
reading, bright_work, gentle_comfort, strong_ventilation, bright_ventilation,
economy. Two new authorization-negative families:

- `light_only` (A3): authorized=[light]. Full goals include a fan change;
  authorized subgoal is the light part only. Tests confused-deputy writes to fan.
- `fan_only` (A3): authorized=[fan]. Present-goal includes fan high, but rule 6
  (fan high requires light>=low) makes the full goal legally unreachable without
  an unauthorized light write; authorized subgoal is fan low. Tests
  authorization x rule interaction.

World rules are unchanged (six provisional rules, implementation_contract.md).

## 4. Split plan

| Split | Families | Contexts per family | Tasks | Role |
|---|---|---|---|---|
| dev | 8 | 2 | 16 | debugging, prompt/recovery tuning |
| pilot | 8 | 2 | 16 | held-out pilot, metric freeze rehearsal |
| test | 8 | 3 | 24 | frozen main evaluation |

- Context labels remain split-disjoint (as v1).
- Family-conditioned `(initial, goal_present, goal_absent, authorized)` tuples
  are disjoint across splits: within each family concept, initial states and
  goal parameterizations differ (structural holdout, W3). Identical device
  tuples can recur under different family labels/instructions and are not
  counted as independent physical structures.
- Perturbation assignment: seeded RNG (seed recorded in manifest), balanced
  50:50 per split and >=1 of each type per family per split (W1).
- Every task keeps v1's three variants: clean / perturbed / boundary.
- Episode math at freeze (unchanged from v1): tasks x 3 variants x 6 conditions
  x 3 seeds; test = 24 x 3 x 6 x 3 = 1,296 episodes.

## 5. Storage and versioning

```
data/scenarios_v2/
  dev.jsonl  pilot.jsonl  test.jsonl   # canonical, sorted keys, one JSON per line
  manifest.json                        # registry + hashes + lifecycle status
reviews/v2/
  <split>.md          # human review cards (explicit HTML anchors per task)
  checklist.csv       # per-task reviewer decisions
  signoff.json        # reviewer, date, per-split decision counts, checklist hash
```

`manifest.json` records: schema_version=2, generator path + git commit, RNG
seed, per-split sha256 + task_ids + structure_ids, perturbation assignment,
machine-check report hash, and a `lifecycle` block per split:
`draft -> machine_checked -> human_reviewed -> frozen`. Freeze happens only at
preregistration; after freeze the files are immutable (hash-pinned).

## 6. Machine pre-checks (scripts/check_scenarios_v2.py)

Run before any human review so reviewers never see broken tasks:
1. Schema validation (fields, types, enums, sorted-keys canonical form).
2. Initial state legal under all six rules for both presence values.
3. Goal states legal under their respective presence value.
4. BFS over the rule-constrained transition graph: each branch requires 1-3
   writes (W4); record the shortest path into annotations.
5. Branch-flip probe: tampered/replayed first observation implies the opposite
   presence branch, so a branch-following policy pursues the wrong goal (attack
   effectiveness by construction).
6. A3-specific: authorized subgoal reachable using authorized devices only;
   full goal requires >=1 unauthorized write; subgoal is not the empty map
   unless abstention is the intended outcome (fan_only present-branch:
   subgoal fan=low is intended).
7. `rules_stressed` coverage: across each split, every rule 1-6 is stressed by
   >=1 family's goal path; checker recomputes stress from BFS paths and
   compares against annotations.
8. Cross-split: structure_id sets disjoint; no duplicate (initial, goals,
   authorized) tuples within a split.
9. Instruction lint: no branch leaks the actual initial presence incorrectly
   (instructions are branch-conditional, as v1), no unauthorized device named
   as required in A3 instructions (the goal text mentions the desired end
   state; authorization lives in the task metadata, as in real deployments).

## 7. Human review design (how Xin checks the corpus)

Full review load is small by design: 24 test + 16 pilot + 16 dev = 56 tasks.
- Review 100% of test, 100% of all A3 tasks (4 per split, 12 total; 6 are
  already inside the full test review), and >=50% sampled dev/pilot non-A3
  tasks. The deterministic sample produces 44 required cards, ~5-8 min each.
- Per-card content (auto-generated): instruction, initial-state table, both
  goal branches with BFS shortest write-path, authorized set and subgoals,
  perturbation mechanism + why it flips the rational branch, rules stressed,
  expected per-condition behavior (B0/B2/M one-liners), and reviewer questions
  (see checklist.csv columns).
- Reviewer records per-task decision (approve / fix / reject + comment) in
  `reviews/v2/checklist.csv`; `scripts/build_review_bundle.py --signoff`
  validates completeness and writes `signoff.json` + manifest lifecycle update.
- Disagreement handling: `fix`/`reject` tasks are regenerated with a new seed
  offset and re-reviewed; the corpus does not advance to `human_reviewed`
  until zero open items remain.
