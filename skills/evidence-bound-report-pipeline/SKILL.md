---
name: evidence-bound-report-pipeline
description: Build a reproducible academic report (IEEE/LaTeX) where every number, table, data chart, and vector schematic is generated programmatically from committed result artifacts and locked by unit tests — with zero hand-typed numbers, automated SVG text-overflow checks, C2PA metadata cleanup, and visual page-by-page PDF verification. Use when writing or updating a course report, workshop paper, or journal manuscript backed by experiment JSON/fingerprint records.
---

# Evidence-Bound Report & Figure Pipeline

Worked example in EviBound:
- Number generator: `scripts/build_report_numbers.py` → `report/generated/*.tex` (`\V{key}` lookup macros)
- Charts & color system: `scripts/report_style.py`, `scripts/build_report_figures.py`
- Editable vector schematics: `scripts/build_report_diagrams.py` (native SVG + PDF export)
- Assembly & build: `report/assemble.py`, `report/late_parts.py`, `report/build.sh`
- Automated locks: `tests/test_report_numbers.py`, `tests/test_report_figures.py`

## 1. Zero hand-typed numbers in LaTeX

- Write a single deterministic script (`scripts/build_report_numbers.py`) that reads committed `artifacts/*.json` and `*.json.gz` records, asserts internal accounting invariants (e.g., episode splits sum to cell totals; zero unsafe writes under guarded conditions), and emits LaTeX macros (`\V{key}`, `\ci{key}`).
- Never type empirical counts, percentages, or confidence intervals directly into `.tex` prose.
- Add a unit test (`tests/test_report_numbers.py`) that fails if:
  - any generated `.tex` file is stale compared to current artifacts,
  - the manuscript references an unknown `\V{...}` or `\ci{...}` key, or
  - private fields (emails, student IDs, tokens) appear in the manuscript.

## 2. Programmatic figures: separate schematics from data charts

- **Shared visual grammar (`scripts/report_style.py`).** Define one color-vision-checked semantic palette across all figures (e.g., Blue = trusted / evidence-bound / descriptive; Orange = legal-write list; Aqua/Teal = plan-anchored; Red = attacker / unsafe / refuted; Slate = reference).
- **Data charts (`scripts/build_report_figures.py`).** Generate directly from artifact JSON via `matplotlib` at exact column/page widths (single-column or full-width IEEE `figure*`). Expose a `--data` flag and test plotted values against frozen records (`tests/test_report_figures.py`).
- **Mechanism schematics (`scripts/build_report_diagrams.py`).** Emit clean, editable native SVG (`<rect>`, `<path>`, `<text>` — no embedded rasters or `foreignObject`). Measure label widths using real font metrics and fail the build if any text overflows its box. Ground worked examples (e.g., Fig. 2) in a **real episode** pulled programmatically from committed fingerprints, not a hand-invented toy.

## 3. Clean metadata & reference hygiene

- **Strip transfer metadata.** Image files copied through cloud/chat pipelines may acquire C2PA content-credential metadata (`c2pa` / `jumb`). Regenerate charts via matplotlib and diagrams via script (and re-encode PNG previews with PIL) before final submission so every asset in `report/figures/` is clean.
- **Citation-order bibliography.** Have the assembler (`report/assemble.py`) sort `\bibitem` entries automatically in order of first `\cite{...}` appearance (required by IEEE) and drop unused entries; lock this with a unit test (`test_references_are_numbered_in_the_order_they_are_cited`).
- **Build portability.** Support both `pdflatex` and `tectonic` in `build.sh`, with fixed `SOURCE_DATE_EPOCH` for reproducible PDFs.

## 4. Visual & consistency audit before submission

Never trust a zero LaTeX exit code alone — always visually inspect **every rendered page** of the compiled PDF:
- Confirm exact page limit (e.g., 8 pages, balanced final column, zero overfull `\hbox` warnings, zero undefined references).
- Check cover date consistency against dates cited inside the body (e.g., post-run review date).
- Check awkward line breaks inside `\path{...}` or URLs, consistent British/American spelling, and that conditional sections (such as `late_parts.py` checking `artifacts/homes_record.json`) actually ran inside the full repository rather than a partial local folder!

## Verification checklist

- [ ] `python3 scripts/build_report_numbers.py --check` passes.
- [ ] `PYTHONPATH=src:. python3 -m unittest tests/test_report_numbers.py tests/test_report_figures.py -v` executes with **0 skipped** and **0 failed**.
- [ ] `report/figures/*` contains zero C2PA metadata markers.
- [ ] Every page of the final PDF has been visually inspected (page count, figures, margins, references).

## Related skills

`preregistered-agent-security-experiment`, `academic-diagram`, `academic-assignment-writing`, `academic-humanizer`, `dataviz`.
