---
name: attack-defense-demo
description: Build a step-by-step, editable visual demo of an attack/defense experiment (LLM agent, attacker, runtime guard, scorer) that is provably faithful to the experiment's own code. Use when someone wants to show or explain what an attacker did, what the defense blocked and what each step changed, with adjustable prompts, parameters and models, for a presentation or for discussing a design.
---

# Attack/defense demo

Worked example: `demo/` in the EviBound repository (`index.html`, `engine.js`,
`app.js`, `serve.py`, `build_demo_data.py`, `tests/test_demo_engine.py`).

## Principles

1. **Never re-describe the experiment by hand. Export it.** A build script
   imports the real modules and writes prompts, rule texts, constants, task
   corpus and frozen results into one data bundle (`window.X = {...}` in a
   `.js` file so the page also works from `file://`). Re-run it after any repo
   change; show the git hash and result-file hash in the page footer.
2. **Port the decision logic, then prove the port.** Re-implement guard,
   recovery messages and scorer in the browser language with the same names
   and order of checks. Write a cross-check test: run every task x variant x
   condition through the port with deterministic scripted planners, feed the
   same planner replies to the real runner (keyed by the exact prompt text the
   real code builds), and require identical events, recovery messages and
   metrics. Break one constant on purpose once to confirm the test fails.
3. **Separate three kinds of numbers.** Scripted planners illustrate behaviour
   and must say so. Real rates come only from the frozen results file. Real
   model outputs come from a live model or replayed traces. Label each source on
   screen.
4. **Every step answers: who acted, what changed, why.** Steps are a state
   machine (setup, sensor read/attack, prompt, model plan, one guard check per
   write, reread, feedback, re-plan, score). Each step card shows the actor,
   a one-line effect in plain language, the individual checks as pass/fail
   chips, and the raw JSON behind a disclosure.
5. **Show belief next to truth.** Two small scenes: what the agent believes
   (from the observation it saw) and what is actually true. A violation lights
   up the truth scene, not the belief scene.
6. **Pending step is editable.** Before a prompt is sent or a model reply is
   executed, show it in an editor. One-off edits apply to this run; "make
   default" moves them into settings.
7. **Edits are drafts until saved.** Keep drafts in browser storage, save
   explicitly to a named preset file through the local server (or download
   JSON when static), store only the diff from repository defaults, and flag
   "deviates from frozen protocol" whenever parameters, prompts or tasks differ.
8. **Paired comparison table.** Run the same first plan under every condition
   so the audience sees the guard as the only variable, mirroring the
   experiment's paired design.
9. **Replay real traces.** Import the experiment's episode JSONL, re-execute
   with the port and print whether events and metrics match the record.

## Live models

A stdlib local server (`127.0.0.1` only) serves the page and forwards the exact
chat messages to an OpenAI-compatible endpoint (Ollama, LM Studio, vLLM through
an SSH tunnel) or a local transformers model. Keys come from environment
variables named in a backends file, never from the page. Report connection
errors in the pending panel with the fix.

## Checklist before showing it

- [ ] `build_demo_data.py` re-run; footer hash matches `git rev-parse --short HEAD`.
- [ ] Cross-check test passes (and was seen to fail on a deliberate break).
- [ ] One full run per condition family, in both light and dark theme, and at
      phone width with no horizontal scroll.
- [ ] Live model path tested at least against a stub endpoint.
- [ ] Scripted-planner disclaimer visible wherever its numbers appear.

## Related skills

`artifact-design` for the visual system, `dataviz` for result charts,
`artifact-diagramming` for the pipeline figure, `playwright` for scripted
browser checks.
