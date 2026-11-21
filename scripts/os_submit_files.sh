#!/usr/bin/env bash
# Submit one OpenScientist job with the benchmark settings (10 iterations, autonomous, no hypothesis tracking).
# Usage: os_submit_files.sh <label> <prompt.txt> <data file> [<data file> ...]
# Needs the API key in ../.os_key (written by run0.sh); OS_URL defaults to http://localhost:8081.
set -euo pipefail
LABEL=$1; PROMPT=$2; shift 2
HERE=$(cd "$(dirname "$0")" && pwd)
OS_URL=${OS_URL:-http://localhost:8081}
OS_KEY=$(cat "$HERE/../.os_key")
args=()
# a file may be given as path::upload_name, so that OpenScientist sees upload_name (e.g. a shuffled copy
# uploaded under the original file name)
names=()
for f in "$@"; do
  path=${f%%::*}; name=$(basename "$path"); [[ "$f" == *::* ]] && name=${f#*::}
  args+=(-F "data_files=@$path;filename=$name"); names+=("$name")
done
echo "$LABEL: prompt sha256 $(sha256sum "$PROMPT" | cut -c1-16), $# files: ${names[*]}" >&2
curl -sS --fail-with-body -X POST "$OS_URL/api/v1/jobs" \
  -H "Authorization: Bearer $OS_KEY" \
  -F "research_question=<$PROMPT" \
  --form-string "max_iterations=10" \
  --form-string "use_hypotheses=false" \
  --form-string "investigation_mode=autonomous" \
  --form-string "short_title=$LABEL" \
  "${args[@]}"
echo
