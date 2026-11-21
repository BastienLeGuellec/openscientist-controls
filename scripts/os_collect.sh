#!/usr/bin/env bash
# Wait for submitted jobs to finish (one at a time, in order), then save each report and artifacts to
# runs/<label>/ and log status, duration and the OpenRouter balance when each one ends.
# Usage: os_collect.sh <label>=<job_id> [...]
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MA=$(cd "$HERE/.." && pwd)
OS_URL=${OS_URL:-http://localhost:8081}
OS_KEY=$(cat "$MA/.os_key")
ORKEY=$(grep -E "^OPENROUTER_API_KEY=" "$MA/../.env" | head -1 | cut -d= -f2- | tr -d "\"' ")
usage() { curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $ORKEY" | python3 -I -c "import json,sys; print(json.load(sys.stdin)['data']['usage'])"; }
LOG="$MA/runs/collect_log.tsv"
[ -f "$LOG" ] || printf "label\tjob_id\tstatus\tfinished\topenrouter_usage\n" > "$LOG"
for pair in "$@"; do
  label=${pair%%=*}; job=${pair#*=}
  while true; do
    st=$(curl -s -H "Authorization: Bearer $OS_KEY" "$OS_URL/api/v1/jobs/$job/status" | python3 -I -c "import json,sys; print(json.load(sys.stdin).get('status'))")
    case "$st" in completed|failed|cancelled|error) break;; esac
    sleep 60
  done
  out="$MA/runs/$label"; mkdir -p "$out"
  curl -s -H "Authorization: Bearer $OS_KEY" "$OS_URL/api/v1/jobs/$job/report" -o "$out/final_report.pdf"
  curl -s -H "Authorization: Bearer $OS_KEY" "$OS_URL/api/v1/jobs/$job/artifacts" -o "$out/artifacts.zip" \
    && (cd "$out" && mkdir -p artifacts && unzip -q -o artifacts.zip -d artifacts)
  printf "%s\t%s\t%s\t%s\t%s\n" "$label" "$job" "$st" "$(date -Iseconds)" "$(usage)" >> "$LOG"
  echo "$label $st"
done
