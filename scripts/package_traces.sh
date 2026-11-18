#!/usr/bin/env bash
# Package the retained raw traces into one archive for delivery and backup
# (research contract, section VII: "raw traces"). Read-only on the run folders.
#
#   EVIBOUND_DATA=/path/to/data-disk bash scripts/package_traces.sh [OUT_DIR]
#
# Writes OUT_DIR/evibound_raw_traces_<UTC date>.tar.gz and a MANIFEST.sha256
# listing every packaged file. Only episode traces, run configurations, hash
# files and completion markers are included: no model weights, caches, tokens
# or logs.
set -euo pipefail
: "${EVIBOUND_DATA:?set EVIBOUND_DATA to the data disk that holds runs/}"
RUNS="$EVIBOUND_DATA/runs"
OUT="${1:-$EVIBOUND_DATA/release}"
mkdir -p "$OUT"
stamp="$(date -u +%Y%m%d)"
list="$(mktemp)"
trap 'rm -f "$list"' EXIT
cd "$RUNS"
find . -type f \( -name '*.jsonl' -o -name 'run.config.json' -o -name '*.sha256' -o -name 'COMPLETE' \
     -o -path '*/analysis/*.json' -o -path '*/analysis/*.csv' \) \
     -not -path './reproduction_*' -not -name '*token*' | sort > "$list"
[ -s "$list" ] || { echo "no trace files under $RUNS" >&2; exit 1; }
xargs -d '\n' sha256sum < "$list" > "$OUT/MANIFEST_$stamp.sha256"
tar -czf "$OUT/evibound_raw_traces_$stamp.tar.gz" -T "$list"
( cd "$OUT" && sha256sum "evibound_raw_traces_$stamp.tar.gz" > "evibound_raw_traces_$stamp.tar.gz.sha256" )
echo "files: $(wc -l < "$list")"
du -sh "$OUT/evibound_raw_traces_$stamp.tar.gz" | cut -f1 | sed 's/^/archive size: /'
cat "$OUT/evibound_raw_traces_$stamp.tar.gz.sha256"
echo "run folders included:"; cut -d/ -f2 "$list" | sort | uniq -c
