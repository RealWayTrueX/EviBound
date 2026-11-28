# EviBound Skills / 项目技能库

This directory documents **(1) the reusable skills we created from EviBound** (ready to install into Claude Code, Codex, or Antigravity) and **(2) the external skills we used** during the project, as encouraged for COSC 723.

Each skill lives in its own folder with a `SKILL.md` file (YAML frontmatter `name` + `description`, followed by concise, actionable procedures, verification checks, and concrete pitfalls learned in this project).

本目录汇总了两部分内容：**（1）我们在 EviBound 项目中沉淀并开源的 6 个可复用自研 skills**（可直接安装到 Claude Code、Codex 或 Antigravity 中使用）；**（2）本项目实际采用过的外部 skills 清单及使用方式**。

---

## Install / 安装自研 skills

```bash
# Claude Code / Codex / Antigravity
mkdir -p ~/.claude/skills ~/.codex/skills ~/.gemini/antigravity/skills
for s in skills/*/; do
  name="$(basename "$s")"
  ln -sfn "$PWD/$s" ~/.claude/skills/"$name"
  ln -sfn "$PWD/$s" ~/.codex/skills/"$name"
  ln -sfn "$PWD/$s" ~/.gemini/antigravity/skills/"$name"
done
```

Symlinks keep installed skills synchronized with `git pull`.

---

## 1. Skills Built in This Project / 本项目自研 skills（6 个，全部可用）

| Skill | What it captures / 解决什么问题 | Worked example in EviBound / 仓库实例 |
|---|---|---|
| [`preregistered-agent-security-experiment`](preregistered-agent-security-experiment/SKILL.md) | End-to-end design of trustworthy LLM-agent security experiments: hash-frozen preregistration, independent attainability oracle, exact-target vs. unrequested-change side-effect metrics, controlled refusal-feedback ladders, and multi-model / multi-scale exploratory checks. | `AGENTS.md`, `docs/v3_1_preregistration.md`, `src/evibound/attainability.py`, `src/evibound/recovery_v3_1.py`, `src/evibound/homes.py`, `scripts/freeze_v3_1_prereg.py`, `scripts/analyze_v3_1.py` |
| [`evidence-bound-report-pipeline`](evidence-bound-report-pipeline/SKILL.md) | Artifact-driven academic report pipeline with zero hand-typed numbers (`\V{key}` macro generation), programmatic editable SVG schematics with box-overflow assertions, unit-tested data charts, C2PA metadata cleanup, and reproducible LaTeX builds (`pdflatex` / `tectonic`). | `scripts/build_report_numbers.py`, `scripts/build_report_diagrams.py`, `scripts/build_report_figures.py`, `scripts/report_style.py`, `tests/test_report_numbers.py`, `tests/test_report_figures.py` |
| [`attack-defense-demo`](attack-defense-demo/SKILL.md) | Building an interactive, step-by-step attack/defense visual demo whose browser decision logic is cross-checked by unit tests against the real experiment engine and supports live local models plus real-trace replay. | `demo/` (`index.html`, `engine.js`, `app.js`, `serve.py`, `build_demo_data.py`), `demo/tests/test_demo_engine.py`, `docs/demo_walkthrough.md` |
| [`human-review-cards`](human-review-cards/SKILL.md) | Designing self-contained, offline bilingual HTML review desks for human verification of synthetic task corpora, with visual state cards, plain-language onboarding, JSON/CSV sign-off export, and inter-rater agreement checks. | `review_desk/` (`template.html`, `README.md`), `scripts/build_review_desk.py`, `scripts/review_agreement.py`, `docs/peer_review_protocol.md`, `artifacts/v3_1_postrun_review.json` |
| [`literature-methods-review`](literature-methods-review/SKILL.md) | Systematic paper selection for course presentations and mechanism-level related-work audits: primary-source venue/title verification, exclusion-list matching, and method-to-roadmap mapping. | `docs/related_work_2026-11.md`, SimuHome (ICLR 2026) presentation & EviBound-T v4 integration |
| [`gpu-idle-autorun`](gpu-idle-autorun/SKILL.md) | Polite, crash-resilient experiment execution on shared multi-GPU Linux servers: sustained-free VRAM checks, `nice` priority, `tmux` detachment, episode-identity resume, and fingerprint-only result publishing. | `scripts/wait_gpu_then_run_v3.sh`, `scripts/run_v3_1.sh`, `scripts/run_v3_1_model.sh`, `scripts/run_homes.sh`, `scripts/v3_1_step.sh` |

---

## 2. External Skills Used in This Project / 本项目使用的外部 skills

Third-party skills are referenced by repository and pinned commit rather than vendored into this repository.

| Skill(s) | Source | How we used them in EviBound / 在本项目中的实际用途 |
|---|---|---|
| `research`, `tdd`, `code-review`, `diagnosing-bugs`, `handoff` | [`mattpocock/skills`](https://github.com/mattpocock/skills) @ `49dd158` | Test-first implementation of guard, oracle, and multi-home engines (251 unit tests); root-cause trajectory analysis (isolating v2's utility gap to failed post-refusal recovery); structured cross-session handoff notes. |
| `academic-diagram` | [`plbbl/academic-diagram-skill`](https://github.com/plbbl/academic-diagram-skill) @ `501efb0` | Guided the design of editable vector schematics (`scripts/build_report_diagrams.py` for Fig. 1 architecture overview and Fig. 2 worked refusal ladder) with consistent role colors and automated text-overflow assertions. |
| `academic-assignment-writing` | [`RealWayTrueX/academic-assignment-writing`](https://github.com/RealWayTrueX/academic-assignment-writing) @ `9e45a36` (author's own skill) | Structured the IEEE course report in clear, human-readable prose with style audits (`scripts/style_audit.py`). |
| `academic-humanizer` | [`AIScientists-Dev/academic-humanizer`](https://github.com/AIScientists-Dev/academic-humanizer) @ `94b88b2` | Removed formulaic phrasing, excessive hedging, and inflated verbs while keeping claims strictly calibrated to statistical evidence. |
| `dataviz`, `data:create-viz` | Built-in agent skills (Anthropic) | Color-vision-checked palette (`scripts/report_style.py`) and paired forest/bar/scale figures (`scripts/build_report_figures.py`). |
| `deep-research` | Built-in agent skills (Anthropic) | Broad 2024–2026 literature sweep across runtime enforcement, provenance, commit-time freshness, and guardrail feedback (`docs/related_work_2026-11.md`). |
| `pptx`, `pdf`, `playwright` | Built-in agent skills (Anthropic / Codex) | Paper presentation deck layout & geometry audits (SimuHome ICLR 2026 deck), page-by-page PDF visual inspection, and browser checks of the demo and GitHub repository. |
| `skill-creator` | Built-in agent skills (Anthropic) | Tightening skill descriptions, scopes, and checklists in this directory. |

---

## Authoring Convention / 编写规范

Every skill in `skills/<name>/SKILL.md` follows four rules:
1. **Trigger clearly**: YAML `description` states both *what* the skill does and *when* to invoke it.
2. **Ground in real code**: Link directly to worked files in this repository rather than abstract advice.
3. **Include verifiable checks**: End with a concrete checklist or command that proves the procedure worked.
4. **Capture real pitfalls**: Record actual bugs or methodological traps encountered in EviBound so future runs avoid repeating them.
