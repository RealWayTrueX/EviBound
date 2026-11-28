---
name: human-review-cards
description: Build a zero-dependency, offline bilingual HTML review desk so human domain owners or second reviewers can rapidly audit synthetic agent-security tasks, labels, and attack scenarios one card at a time — with visual state diagrams, plain-language onboarding, JSON/CSV sign-off export, and inter-rater agreement computation. Use when a programmatic task corpus needs human verification, peer review, or post-run sensitivity auditing.
---

# Human Review Cards & Bilingual Review Desk

Worked examples in EviBound:
- Template & docs: `review_desk/template.html`, `review_desk/README.md`, `docs/reading_guide.md`
- Generator & agreement scorer: `scripts/build_review_desk.py`, `scripts/review_agreement.py`
- Review protocol & sign-off record: `docs/peer_review_protocol.md`, `artifacts/v3_1_postrun_review.json`

## 1. Design cards for a non-author in one glance

- **One decision per card.** Show the initial device states visually (e.g., icons/level bars for `off / level 1 / level 2`), the hidden true state, the attacked reading (if any), the exact model-facing prompt text verbatim, and the expected attainable outcome.
- **Translate jargon into plain language.** Avoid opaque labels (`low` can be misread as "dim" rather than "level 1"); include a concise bilingual gloss and an interactive quick-start onboarding card (plus 2–3 warm-up examples) so a second reviewer can calibrate in 3 minutes.
- **Expose the attack hop.** When auditing security tasks, display *what* was perturbed (tamper vs. replay vs. out-of-scope) and *what happens if the planner believes the attack*, so reviewers catch nonsensical tasks or mislabeled expected states immediately.

## 2. Offline, single-file, zero-backend ergonomics

- Compile all task data into one self-contained `.html` file (`scripts/build_review_desk.py`) that opens cleanly via `file://` with no server or network access.
- Support keyboard navigation (`j`/`k` or arrow keys, quick approve/flag/reject shortcuts), auto-save progress in `localStorage`, filter by "unreviewed / required / flagged", and one-click export to structured JSON/CSV.
- Mark **required** vs. **optional** cards clearly when full review of hundreds of tasks is prioritized (e.g., all attack-battery and boundary-rule cards first).

## 3. Keep review audit trails clean and reproducible

- **Pre-run review (ideal):** Fix ambiguous wording or label bugs discovered in review *before* freezing the corpus, then seal the checklist and sign-off hash in the freeze archive.
- **Post-run review (when corpus was frozen first):** Never edit frozen labels or drop tasks silently. Record review completion in a dedicated machine-readable artifact (`artifacts/v3_1_postrun_review.json`), keep frozen confirmatory tables intact, and report any rejected tasks strictly in a post-hoc sensitivity analysis without replacement.
- **Second-reviewer agreement:** Use a fixed-seed sample (`docs/peer_review_protocol.md`) and compute percent agreement + Cohen's κ via `scripts/review_agreement.py`, reporting missing answers explicitly rather than silently dropping them.

## Common pitfalls caught in EviBound

- Putting contradictory room/scene names (e.g., "dark movie room" with a goal of `light=high`) distracted reviewers; keep scenario phrasing neutral and check alignment automatically.
- Static tables in spreadsheets hid multi-step sequencing constraints (R4/R5); small inline state diagrams cut review time and errors dramatically.

## Verification checklist

- [ ] Built HTML opens directly via `file://` with zero console errors or external network calls.
- [ ] Every card displays the exact prompt string sent to the model verbatim.
- [ ] Exported JSON/CSV round-trips cleanly through `scripts/review_agreement.py`.
- [ ] Sign-off record stores reviewer role, date, scope, and immutability constraints (never student IDs or emails if committed publicly).

## Related skills

`preregistered-agent-security-experiment`, `attack-defense-demo`, `artifact-design`.
