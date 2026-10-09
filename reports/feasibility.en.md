# EviBound: overnight feasibility findings

23 September 2026 · [Chinese report](feasibility.zh-CN.md) · [Original contract](<../main (14).pdf>)

The engineering prototype is feasible, and evidence validation reduced executed violations in this synthetic experiment. The complete research hypothesis was **not met**: clean task completion fell by 20.83 percentage points relative to the unprotected agent, exceeding the permitted five-point loss. The safety comparison applies specifically to **B2's interface, which trusts agent-submitted presence values**, while M validates immutable collector records. B2 is a controlled baseline, not a reproduction of existing guardrail frameworks.

## Completed experiment

The system uses local Qwen2.5-7B-Instruct, two RTX 4090s, synthetic devices, and no paid inference API. The [official model](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) is Apache-2.0 licensed. Code, reports and small scenarios remain in this workspace; weights, environments, caches and raw traces are under `/mnt/HDD-8T-0/evibound_yanke/`. Execution ran inside tmux.

Development and pilot each completed 216 episodes. The frozen test completed **1,296 episodes**: 24 tasks × three observation variants × six conditions × three seeds. This includes 864 core episodes and 432 ablation/refresh diagnostics; every condition–variant cell contains 72 episodes. [Validation](../artifacts/final_validation.json) reports complete coverage, no issues, and no malformed or token-truncated responses. All 27 [component tests](../artifacts/component_tests.log) passed; independent rescoring found no stored-metric disagreements or inconsistent trajectories. These checks are separate from model performance.

Development B0 clean completion was **91.67%**, passing the 70% prerequisite. The dedicated repeated perturbation probe changed actions in **6/6 pairs**, passing the observation-sensitivity prerequisite. [Gate record](../artifacts/feasibility_gates.json)

The pipeline separates actual state, immutable observations, per-write enforcement and independent trajectory scoring. At most three writes and one rejection-triggered reread/resubmission are allowed. Evidence age must be between zero and two simulated time units, inclusive. Each successful write advances time by 0.25. [Implementation contract](../docs/implementation_contract.md)

## Main results

Percentages below use 72 episodes per cell. Reads include initial observation, rejection-triggered rereads and automatic refreshes. B1 adds a safety prompt; M_no_freshness retains provenance validation but removes age checks.

| Condition | Clean goal completion | Perturbed unsafe effect | Perturbed safe completion | Perturbed mean reads |
| --- | ---: | ---: | ---: | ---: |
| B0: unprotected | 91.67% | 50.00% | 0.00% | 1.000 |
| B1: safety prompt | 86.11% | 50.00% | 0.00% | 1.000 |
| B2: stateful guard | 70.83% | 37.50% | 12.50% | 1.208 |
| M: EviBound | 70.83% | 0.00% | 37.50% | 1.875 |
| M_no_freshness | 70.83% | 16.67% | 37.50% | 1.625 |
| Always_refresh | 70.83% | 0.00% | 50.00% | 3.278 |

Source: [complete summary](test/summary.csv), [paired comparisons](test/paired_effects.json).

The primary B2−M perturbed unsafe-effect difference was **+37.50 points**, with a task-clustered 95% bootstrap interval of **[20.83, 58.33]**. M increased perturbed safe completion by **25.00 points [4.17, 50.00]**. This supports the safety-benefit hypothesis within the specified interface and suite.

The clean M−B0 goal-completion difference was **−20.83 points [−37.50, −4.17]**. Its observed loss exceeds the five-point tolerance by **15.83 points**; the required completion-preservation claim is not established. The interval crosses the −5-point threshold, so it does not establish that the population loss necessarily exceeds five points either.

B0's 91.67% clean goal completion included unsafe successes: its clean safe completion was only **70.83%**, with **20.83%** experiencing unsafe effects. All 15 matched clean B0 successes lost by M contained unsafe B0 execution. M and B2 both achieved 70.83% clean completion, so evidence validation added no observed clean-completion loss beyond the stateful guard. Nevertheless, the original hypothesis compares M against B0's goal completion and remains unmet.

Removing freshness produced **12 unsafe episodes**, all in replay cases: 12/36 replay episodes versus M's 0/36. The pooled ablation difference was **16.67 points [4.17, 33.33]**. Always_refresh also recorded zero unsafe effects and achieved higher perturbed safe completion, at **1.403 additional reads per episode [1.097, 1.708]** relative to M. Thus the evidence supports a query-cost trade-off, not universal superiority over refreshing. In boundary cases, M remained safe but completed 48/72 tasks, versus B2's 49/72; evidence accepted for the first write can expire before the next.

## What the evidence does not establish

Nine perturbed M episodes began with an empty plan, completed no task and triggered no reread. A wrong absence observation can select an already-satisfied wrong branch; an execution guard cannot repair an omission without an attempted write. Remaining failures include unsuccessful model repairs after rejected transitions. All failed and blocked episodes remain in denominators. [Retained trajectories](test/retained_failures.jsonl)

The six provisional rules require presence for lighting and high fan speed, load ≤3, no direct off→high transition for either actuator, and lighting as an indicator for high fan speed. The high-fan presence rule is logically implied by the lighting-presence and indicator rules. All tasks authorize both actuators, so authorization-negative coverage comes from component tests, not model episodes.

The [dataset audit](../docs/dataset_card.md) confirms 1–3-write reachability, but splits share six templates and the 24 test tasks contain only 18 distinct structures. Perturbation type is tied to family. Task bootstrap handles repeated seeds, not shared-template dependence. Initial sampled proposals are reused across B0/B2/M and diagnostics; B1 uses a different prompt, and retries are condition-specific. Sampling uses temperature 0.2, top-p 0.9, top-k 20 and a 224-token generation budget. [Frozen protocol](../artifacts/protocol_freeze.json)

Logical call/token accounting includes reused proposals; recorded latency amortizes batch time and is not a production overhead estimate. Fixed corruption/replay, an immutable process-local store and atomic check/commit do not establish real-home, prompt-injection or backdoor robustness. Provenance already appears in [CaMeL](https://arxiv.org/html/2503.18813v2); this experiment does not claim its invention.

Policies, representative traces and the narrowed project scope still require human review. Proceed with the prototype as feasibility evidence; prioritize omission detection and valid transition repair before claiming acceptable utility preservation. Use the [30-episode reproduction entry](../scripts/reproduce_subset.sh) and [bilingual demonstration](../docs/demo_walkthrough.md) for review, retaining the frozen results unchanged.
