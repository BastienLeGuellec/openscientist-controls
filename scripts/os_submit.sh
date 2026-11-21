#!/usr/bin/env bash
# Submit one OpenScientist job with the case study 3 prompt, as in the authors' benchmark
# (10 iterations, autonomous, hypothesis tracking off).
# Usage: os_submit.sh <data.h5ad> <label>     (needs OS_KEY=name:secret, OS_URL default http://localhost:8081)
set -euo pipefail
DATA=$1
LABEL=$2
OS_URL=${OS_URL:-http://localhost:8081}
HERE=$(cd "$(dirname "$0")" && pwd)
PROMPT_FILE=${PROMPT_FILE:-$HERE/../zenodo/cs3_online30/bourdenx-benchmark-2026-08-14/PROMPT.txt}
echo "prompt sha256 $(sha256sum "$PROMPT_FILE" | cut -c1-16)…  data md5 $(md5sum "$DATA" | cut -d' ' -f1)" >&2
curl -sS --fail-with-body -X POST "$OS_URL/api/v1/jobs" \
  -H "Authorization: Bearer $OS_KEY" \
  -F "research_question=<$PROMPT_FILE" \
  --form-string "max_iterations=10" \
  --form-string "use_hypotheses=false" \
  --form-string "investigation_mode=autonomous" \
  --form-string "short_title=$LABEL" \
  -F "data_files=@$DATA"
echo
