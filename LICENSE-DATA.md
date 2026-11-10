# Licence for data and documentation

**Code.** All source code in this repository (`src/`, `scripts/`, `tests/`,
`demo/`, `review_desk/`, `skills/`) is under the MIT License; see `LICENSE`.

**Data and documentation.** Unless a file says otherwise, the following are
licensed under the Creative Commons Attribution 4.0 International licence
(CC BY 4.0, https://creativecommons.org/licenses/by/4.0/):

- the synthetic scenario corpora in `data/`;
- the machine-readable records in `artifacts/` (results, freezes, audits);
- the raw-trace bundle distributed with the project;
- the documentation in `docs/` and the top-level Markdown files.

Suggested attribution: "EviBound: Evidence-Bound Runtime Enforcement for
Smart-Home Agents, Xin Li, 2026, https://github.com/RealWayTrueX/EviBound".

**Not covered.**

- The Qwen2.5-7B-Instruct model weights are not part of this repository. They
  are distributed by their authors under the Apache License 2.0.
- External skills and tools that `skills/README.md` refers to are not copied
  here; each keeps its own licence.
- No third-party dataset is included. Datasets named as future work
  (`docs/week12_direction_review.md`) keep their own licences and are not
  redistributed.

**Third-party content check (2026-11-10).** The tracked files contain no
vendored third-party code or data. The demo and the review desk load web fonts
from Google Fonts at run time and fall back to system fonts offline.
