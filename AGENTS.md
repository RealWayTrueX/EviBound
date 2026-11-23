# EviBound Agent Guide

## Scope

This repository is a synthetic, offline cybersecurity study of runtime enforcement
for smart-home agents. Read `docs/research-contract.md` before changing research
semantics and `docs/roadmap_week6.md` before continuing semester work.

## Research Boundary

- Keep default experiments inside the deterministic simulator and synthetic
  scenario corpus. An unmodified, pinned SimuHome checkout may be used as an
  external arm through `src/evibound/external_v4/`; do not copy its data or
  code into this repository and do not publish modified episodes.
- Treat `data/scenarios/`, `reports/`, and `artifacts/` from the frozen v1 study as immutable.
- Gate all model-in-the-loop v2 evaluation behind the Week-8 preregistration.
- Keep `Background_dont_push_to_github/` local-only and exclude it from releases.
- Keep the independent oracle independent from backend and guard predicates.
- Preserve failures, rejections, empty plans, and format errors in denominators.
- Store models, caches, environments, and raw run traces under `/mnt/HDD-8T-0/evibound_yanke/`.
- For the v4 external arm, use SimuHome commit
  `83d28837b69f0cbf1bc02ed5334cb8b561a9d54d` and interact only through its
  public HTTP API.

## Required Workflow

1. Identify the active roadmap item and record the intended completion criterion.
2. Change code and tests together through the public interface.
3. Run `PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py' -v`.
4. Run `python3 scripts/check_scenarios_v2.py` when scenario semantics or corpus files change.
5. Record evidence in machine-readable artifacts before updating prose summaries.
6. Update `docs/roadmap_week6.md` and the local session handoff before stopping.

## Safety Rules

- Use simulated devices only; real locks, heaters, cameras, vehicles, occupied
  spaces, home accounts, and external control endpoints remain outside scope.
- Use paid services only after explicit approval and record the disclosure.
- Keep human approval authoritative for policies, labels, and release decisions.
