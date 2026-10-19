# EviBound skills / 项目技能库

This folder turns the repeatable parts of the EviBound project into skills that
Claude Code and Codex can load in later sessions and that other students can
copy. Each skill is one folder with a `SKILL.md` (YAML front matter `name` +
`description`, then instructions). Both agents read this format.

本目录把项目里可重复的做法沉淀成 skills：以后的会话可以直接加载，也方便分享给
同学。每个 skill 是一个带 `SKILL.md` 的文件夹，Claude Code 和 Codex 都能读。

## Install / 安装

```bash
# Claude Code (all projects) / Codex
mkdir -p ~/.claude/skills ~/.codex/skills
for s in skills/*/; do
  ln -sfn "$PWD/$s" ~/.claude/skills/"$(basename "$s")"
  ln -sfn "$PWD/$s" ~/.codex/skills/"$(basename "$s")"
done
```

Symlinks keep the skills in sync with `git pull`. Inside this repository they
are also picked up when a session is started here and pointed at `skills/`.

## Skills in this repository

| Skill | What it captures | Source in this project | Status |
|---|---|---|---|
| [`preregistered-agent-security-experiment`](preregistered-agent-security-experiment/SKILL.md) | How to design, freeze and report an LLM-agent attack/defense experiment so results cannot steer the analysis | `AGENTS.md`, Week-8 and v3 preregistrations, freeze scripts, independent oracle | ready |
| [`attack-defense-demo`](attack-defense-demo/SKILL.md) | How to build a step-by-step, editable visual demo that is provably faithful to the experiment code | `demo/` (this demo and its cross-check test) | ready |
| [`literature-methods-review`](literature-methods-review/SKILL.md) | How to pick a presentation paper and write a methods map without losing the compared papers | the "第二轮汇报选论文" research thread, `docs/week12_direction_review.md` | ready |
| `human-review-cards` | Bilingual review cards that a non-author can judge in one glance (levels as "off / level 1 / level 2", one decision per card) | `scripts/build_review_page_v3.py`, `docs/reading_guide.md` | planned |
| `gpu-idle-autorun` | Waiting for a shared GPU without spending tokens (bash watcher in tmux, sustained-free threshold, never preempt other jobs) | `scripts/wait_gpu_then_run_v3.sh` | planned |

## Existing skills these build on / 可以直接引用的现成 skills

| Need | Skill | Where it comes from |
|---|---|---|
| More scientific design: test-first changes, focused review, root-cause debugging, cross-session handoff | `research`, `tdd`, `code-review`, `diagnosing-bugs`, `handoff` | [`mattpocock/skills`](https://github.com/mattpocock/skills) @ `49dd158`, already adopted in `docs/agentic_workflow.md` |
| Thorough, cited literature search across many sources | `deep-research` | Anthropic skills (Claude Code / claude.ai) |
| Beautiful, accurate charts and figures | `dataviz` (palette + chart rules), `data:create-viz` (matplotlib/plotly) | Anthropic skills |
| Diagrams that show the real mechanism | `artifact-diagramming` | Anthropic skills |
| Pages, decks and documents that look designed | `artifact-design`, `pptx`, `docx`, `pdf` | Anthropic skills |
| Writing or improving a skill and testing it | `skill-creator` | Anthropic skills |
| Browser checks of a page | `playwright` | Codex skill already on this Mac |

The project skills below reference these instead of copying them, so an
improvement upstream reaches this project too.

## Where Jev fits / JEV 放在哪里

`docs/agentic_workflow.md` already places TypeSafe's **Jev** (typed
`Choice`/`Score` decisions with confidence) outside the ground-truth and
enforcement path. The skills keep that boundary and name two optional uses:

1. **Review triage** (`human-review-cards`): rank cards by predicted ambiguity so
   the human reviews the uncertain ones first. The human still signs every card.
2. **Demo annotation** (`attack-defense-demo`): an optional "second opinion"
   column that scores whether a model plan looks risky, shown next to the
   deterministic guard so the audience can compare a learned judge with a
   provable check.

Neither use is wired in yet. Jev is a paid API, so per `AGENTS.md` it needs
explicit approval, a data disclosure, a pinned request schema and, for any
claim, a frozen comparison protocol.

## Adding a skill / 新增 skill

1. Notice a prompt or procedure repeated in two or more sessions.
2. Write it down as `skills/<name>/SKILL.md`: when to use it, the steps, the
   checks that prove it worked, and the mistakes this project already made.
3. Point to the files in this repository that are the worked example.
4. Use `skill-creator` to tighten the description and, if useful, add an eval.
