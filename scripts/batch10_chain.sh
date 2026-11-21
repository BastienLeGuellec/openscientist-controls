#!/usr/bin/env bash
# Shuffled-label runs to reach 10 per model: GLM 5.2, then Opus 4.8, on the same shuffled copies (seeds 4-10).
# One OpenScientist job at a time. Guards: stop if a run costs more than $15, if the next run could take the batch
# past $100, if free disk falls below 4 GB, or if a job runs longer than 4 h. A run that ends failed or cancelled is
# logged to runs/failed_attempts.tsv and resubmitted once (label suffix b). After collection, the data copy in
# runs/<label>/artifacts/data is replaced by a hard link to the identical input file in data/ (checked with cmp).
# Log: runs/batch10.log; costs (OpenRouter usage before and after each run): runs/run_costs.tsv.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); MA=$(cd "$HERE/.." && pwd); cd "$MA"
LOG=runs/batch10.log
OS_URL=http://localhost:8081
ORK=$(grep -E "^OPENROUTER_API_KEY=" ../.env | head -1 | cut -d= -f2- | tr -d "\"' ")
PROMPT=zenodo/cs3_online30/bourdenx-benchmark-2026-08-14/PROMPT.txt
SEEDS="4 5 6 7 8 9 10"
MAX_RUN=15; MAX_TOTAL=100; MIN_DISK_GB=4; MAX_WAIT_MIN=240
TOTAL=0

usage() { curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $ORK" | python3 -I -c "import json,sys; print(json.load(sys.stdin)['data']['usage'])"; }
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
stop() { log "STOP: $*; batch total \$$TOTAL"; exit 1; }
status() { curl -s -H "Authorization: Bearer $(cat .os_key)" "$OS_URL/api/v1/jobs/$1/status" | python3 -I -c "import json,sys; print(json.load(sys.stdin).get('status'))" 2>/dev/null; }
free_gb() { df -BG --output=avail "$MA" | tail -1 | tr -dc 0-9; }
le() { python3 -I -c "import sys; sys.exit(0 if $1 <= $2 else 1)"; }

wait_job() {  # sets JOB_STATUS
  local n=0
  while true; do
    JOB_STATUS=$(status "$1")
    case "$JOB_STATUS" in completed|failed|cancelled|error) return;; esac
    n=$((n + 1)); [ "$n" -le "$MAX_WAIT_MIN" ] || stop "job $1 still '$JOB_STATUS' after $MAX_WAIT_MIN min"
    sleep 60
  done
}

configure() {  # env file, expected model
  (cd os_bench && cp "$1" .env && docker compose up -d openscientist) >> "$LOG" 2>&1
  until curl -s -o /dev/null -w "%{http_code}" "$OS_URL/" | grep -q -E "^(200|302|307)$"; do sleep 3; done
  local pu pd ns model
  pu=$(grep -E "^POSTGRES_USER=" os_bench/.env | cut -d= -f2-); pd=$(grep -E "^POSTGRES_DB=" os_bench/.env | cut -d= -f2-)
  ns=$(cd os_bench && docker compose exec -T postgres psql -U "$pu" -d "$pd" -At -c "select count(*) from skills where is_enabled")
  model=$(cd os_bench && docker compose exec -T openscientist printenv OPENSCIENTIST_MODEL)
  log "app on $model, enabled skills $ns"
  [ "$ns" = "10" ] && [ "$model" = "$2" ] || stop "unexpected configuration (wanted $2)"
}

run_one() {  # label, data file; sets RUN_STATUS RUN_COST RUN_JOB
  local label=$1 data=$2 u0 u1 f
  u0=$(usage)
  RUN_JOB=$(scripts/os_submit_files.sh "$label" "$PROMPT" "$data::OteroGarcia_excitatory_subset.h5ad" 2>>"$LOG" \
            | python3 -I -c "import json,sys; print(json.load(sys.stdin)['id'])")
  [ -n "$RUN_JOB" ] || stop "submission failed for $label"
  log "submitted $label job $RUN_JOB"
  wait_job "$RUN_JOB"; RUN_STATUS=$JOB_STATUS
  scripts/os_collect.sh "$label=$RUN_JOB" >> "$LOG" 2>&1
  u1=$(usage)
  RUN_COST=$(python3 -I -c "print(round($u1-$u0,2))")
  TOTAL=$(python3 -I -c "print(round($TOTAL+$RUN_COST,2))")
  log "$label $RUN_STATUS cost \$$RUN_COST, batch total \$$TOTAL"
  printf "%s\t%s\t%s\t%s\n" "$label" "$RUN_JOB" "$RUN_STATUS" "$RUN_COST" >> runs/run_costs.tsv
  f=runs/$label/artifacts/data/OteroGarcia_excitatory_subset.h5ad
  if [ -f "$f" ] && cmp -s "$f" "$data"; then ln -f "$data" "$f"; fi
  le "$RUN_COST" "$MAX_RUN" || stop "$label cost \$$RUN_COST, above \$$MAX_RUN"
}

run_seed() {  # label, data file, expected cost of one run
  local label=$1 data=$2 expected=$3
  [ "$(free_gb)" -ge "$MIN_DISK_GB" ] || stop "free disk below $MIN_DISK_GB GB"
  le "$TOTAL + $expected" "$MAX_TOTAL" || stop "next run $label could take the batch past \$$MAX_TOTAL"
  run_one "$label" "$data"
  if [ "$RUN_STATUS" != "completed" ]; then
    printf "%s\t%s\t%s\t%s\t%s\n" "$label" "$RUN_JOB" "$RUN_STATUS" "$(date -Iseconds)" "resubmitted as ${label}b by batch10_chain.sh" >> runs/failed_attempts.tsv
    le "$TOTAL + $expected" "$MAX_TOTAL" || stop "resubmission of $label could take the batch past \$$MAX_TOTAL"
    run_one "${label}b" "$data"
    [ "$RUN_STATUS" = "completed" ] || log "$label failed twice, moving on"
  fi
}

log "batch start, free disk $(free_gb) GB"
configure .env.glm z-ai/glm-5.2
for s in $SEEDS; do run_seed "ma1_null_s$s" "data/null_seed$s.h5ad" 5; done
configure .env.opus claude-opus-4-8
for s in $SEEDS; do run_seed "opus_null_s$s" "data/null_seed$s.h5ad" 10; done
configure .env.glm z-ai/glm-5.2
log "batch done, total \$$TOTAL"
