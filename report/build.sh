#!/usr/bin/env bash
# Build the course report: regenerate every number from the committed artifacts, then typeset.
#
#   bash report/build.sh            # writes report/evibound_report.pdf
#
# Needs python3 and a LaTeX installation with pdflatex (packages: mathptmx, helvet, lm, geometry,
# microtype, booktabs, tabularx, xcolor, tikz, caption, enumitem, titlesec, xurl, hyperref).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/build_report_numbers.py
cd report
BUILD="${REPORT_BUILD_DIR:-$ROOT/report/.build}"
mkdir -p "$BUILD"
# A fixed timestamp keeps the PDF identical from one build to the next.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1794960000}" FORCE_SOURCE_DATE=1
for pass in 1 2 3; do
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$BUILD" evibound_report.tex \
    > "$BUILD/pdflatex_pass${pass}.log" 2>&1 || { tail -30 "$BUILD/pdflatex_pass${pass}.log"; exit 1; }
done
cp "$BUILD/evibound_report.pdf" evibound_report.pdf
if grep -q "LaTeX Warning: Reference\|undefined" "$BUILD/evibound_report.log"; then
  grep "LaTeX Warning: Reference\|undefined" "$BUILD/evibound_report.log" | head; exit 1
fi
pages="$(grep -a -c '/Type */Page[^s]' evibound_report.pdf || true)"
command -v pdfinfo > /dev/null && pages="$(pdfinfo evibound_report.pdf | awk '/^Pages:/ {print $2}')"
echo "report/evibound_report.pdf: ${pages} pages"
