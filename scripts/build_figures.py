#!/usr/bin/env python3
"""Render publication-friendly figures from completed EviBound analysis files.

No metrics are simulated or filled in. Missing groups remain visibly missing.
Usage: python3 scripts/build_figures.py --report-dir reports/test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter


CONDITION_ORDER = ["B0", "B1", "B2", "M", "M_no_freshness", "Always_refresh"]
VARIANT_ORDER = ["clean", "perturbed", "boundary"]
LABELS = {"B0": "B0", "B1": "B1", "B2": "B2", "M": "M",
          "M_no_freshness": "No freshness", "Always_refresh": "Always refresh"}
COLORS = {"B0": "#999999", "B1": "#E69F00", "B2": "#0072B2", "M": "#009E73",
          "M_no_freshness": "#CC79A7", "Always_refresh": "#56B4E9"}
VARIANT_LABELS = {"clean": "Clean observations", "perturbed": "Perturbed observations",
                  "boundary": "Freshness-boundary observations"}


def ordered(values, preferred):
    values = set(values)
    return [item for item in preferred if item in values] + sorted(values - set(preferred))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def configure_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.titlesize": 12, "axes.labelsize": 11,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.7, "axes.edgecolor": "#444444",
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "svg.fonttype": "none", "savefig.facecolor": "white",
        "figure.facecolor": "white", "figure.dpi": 130,
    })


def save_figure(figure, directory, name):
    for extension in ("svg", "png"):
        figure.savefig(directory / f"{name}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(figure)


def decorate_axis(axis, conditions, lookup, variant, *, percent):
    labels = []
    for condition in conditions:
        row = lookup.get((condition, variant))
        count = str(row["n"]) if row else "missing"
        labels.append(f"{LABELS.get(condition, condition)}\nn={count}")
    axis.set_xticks(range(len(conditions)), labels, rotation=25, ha="right")
    axis.set_axisbelow(True)
    axis.grid(axis="y", color="#DEDEDE", linewidth=0.6)
    if percent:
        axis.set_ylim(0, 1.13)
        axis.set_yticks([0, 0.25, 0.5, 0.75, 1])
        axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))


def rate_panels(rows, output, split):
    conditions = ordered((row["condition"] for row in rows), CONDITION_ORDER)
    variants = ordered((row["variant"] for row in rows), VARIANT_ORDER)
    lookup = {(row["condition"], row["variant"]): row for row in rows}
    figure, axes = plt.subplots(2, len(variants), figsize=(5.2 * len(variants), 8),
                                sharey=True, squeeze=False)
    metrics = [("unsafe_effect_rate", "Unsafe-effect rate"),
               ("safe_completion_rate", "Safe-completion rate")]
    for column, variant in enumerate(variants):
        for row_index, (metric, title) in enumerate(metrics):
            axis = axes[row_index, column]
            for position, condition in enumerate(conditions):
                row = lookup.get((condition, variant))
                if row is None:
                    continue
                value = row[metric]
                axis.bar(position, value, color=COLORS.get(condition, "#555555"),
                         width=0.72, edgecolor="white", linewidth=0.7)
                axis.text(position, value + 0.025, f"{value:.1%}", ha="center", va="bottom",
                          fontsize=8.5, color="#222222")
            decorate_axis(axis, conditions, lookup, variant, percent=True)
            if row_index == 0:
                axis.set_title(VARIANT_LABELS.get(variant, variant), pad=12)
            if column == 0:
                axis.set_ylabel(title)
    figure.suptitle(f"EviBound synthetic {split} suite: executed safety and task success",
                    fontsize=15, y=1.02)
    figure.text(0.5, -0.035,
                "n = episodes per bar. Intermediate executed violations count as unsafe. "
                "Raw rates; no independence or deployment guarantee is implied.",
                ha="center", va="top", fontsize=9, color="#444444")
    figure.tight_layout(h_pad=2.8, w_pad=1.6)
    save_figure(figure, output, "safety_completion_by_variant")


def reads_panels(rows, output, split):
    conditions = ordered((row["condition"] for row in rows), CONDITION_ORDER)
    variants = ordered((row["variant"] for row in rows), VARIANT_ORDER)
    lookup = {(row["condition"], row["variant"]): row for row in rows}
    figure, axes = plt.subplots(1, len(variants), figsize=(5.2 * len(variants), 4.1),
                                sharey=True, squeeze=False)
    max_reads = max(row["reads_mean"] for row in rows)
    upper = max(1.5, max_reads * 1.22)
    for column, variant in enumerate(variants):
        axis = axes[0, column]
        for position, condition in enumerate(conditions):
            row = lookup.get((condition, variant))
            if row is None:
                continue
            value = row["reads_mean"]
            axis.bar(position, value, color=COLORS.get(condition, "#555555"), width=0.72,
                     edgecolor="white", linewidth=0.7)
            axis.text(position, value + upper * 0.025, f"{value:.2f}", ha="center", va="bottom",
                      fontsize=9, color="#222222")
        decorate_axis(axis, conditions, lookup, variant, percent=False)
        axis.set_ylim(0, upper)
        axis.yaxis.set_major_locator(MaxNLocator(nbins=5))
        axis.set_title(VARIANT_LABELS.get(variant, variant), pad=12)
        if column == 0:
            axis.set_ylabel("Mean sensor reads per episode")
    figure.suptitle(f"EviBound synthetic {split} suite: observation-access cost", fontsize=15, y=1.06)
    figure.text(0.5, -0.05,
                "Includes initial observation, rejection-triggered re-reads, and Always_refresh queries. "
                "Sensor reads are not model calls or wall-clock latency.",
                ha="center", va="top", fontsize=9, color="#444444")
    figure.tight_layout(w_pad=1.6)
    save_figure(figure, output, "sensor_reads_by_variant")


def paired_effects_plot(effects, output, split):
    selected = [row for row in effects if row.get("split") == split and "perturbation" not in row
                and ((row.get("contrast") == "B2-M" and row.get("metric") == "unsafe_effect")
                     or (row.get("contrast") == "M-B0" and row.get("variant") == "clean"
                         and row.get("metric") == "goal_completion"))]
    if not selected:
        return []
    selected.sort(key=lambda row: (row["contrast"] != "B2-M",
                                   VARIANT_ORDER.index(row["variant"]) if row["variant"] in VARIANT_ORDER else 99))
    figure, axes = plt.subplots(1, 2, figsize=(13, max(3.4, 0.7 * len(selected))),
                                gridspec_kw={"width_ratios": [3, 1.2]})
    axis, numbers = axes
    labels = []
    for position, row in enumerate(selected):
        low, estimate, high = (100 * row[key] for key in ("ci95_low", "estimate", "ci95_high"))
        color = COLORS["B2"] if row["contrast"] == "B2-M" else COLORS["M"]
        axis.plot([low, high], [position, position], color=color, linewidth=2.2,
                  solid_capstyle="butt")
        axis.plot([low, high], [position, position], "|", color=color, markersize=10)
        axis.plot(estimate, position, "o", color=color, markersize=7, zorder=3)
        metric = "Unsafe effect: B2 - M" if row["contrast"] == "B2-M" else "Goal completion: M - B0"
        labels.append(f"{metric}\n{row['variant'].capitalize()}; {row['n_tasks']} task clusters")
        numbers.text(0, position, f"{estimate:+.1f} [{low:+.1f}, {high:+.1f}]",
                     ha="left", va="center", fontsize=10)
    axis.axvline(0, color="#555555", linewidth=0.9, linestyle="--", zorder=0)
    axis.set_yticks(range(len(selected)), labels)
    axis.set_ylim(len(selected) - 0.5, -0.5)
    axis.set_xlabel("Paired difference (percentage points; positive favors M)")
    axis.grid(axis="x", color="#DEDEDE", linewidth=0.6)
    axis.set_axisbelow(True)
    numbers.set_ylim(axis.get_ylim())
    numbers.set_xlim(0, 1)
    numbers.set_axis_off()
    numbers.set_title("Estimate [95% interval]", fontsize=10, loc="left", pad=14)
    figure.suptitle(f"EviBound synthetic {split} suite: prespecified paired effects", fontsize=14, y=1.04)
    figure.text(0.5, -0.08,
                "Percentile bootstrap over tasks; paired seeds are averaged within each task. "
                "Shared-template dependence is not captured by these intervals.",
                ha="center", va="top", fontsize=9, color="#444444")
    figure.tight_layout(w_pad=2)
    save_figure(figure, output, "paired_effects")
    return selected


def captions(rows, selected, split, input_hashes):
    task_counts = sorted({row["n_tasks"] for row in rows})
    episode_counts = sorted({row["n"] for row in rows})
    repetitions = sorted({row["n"] / row["n_tasks"] for row in rows if row["n_tasks"]})
    consistent = len(task_counts) == len(episode_counts) == len(repetitions) == 1
    if consistent:
        suite = (f"The analyzed {split} suite contains {task_counts[0]} synthetic tasks with "
                 f"{repetitions[0]:g} episodes per task in each condition/variant group "
                 f"({episode_counts[0]} episodes per bar).")
    else:
        suite = (f"The analyzed {split} suite has unequal group sizes: task counts {task_counts}, "
                 f"episode counts {episode_counts}. Each plotted bar labels its actual episode count.")
    lines = [
        "# EviBound figure captions and provenance", "", suite, "",
        "These are synthetic offline device scenarios generated from six shared task templates. "
        "Task identifiers are not independent real-world task families. Policies and labels are "
        "provisional and require human review. Results do not establish physical deployment safety, "
        "general adversarial robustness, or containment of trained backdoors.", "",
        "## Figure 1: Executed safety and safe task completion", "",
        "[SVG](safety_completion_by_variant.svg) · [PNG](safety_completion_by_variant.png)", "",
        "Top: fraction of episodes with at least one actually executed unsafe state or transition, "
        "including intermediate writes subsequently repaired. Bottom: final goal completion without "
        "any unsafe effect or unauthorized executed write. Columns separate clean, perturbed, and "
        "freshness-boundary observations. Bars are descriptive episode proportions, with failures "
        "and blocked episodes retained. They do not display confidence intervals; repeated seeds "
        "and shared templates must not be treated as independent episodes.", "",
        "## Figure 2: Sensor observation cost", "",
        "[SVG](sensor_reads_by_variant.svg) · [PNG](sensor_reads_by_variant.png)", "",
        "Mean sensor reads per episode includes the initial observation, rejection-triggered "
        "re-reads, and each Always_refresh query before a write. The count is a sensor-access cost, "
        "not wall-clock latency or model-token expenditure. The initial sampled planner response "
        "is shared across B0, B2, M, M_no_freshness, and Always_refresh within each task/variant/seed; "
        "B1 uses its separate safety prompt. Retry responses are condition-specific.", "",
    ]
    if selected:
        resamples = sorted({row["resamples"] for row in selected})
        seeds = sorted({row["bootstrap_seed"] for row in selected})
        lines.extend([
            "## Figure 3: Paired effects with task-cluster intervals", "",
            "[SVG](paired_effects.svg) · [PNG](paired_effects.png)", "",
            "Points show equal-task means of matched-seed differences. B2 minus M unsafe-effect "
            "differences and M minus B0 clean goal-completion differences are oriented so positive "
            "values favor M. Horizontal lines show percentile 95% bootstrap intervals over task "
            f"clusters ({resamples} resamples; fixed seed {seeds}). Matched repeated seeds are "
            "averaged within each task before resampling. Pair coverage is available in paired_effects.json. "
            "These intervals do not account for dependence across shared templates, policy uncertainty, "
            "or label error. A zero-width interval in this finite synthetic suite is not evidence "
            "of zero uncertainty outside the suite.", "",
            "The clean-completion tolerance is a difference no lower than -5 percentage points. "
            "An interval crossing that threshold is inconclusive for the tolerance claim; an "
            "unsafe-effect interval containing zero is inconclusive for superiority.", "",
        ])
    lines.extend([
        "## Condition labels", "",
        "B0: unprotected; B1: safety prompt; B2: stateful action guard; M: B2 plus exact observation "
        "provenance and freshness; No freshness: M_no_freshness; Always refresh: additional authentic "
        "sensor access before every write with the B2 policy guard.", "",
        "## Rendering and provenance", "",
        "Charts use English text, a colorblind-friendly palette, editable SVG text, and 300 dpi PNG. "
        "They are generated only from completed summary and paired-effect files; missing groups "
        "are never filled with zero or fabricated metrics.", "",
        "Input SHA-256 hashes:", "",
    ])
    lines.extend(f"- `{name}`: `{digest}`" for name, digest in sorted(input_hashes.items()))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--split", help="Required only if summary contains multiple splits")
    args = parser.parse_args()
    summary_path = args.report_dir / "summary.json"
    if not summary_path.is_file():
        parser.error(f"Completed analysis is required; missing {summary_path}")
    summary = read_json(summary_path)
    if not isinstance(summary, list) or not summary:
        parser.error("summary.json must contain a nonempty list of measured groups")
    splits = sorted({row["split"] for row in summary})
    if args.split is None and len(splits) != 1:
        parser.error(f"Multiple splits present {splits}; specify --split")
    split = args.split or splits[0]
    rows = [row for row in summary if row["split"] == split]
    if not rows:
        parser.error(f"No measured groups for split {split}")
    seen = set()
    for row in rows:
        key = (row["condition"], row["variant"])
        if key in seen:
            parser.error(f"Duplicate summary group {key}")
        seen.add(key)
        if not isinstance(row.get("n"), int) or row["n"] <= 0 or row.get("n_tasks", 0) <= 0:
            parser.error(f"Invalid measured sample count for {key}")
        for field in ("unsafe_effect_rate", "safe_completion_rate", "reads_mean"):
            value = row.get(field)
            if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                parser.error(f"Missing or invalid measurement {field} for {key}")
            if field.endswith("rate") and value > 1:
                parser.error(f"Rate exceeds one for {field}, {key}")
    effects_path = args.report_dir / "paired_effects.json"
    effects = read_json(effects_path) if effects_path.is_file() else []
    input_hashes = {summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    if effects_path.is_file():
        input_hashes[effects_path.name] = hashlib.sha256(effects_path.read_bytes()).hexdigest()
    configure_style()
    output = args.report_dir / "figures"
    output.mkdir(parents=True, exist_ok=True)
    rate_panels(rows, output, split)
    reads_panels(rows, output, split)
    selected = paired_effects_plot(effects, output, split)
    (output / "figures.md").write_text(captions(rows, selected, split, input_hashes), encoding="utf-8")
    print(json.dumps({"output": str(output), "split": split, "groups": len(rows),
                      "figure_pairs": 3 if selected else 2, "input_sha256": input_hashes}, sort_keys=True))


if __name__ == "__main__":
    main()
