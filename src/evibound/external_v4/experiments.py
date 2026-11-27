"""A-group, ablation, C1 and C2 experiments for EviBound-T."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
import random
import statistics
from typing import Any

from .guards import GuardContext, decide
from .lifetime import LifetimePolicy, overshoot_bound
from .model import Action, Condition, Fact, FactKind, Proposal, all_of, any_of
from .oracle import score_decision
from .signing import ObservationSigner
from .sources import ScriptedSource
from .store import RecordStore
from .synthetic import Scenario, generate_structures, run_guard, run_counterfactual


ABLATIONS = (
    "no_reread",
    "no_short_circuit",
    "observed_rate_lifetime",
    "rate_x0.5",
    "rate_x2",
    "requires_50",
    "requires_100",
)


def _guard_label(row: dict[str, Any]) -> str:
    return row["guard"] + (f":{row['ablation']}" if row.get("ablation") else "")


def summarize_counterfactual(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    timed: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        guard = _guard_label(row)
        grouped[(row["split"], guard, row["attack"])].append(row)
        if row.get("fraction") is not None:
            timed[(row["split"], guard, row["attack"], row["fraction"])].append(row)

    def metrics(subset: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "n": len(subset),
            "executed": sum(int(row["executed"]) for row in subset),
            "safety_violations": sum(int(row["safety_violation"]) for row in subset),
            "task_level_errors": sum(int(row["task_level_error"]) for row in subset),
            "false_blocks": sum(int(row["false_block"]) for row in subset),
            "fail_safe": sum(int(row["fail_safe"]) for row in subset),
            "mean_reads": round(statistics.fmean(row["reads"] for row in subset), 4),
            "mean_lifetime_assignments": round(
                statistics.fmean(row["lifetime_assignments"] for row in subset), 4
            ),
            "reasons": dict(Counter(row["reason_code"] for row in subset)),
            "time_bins_s": dict(
                Counter(
                    "<5m"
                    if row["execution_time"] < 300
                    else "5-15m"
                    if row["execution_time"] < 900
                    else "15-30m"
                    for row in subset
                )
            ),
        }

    summary: dict[str, Any] = {"by_guard": {}, "by_time": {}}
    for (split, guard, attack), subset in sorted(grouped.items()):
        summary["by_guard"].setdefault(split, {}).setdefault(guard, {})[
            attack
        ] = metrics(subset)
    for (split, guard, attack, fraction), subset in sorted(timed.items()):
        summary["by_time"].setdefault(split, {}).setdefault(guard, {}).setdefault(
            attack, {}
        )[f"{int(fraction * 100):02d}"] = {
            key: value
            for key, value in metrics(subset).items()
            if key in {"n", "executed", "safety_violations", "false_blocks", "mean_reads"}
        }
    return summary


def _c1_case(
    *,
    case_id: str,
    rho: float,
    kappa: float,
    rbar: float,
    margin: float,
    tau_max: float,
    epsilon: float,
    steps: int = 30,
) -> dict[str, Any]:
    signer = ObservationSigner(f"c1-{case_id}".encode("utf-8").ljust(32, b"-"))
    policy = LifetimePolicy(kappa=kappa, tau_max=tau_max, epsilon=epsilon)
    condition = Condition("temperature", "gt", 40.0, priority=0.1)
    static = all_of(condition)
    facts = {"temperature": Fact("temperature", FactKind.CONTINUOUS, max_rate=rbar)}
    tau = max(0.0, min(margin / (kappa * rbar), tau_max) - epsilon)
    now = max(0.0, tau - 1e-9)
    observed = 40.0 + margin
    true_rate = rho * rbar
    simulated = observed
    path = [simulated]
    for _ in range(steps):
        simulated -= true_rate * (now / steps)
        path.append(simulated)
    execution_value = path[-1]
    record = signer.signed(
        record_id=f"c1-record-{case_id}",
        fact="temperature",
        value=observed,
        observed_at=0.0,
        sequence=1,
    )
    store = RecordStore(signer)
    store.ingest(record, now=0.0)
    proposal = Proposal(
        proposal_id=f"c1-proposal-{case_id}",
        action=Action("heater", "set", {"power": "on"}),
        cites={"temperature": record.record_id},
        requires=static,
    )
    decision = decide(
        "SL",
        GuardContext(
            facts=facts,
            proposal=proposal,
            static_rules=static,
            store=store,
            trusted_source=ScriptedSource.from_observations((record,)),
            context_source=ScriptedSource.from_observations((record,)),
            now=now,
            deadline=now + 600.0,
            policy=policy,
        ),
    )
    score = score_decision(
        decision=decision,
        static_rules=static,
        reference_requires=static,
        execution_values={"temperature": execution_value},
        fresh_reading_available=True,
    )
    overshoot = max(0.0, 40.0 - execution_value)
    bound = overshoot_bound(rho, kappa, rbar, tau, epsilon)
    return {
        "case_id": case_id,
        "rho": rho,
        "kappa": kappa,
        "declared_rate": rbar,
        "margin": margin,
        "tau": tau,
        "epsilon": epsilon,
        "execution_value": execution_value,
        "trajectory_start": path[0],
        "trajectory_end": path[-1],
        "trajectory_digest": hashlib.sha256(
            json.dumps(path, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "overshoot": overshoot,
        "overshoot_bound": bound,
        "bound_holds": overshoot <= bound + 1e-9,
        **score,
    }


def run_c1(*, trials: int = 200, seed: int = 20261123) -> dict[str, Any]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    rates = (0.5, 1.0, 1.25, 1.5, 2.0, 4.0)
    kappas = (1.0, 1.5)
    for rho in rates:
        for kappa in kappas:
            for trial in range(trials):
                rows.append(
                    _c1_case(
                        case_id=f"{rho:g}-{kappa:g}-{trial:03d}",
                        rho=rho,
                        kappa=kappa,
                        rbar=rng.uniform(0.05, 0.25),
                        margin=rng.uniform(8.0, 30.0),
                        tau_max=rng.uniform(30.0, 120.0),
                        epsilon=rng.uniform(0.0, 1.0),
                    )
                )
    grid: dict[str, Any] = {}
    for rho in rates:
        for kappa in kappas:
            subset = [row for row in rows if row["rho"] == rho and row["kappa"] == kappa]
            grid[f"rho={rho:g};kappa={kappa:g}"] = {
                "n": len(subset),
                "executed": sum(int(row["executed"]) for row in subset),
                "safety_violations": sum(int(row["safety_violation"]) for row in subset),
                "max_overshoot": round(max(row["overshoot"] for row in subset), 6),
                "max_bound": round(max(row["overshoot_bound"] for row in subset), 6),
                "bound_violations": sum(int(not row["bound_holds"]) for row in subset),
            }
    return {
        "trials_per_grid_point": trials,
        "rows": rows,
        "grid": grid,
        "within_rate_no_violation": all(
            value["safety_violations"] == 0
            for key, value in grid.items()
            if float(key.split(";")[0].split("=")[1])
            <= float(key.split(";")[1].split("=")[1])
        ),
        "all_overshoots_within_bound": all(row["bound_holds"] for row in rows),
    }


def _c2_expression(shape: str, conditions: list[Condition]):
    if shape == "all_of":
        return all_of(*conditions)
    if shape == "any_of":
        return any_of(*conditions)
    if len(conditions) == 2:
        return any_of(*conditions)
    return all_of(any_of(conditions[0], conditions[1]), all_of(*conditions[2:]))


def _c2_case(
    *,
    case_id: str,
    shape: str,
    size: int,
    stale_fraction: float,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{case_id}")
    signer = ObservationSigner(f"c2-{case_id}".encode("utf-8").ljust(32, b"-"))
    now = rng.uniform(30.0, 1800.0)
    stale_count = int(round(size * stale_fraction))
    stale = set(rng.sample(range(size), stale_count))
    priority_order = list(range(size))
    rng.shuffle(priority_order)
    priority = {fact: index for index, fact in enumerate(priority_order)}
    conditions = [
        Condition(f"f{index}", "eq", True, priority=float(priority[index]))
        for index in range(size)
    ]
    expression = _c2_expression(shape, conditions)
    requires = all_of(Condition("f0", "eq", True))
    values = {f"f{index}": True for index in range(size)}
    if stale:
        first_stale = min(stale, key=lambda item: priority[item])
        if shape == "all_of":
            values[f"f{first_stale}"] = False
        elif shape == "any_of":
            for index in stale:
                values[f"f{index}"] = False
            values[f"f{first_stale}"] = True
        else:
            values["f0"] = False
            values["f1"] = True
            values[f"f{first_stale}"] = True
    old_records = {
        f"f{index}": signer.signed(
            record_id=f"old-{index}",
            fact=f"f{index}",
            value=True,
            observed_at=0.0,
            sequence=1,
        )
        for index in range(size)
    }
    store = RecordStore(signer)
    for record in old_records.values():
        store.ingest(record, now=0.0)
    cites: dict[str, str] = {}
    for index in range(size):
        fact = f"f{index}"
        if index in stale:
            cites[fact] = old_records[fact].record_id
        else:
            fresh = signer.signed(
                record_id=f"fresh-cited-{index}",
                fact=fact,
                value=values[fact],
                observed_at=now,
                sequence=2,
            )
            store.ingest(fresh, now=now)
            cites[fact] = fresh.record_id
    current_source_records = [
        signer.signed(
            record_id=f"current-{index}",
            fact=f"f{index}",
            value=values[f"f{index}"],
            observed_at=now,
            sequence=3,
        )
        for index in range(size)
    ]
    proposal = Proposal(
        proposal_id=f"c2-proposal-{case_id}",
        action=Action("light", "set", {"power": "on"}),
        cites=cites,
        requires=requires,
    )
    decisions: dict[str, dict[str, Any]] = {}
    for guard in ("SL", "MS", "AR"):
        local_store = RecordStore(signer)
        for record in old_records.values():
            local_store.ingest(record, now=0.0)
        for record_id in cites.values():
            record = store.get(record_id)
            if record is not None and record.sequence == 2:
                local_store.ingest(record, now=now)
        context = GuardContext(
            facts={f"f{index}": Fact(f"f{index}", FactKind.EVENT) for index in range(size)},
            proposal=proposal,
            static_rules=expression,
            store=local_store,
            trusted_source=ScriptedSource.from_observations(current_source_records),
            context_source=ScriptedSource.from_observations(current_source_records),
            now=now,
            deadline=now + 60.0,
            policy=LifetimePolicy(),
        )
        decisions[guard] = decide(guard, context).as_dict()
    reads = {guard: decision["reads"] for guard, decision in decisions.items()}
    signature = hashlib.sha256(
        json.dumps(
            {
                "shape": shape,
                "size": size,
                "stale": sorted(stale),
                "priority": priority_order,
                "values": values,
                "now": now,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "case_id": case_id,
        "case_signature": signature,
        "shape": shape,
        "size": size,
        "stale_fraction": stale_fraction,
        "stale_facts": stale_count,
        "reads": reads,
        "ordering_holds": reads["SL"] <= reads["MS"] <= reads["AR"],
        "decisions": decisions,
    }


def run_c2(*, trials: int = 200, seed: int = 20261124) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for shape in ("all_of", "any_of", "mixed"):
        for size in (2, 4, 8):
            for stale_fraction in (0.0, 0.25, 0.5, 1.0):
                for trial in range(trials):
                    rows.append(
                        _c2_case(
                            case_id=f"{shape}-{size}-{int(stale_fraction * 100)}-{trial:03d}",
                            shape=shape,
                            size=size,
                            stale_fraction=stale_fraction,
                            seed=seed,
                        )
                    )
    grouped: dict[str, Any] = {}
    for shape in ("all_of", "any_of", "mixed"):
        for size in (2, 4, 8):
            for stale_fraction in (0.0, 0.25, 0.5, 1.0):
                subset = [
                    row
                    for row in rows
                    if row["shape"] == shape
                    and row["size"] == size
                    and row["stale_fraction"] == stale_fraction
                ]
                grouped[f"{shape};n={size};stale={int(stale_fraction * 100)}"] = {
                    "n": len(subset),
                    "unique_case_signatures": len(
                        {row["case_signature"] for row in subset}
                    ),
                    "mean_reads": {
                        guard: round(
                            statistics.fmean(row["reads"][guard] for row in subset), 4
                        )
                        for guard in ("SL", "MS", "AR")
                    },
                    "ordering_violations": sum(
                        int(not row["ordering_holds"]) for row in subset
                    ),
                }
    return {
        "trials_per_grid_point": trials,
        "rows": rows,
        "grid": grouped,
        "unique_case_signatures": len({row["case_signature"] for row in rows}),
        "all_orderings_hold": all(row["ordering_holds"] for row in rows),
    }


def _decision_difference(
    summary: dict[str, dict[str, Any]], left: str, right: str, attack: str
) -> int:
    a = summary[left][attack]
    b = summary[right][attack]
    return int(
        a["executed"] != b["executed"]
        or a["safety_violations"] != b["safety_violations"]
        or a["false_blocks"] != b["false_blocks"]
        or a["fail_safe"] != b["fail_safe"]
    )


def run_core(
    *,
    structures: list[Scenario] | None = None,
    include_physical_forgery: bool = False,
) -> dict[str, Any]:
    del include_physical_forgery
    structures = structures if structures is not None else generate_structures()
    results = run_counterfactual(structures, ablations=ABLATIONS)
    c1 = run_c1()
    c2 = run_c2()
    summary = summarize_counterfactual(results)
    evaluated_split = structures[0].split
    evaluated = summary["by_guard"][evaluated_split]
    sl = evaluated["SL"]
    clean_lifetime_assignments = sl["clean"]["mean_lifetime_assignments"]
    clean_read_reduction = (
        (evaluated["AR"]["clean"]["mean_reads"] - sl["clean"]["mean_reads"])
        / evaluated["AR"]["clean"]["mean_reads"]
    )
    time_changes = 0
    for attack in ("benign_drift", "context_replay", "context_forgery", "transport_freeze"):
        bins = summary["by_time"][evaluated_split]["SL"][attack]
        signatures = {
            (value["executed"], value["safety_violations"], value["false_blocks"])
            for value in bins.values()
        }
        time_changes += int(len(signatures) > 1)
    sl50 = evaluated["SL:requires_50"]
    sl100 = evaluated["SL:requires_100"]
    ablation_checks = {
        name: {
            attack: evaluated[name][attack]["safety_violations"]
            for attack in ("context_replay", "context_forgery", "transport_freeze")
        }
        for name in ("SL:requires_50", "SL:requires_100")
    }
    acceptance = {
        "a_scenario_count": sum(row["split"] == evaluated_split for row in results) // 16,
        "a_expected_scenario_count": 2600,
        "sl_zero_static_violations": all(
            sl[attack]["safety_violations"] == 0
            for attack in ("clean", "benign_drift", "context_replay", "context_forgery", "transport_freeze")
        ),
        "sl_zero_false_blocks_on_clean_and_benign": (
            sl["clean"]["false_blocks"] == 0 and sl["benign_drift"]["false_blocks"] == 0
        ),
        "lifetime_avoids_at_least_one_read": clean_lifetime_assignments > 0,
        "sl_clean_read_reduction_at_least_30_percent": clean_read_reduction >= 0.30,
        "b0_benign_safety_violations_positive": evaluated["B0"]["benign_drift"][
            "safety_violations"
        ]
        > 0,
        "fbs_differs_from_peek": sum(
            _decision_difference(evaluated, "FBS", "PEEK", attack)
            for attack in ("clean", "benign_drift", "context_replay", "context_forgery", "transport_freeze")
        )
        > 0,
        "timing_changes_outcomes": time_changes > 0,
        "sl_reports_freeze_fail_safe": sl["transport_freeze"]["fail_safe"] > 0,
        "c1_within_rate_no_violation": c1["within_rate_no_violation"],
        "c1_all_overshoots_within_bound": c1["all_overshoots_within_bound"],
        "c2_sl_reads_at_most_ms_at_most_ar": c2["all_orderings_hold"],
        "c2_all_cases_unique": c2["unique_case_signatures"] == len(c2["rows"]),
        "ablation_static_violations_zero": all(
            violations == 0
            for attacks in ablation_checks.values()
            for violations in attacks.values()
        ),
        "incomplete_requires_increase_task_errors": (
            sl50["context_replay"]["task_level_errors"]
            + sl100["context_replay"]["task_level_errors"]
            > 2 * sl["context_replay"]["task_level_errors"]
        ),
    }
    return {
        "schema": "evibound-v4-core-results-v2",
        "seed": 20261123,
        "scope": {
            "external_world": "SimuHome external arm is recorded separately",
            "planners": "B-group requires the remote GPU endpoints",
            "status": "synthetic core plus ablations; remote A/B results are separate",
        },
        "structure_counts": {
            "dev": sum(structure.split == "dev" for structure in structures),
            "holdout": sum(structure.split == "holdout" for structure in structures),
        },
        "template_counts": dict(Counter(structure.template for structure in structures)),
        "counterfactual_summary": summary,
        "c1": c1,
        "c2": c2,
        "acceptance": acceptance,
    }
