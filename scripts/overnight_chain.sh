#!/usr/bin/env bash
# Overnight queue, one OpenScientist job at a time:
#  1. wait for the Opus 4.8 real-label run (job in runs/opus_jobs.txt)
#  2. Opus 4.8 on shuffled seeds 1-3, each only if the previous Opus run cost <= $25 and Opus total <= $100
#  3. switch the app to GLM 5.2 and run the three planted-effect copies (positive control)
# Every step is logged to runs/overnight.log; costs from the OpenRouter balance before and after each run.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); MA=$(cd "$HERE/.." && pwd); cd "$MA"
LOG=runs/overnight.log
OS_URL=http://localhost:8081
ORK=$(grep -E "^OPENROUTER_API_KEY=" ../.env | head -1 | cut -d= -f2- | tr -d "\"' ")
PROMPT=zenodo/cs3_online30/bourdenx-benchmark-2026-08-14/PROMPT.txt
usage() { curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $ORK" | python3 -I -c "import json,sys; print(json.load(sys.stdin)['data']['usage'])"; }
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
status() { curl -s -H "Authorization: Bearer $(cat .os_key)" "$OS_URL/api/v1/jobs/$1/status" | python3 -I -c "import json,sys; print(json.load(sys.stdin).get('status'))"; }
wait_job() { while true; do s=$(status "$1"); case "$s" in completed|failed|cancelled|error) echo "$s"; return;; esac; sleep 60; done; }
run_job() {  # label, data path (uploaded as the original file name); echoes cost
  local label=$1 data=$2 u0 u1 j st
  u0=$(usage)
  j=$(scripts/os_submit_files.sh "$label" "$PROMPT" "$data::OteroGarcia_excitatory_subset.h5ad" 2>>"$LOG" | python3 -I -c "import json,sys; print(json.load(sys.stdin)['id'])")
  log "submitted $label job $j"
  st=$(wait_job "$j")
  scripts/os_collect.sh "$label=$j" >> "$LOG" 2>&1
  u1=$(usage)
  local cost; cost=$(python3 -c "print(round($u1-$u0,2))")
  log "$label $st cost \$$cost"
  printf "%s\t%s\t%s\t%s\n" "$label" "$j" "$st" "$cost" >> runs/run_costs.tsv
  echo "$cost"
}

# 1. Opus real-label run already submitted
J0=$(cut -d= -f2 runs/opus_jobs.txt)
log "waiting for opus_cs3_original ($J0)"
U_START=$(grep -P "^opus_start2\t" runs/collect_log.tsv | cut -f5)
st=$(wait_job "$J0"); sleep 90   # let its collector finish
U_NOW=$(usage)
C0=$(python3 -c "print(round($U_NOW-$U_START,2))")
log "opus_cs3_original $st, cost about \$$C0 (includes small audit calls)"
printf "opus_cs3_original\t%s\t%s\t%s\n" "$J0" "$st" "$C0" >> runs/run_costs.tsv

# 2. Opus shuffled runs under the cost rule
TOTAL=$C0; LAST=$C0
for s in 1 2 3; do
  if python3 -c "import sys; sys.exit(0 if ($LAST <= 25 and $TOTAL + $LAST <= 100) else 1)"; then
    c=$(run_job "opus_null_s$s" "data/null_seed$s.h5ad" | tail -1)
    LAST=$c; TOTAL=$(python3 -c "print($TOTAL+$c)")
  else
    log "skipping opus_null_s$s: last run \$$LAST, Opus total \$$TOTAL (rule: <= \$25 per run, <= \$100 total)"
    break
  fi
done
log "Opus total about \$$TOTAL"

# 3. back to GLM 5.2 for the planted-effect runs
cd os_bench && cp .env.glm .env && docker compose up -d openscientist >> "../$LOG" 2>&1
until curl -s -o /dev/null -w "%{http_code}" "$OS_URL/" | grep -q -E "^(200|302|307)$"; do sleep 3; done
PU=$(grep -E "^POSTGRES_USER=" .env | cut -d= -f2-); PD=$(grep -E "^POSTGRES_DB=" .env | cut -d= -f2-)
NS=$(docker compose exec -T postgres psql -U "$PU" -d "$PD" -At -c "select count(*) from skills where is_enabled")
MODEL=$(docker compose exec -T openscientist printenv OPENSCIENTIST_MODEL)
cd ..
log "switched app to $MODEL, enabled skills $NS"
if [ "$NS" != "10" ] || [ "$MODEL" != "z-ai/glm-5.2" ]; then log "unexpected configuration, stopping"; exit 1; fi
for s in 21 22 23; do run_job "glm_planted_s$s" "data/planted_seed$s.h5ad" > /dev/null; done
log "overnight queue done"
