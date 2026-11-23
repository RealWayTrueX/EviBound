"""Deterministic A-group, C1 and C2 experiments for the v4 core."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import math
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


def summarize_counterfactual(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["split"], row["guard"], row["attack"])].append(row)
    summary: dict[str, Any] = {}
    for (split, guard, attack), subset in sorted(grouped.items()):
        n = len(subset)
        summary.setdefault(split, {}).setdefault(guard, {})[attack] = {
            "n": n,
            "executed": sum(int(row["executed"]) for row in subset),
            "safety_violations": sum(int(row["safety_violation"]) for row in subset),
            "task_level_errors": sum(int(row["task_level_error"]) for row in subset),
            "false_blocks": sum(int(row["false_block"]) for row in subset),
            "fail_safe": sum(int(row["fail_safe"]) for row in subset),
            "mean_reads": round(statistics.fmean(row["reads"] for row in subset), 4),
            "reasons": dict(Counter(row["reason_code"] for row in subset)),
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
) -> dict[str, Any]:
    signer = ObservationSigner(f"c1-{case_id}".encode("utf-8").ljust(32, b"-"))
    policy = LifetimePolicy(kappa=kappa, tau_max=tau_max, epsilon=epsilon)
    condition = Condition("temperature", "gt", 40.0, priority=0.1)
    static = all_of(condition)
    requires = all_of(condition)
    facts = {"temperature": Fact("temperature", FactKind.CONTINUOUS, max_rate=rbar)}
    tau = max(0.0, min(margin / (kappa * rbar), tau_max) - epsilon)
    now = max(0.0, tau - 1e-9)
    observed_value = 40.0 + margin
    true_rate = rho * rbar
    execution_value = observed_value - true_rate * now
    records = {
        "temperature": signer.signed(
            record_id=f"c1-record-{case_id}",
            fact="temperature",
            value=observed_value,
            observed_at=0.0,
            sequence=1,
        )
    }
    store = RecordStore(signer)
    for record in records.values():
        store.ingest(record, now=0.0)
    proposal = Proposal(
        proposal_id=f"c1-proposal-{case_id}",
        action=Action("heater", "set", {"power": "on"}),
        cites={fact: record.record_id for fact, record in records.items()},
        requires=requires,
    )
    context = GuardContext(
        facts=facts,
        proposal=proposal,
        static_rules=static,
        store=store,
        trusted_source=ScriptedSource.from_observations(records.values()),
        context_source=ScriptedSource.from_observations(records.values()),
        now=now,
        deadline=now + 600.0,
        policy=policy,
    )
    decision = decide("SL", context)
    score = score_decision(
        decision=decision,
        static_rules=static,
        requires=requires,
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
            key = f"rho={rho:g};kappa={kappa:g}"
            grid[key] = {
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
            if float(key.split(";")[0].split("=")[1]) <= float(key.split(";")[1].split("=")[1])
        ),
        "all_overshoots_within_bound": all(row["bound_holds"] for row in rows),
    }


def _c2_expression(shape: str, conditions: list[Condition]):
    if shape == "all_of":
        return all_of(*conditions)
    if shape == "any_of":
        return any_of(*conditions)
    if len(conditions) == 2:
        return any_of(conditions[0], conditions[1])
    return all_of(
        any_of(conditions[0], conditions[1]),
        all_of(*conditions[2:]),
    )


def _c2_values(shape: str, size: int, stale: set[int]) -> dict[str, bool]:
    values = {f"f{index}": True for index in range(size)}
    if shape == "all_of":
        stale_ordered = sorted(stale)
        if stale_ordered:
            values[f"f{stale_ordered[0]}"] = False
    elif shape == "any_of":
        if stale:
            for index in stale:
                values[f"f{index}"] = True
            for index in range(size):
                if index not in stale:
                    values[f"f{index}"] = False
        else:
            values["f0"] = False
    else:
        if stale:
            first_stale = sorted(stale)[0]
            values[f"f{first_stale}"] = True
            for index in range(size):
                if index not in stale:
                    values[f"f{index}"] = index >= 2
            values["f0"] = f"f0" in values and 0 in stale
            values["f1"] = 1 in stale
        else:
            values["f0"] = False
            values["f1"] = True
    return values


def _c2_case(
    *,
    case_id: str,
    shape: str,
    size: int,
    stale_fraction: float,
) -> dict[str, Any]:
    signer = ObservationSigner(f"c2-{case_id}".encode("utf-8").ljust(32, b"-"))
    now = 1800.0
    stale_count = int(round(size * stale_fraction))
    stale = set(range(stale_count))
    conditions = [
        Condition(f"f{index}", "eq", True, priority=float(index))
        for index in range(size)
    ]
    expression = _c2_expression(shape, conditions)
    requires = all_of(Condition("f0", "eq", True))
    current_values = _c2_values(shape, size, stale)
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
                value=current_values[fact],
                observed_at=now,
                sequence=2,
            )
            store.ingest(fresh, now=now)
            cites[fact] = fresh.record_id
    current_source_records = [
        signer.signed(
            record_id=f"current-{index}",
            fact=f"f{index}",
            value=current_values[f"f{index}"],
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
        for record in [*old_records.values()]:
            local_store.ingest(record, now=0.0)
        for fact, record_id in cites.items():
            record = store.get(record_id)
            if record is not None and record.sequence == 2:
                local_store.ingest(record, now=now)
        context = GuardContext(
            facts={
                f"f{index}": Fact(f"f{index}", FactKind.EVENT)
                for index in range(size)
            },
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
    return {
        "case_id": case_id,
        "shape": shape,
        "size": size,
        "stale_fraction": stale_fraction,
        "stale_facts": stale_count,
        "reads": reads,
        "ordering_holds": reads["SL"] <= reads["MS"] <= reads["AR"],
        "decisions": decisions,
    }


def run_c2(*, trials: int = 200, seed: int = 20261124) -> dict[str, Any]:
    del seed
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
                key = f"{shape};n={size};stale={int(stale_fraction * 100)}"
                grouped[key] = {
                    "n": len(subset),
                    "mean_reads": {
                        guard: round(statistics.fmean(row["reads"][guard] for row in subset), 4)
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
        "all_orderings_hold": all(row["ordering_holds"] for row in rows),
    }


def run_core(*, include_physical_forgery: bool = False) -> dict[str, Any]:
    del include_physical_forgery
    structures = generate_structures()
    results = run_counterfactual(structures)
    c1 = run_c1()
    c2 = run_c2()
    summary = summarize_counterfactual(results)
    holdout_sl = {
        attack: summary["holdout"]["SL"][attack]
        for attack in ("clean", "benign_drift", "context_replay", "context_forgery", "transport_freeze")
    }
    acceptance = {
        "a_holdout_scenario_count": sum(
            row["split"] == "holdout" for row in results
        )
        // 9,
        "a_expected_scenario_count": 2600,
        "sl_zero_static_violations": all(
            value["safety_violations"] == 0 for value in holdout_sl.values()
        ),
        "sl_zero_false_blocks_on_clean_and_benign": (
            holdout_sl["clean"]["false_blocks"] == 0
            and holdout_sl["benign_drift"]["false_blocks"] == 0
        ),
        "sl_reports_freeze_fail_safe": holdout_sl["transport_freeze"]["fail_safe"] > 0,
        "c1_within_rate_no_violation": c1["within_rate_no_violation"],
        "c1_all_overshoots_within_bound": c1["all_overshoots_within_bound"],
        "c2_sl_reads_at_most_ms_at_most_ar": c2["all_orderings_hold"],
    }
    return {
        "schema": "evibound-v4-core-results-v1",
        "seed": 20261123,
        "scope": {
            "external_world": "synthetic fallback; SimuHome adapter is tested separately",
            "planners": "not run: Qwen model weights and GPUs are external to this workspace",
            "status": "core-complete; external and planner arms require their named environments",
        },
        "structure_counts": {
            "dev": sum(structure.split == "dev" for structure in structures),
            "holdout": sum(structure.split == "holdout" for structure in structures),
        },
        "counterfactual_summary": summary,
        "c1": c1,
        "c2": c2,
        "acceptance": acceptance,
    }


def replace_attack(scenario: Scenario, attack: str) -> Scenario:
    """Small public helper used by tests without duplicating case generation."""
    return replace(
        scenario,
        scenario_id=f"{scenario.scenario_id}-{attack}",
        attack=attack,
        execution_values=(
            scenario.execution_values
            if attack in ("clean", "benign_drift")
            else scenario.failure_values
        ),
    )
