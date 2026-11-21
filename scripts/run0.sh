#!/usr/bin/env bash
# Run 0: OpenScientist on the original case study 3 data with the authors' prompt and GLM 5.2 settings,
# to check our rebuilt stack against their 10 GLM 5.2 benchmark runs.
# Starts the stack, creates an API key for the dev-mode admin user, submits the job, prints the job id.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MA=$(cd "$HERE/.." && pwd)
cd "$MA/os_bench"
OS_URL=${OS_URL:-http://localhost:8081}

make start
echo "waiting for the web app on $OS_URL ..." >&2
for i in $(seq 1 90); do
  curl -s -o /dev/null -w "%{http_code}" "$OS_URL/" | grep -q -E "^(200|302|307)$" && break
  sleep 5
done
# upstream init.sql gives openscientist_admin the default dev password, while the app connects with
# POSTGRES_PASSWORD: align them, then create the schema (both steps are idempotent)
PW=$(grep -E "^POSTGRES_PASSWORD=" .env | cut -d= -f2-); PU=$(grep -E "^POSTGRES_USER=" .env | cut -d= -f2-)
PD=$(grep -E "^POSTGRES_DB=" .env | cut -d= -f2-)
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -q -U "$PU" -d "$PD" -c "ALTER ROLE openscientist_admin PASSWORD '$PW';"
docker compose exec -T openscientist alembic upgrade head
# skills: the authors' 30 benchmark runs show only the 10 built-in skills. A fresh database gets them from
# the startup sync, which must run after the migrations; the remote K-Dense source stays disabled.
Q() { docker compose exec -T postgres psql -U "$PU" -d "$PD" -At -c "$1"; }
if [ "$(Q "select count(*) from skills where is_enabled")" != "10" ]; then
  docker compose restart openscientist >/dev/null
  for i in $(seq 1 60); do [ "$(Q "select count(*) from skills where is_enabled")" = "10" ] && break; sleep 3; done
fi
Q "update skill_sources set is_enabled=false where source_type='github';" >/dev/null
N=$(Q "select count(*) from skills where is_enabled")
[ "$N" = "10" ] || { echo "expected the 10 built-in skills, found $N enabled; not submitting" >&2; exit 1; }
for i in $(seq 1 60); do curl -s -o /dev/null -w "%{http_code}" "$OS_URL/" | grep -q -E "^(200|302|307)$" && break; sleep 2; done
curl -s -o /dev/null "$OS_URL/auth/mock/admin-login"
WEB=$(docker compose ps -q openscientist)
OS_KEY=$(docker exec -i "$WEB" python - < "$HERE/os_make_key.py" | tail -1)
echo "$OS_KEY" > "$MA/.os_key" && chmod 600 "$MA/.os_key"

KEY=$(grep -E "^OPENROUTER_API_KEY=" "$MA/../.env" | head -1 | cut -d= -f2- | tr -d "\"' ")
curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $KEY" \
  | python3 -I -c "import json,sys,datetime; d=json.load(sys.stdin)['data']; print(datetime.datetime.now().isoformat(timespec='seconds'), 'usage', d.get('usage'))" \
  >> "$MA/openrouter_usage_log.txt"

DATA="$MA/zenodo/cs3_main/job_a66ae54c/data/OteroGarcia_excitatory_subset.h5ad"
OS_KEY="$OS_KEY" OS_URL="$OS_URL" "$HERE/os_submit.sh" "$DATA" run0_cs3_original | tee "$MA/run0_submit.json"
