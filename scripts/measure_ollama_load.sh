#!/bin/bash
# How long Ollama takes to load the chat model from a fresh container, and whether its memory limit slows that down
# (M5 Step 0, D25). Run on a freshly started WSL, before the model has been loaded by anything:
#   ./scripts/measure_ollama_load.sh [model] | tee docs/evidence/m5-ollama-load.md
# Three loads, each in a recreated container: with compose's limit (the model file not yet in the host's page cache
# after a WSL restart, so read from disk), with the limit again (file cached by the host), and with an 8 GiB limit
# (cached). The last two differ only in the limit. Each line: seconds until /api/generate returned, the cgroup's
# peak memory, and how much of it was file cache (the mmap'd model) and process memory at the end. Ends with the
# stack's own limit in place and the model loaded. Waits silently while a model loads (up to 5 minutes each).
set -euo pipefail
model=${1:-phi4-mini:3.8b}
override=$(mktemp --suffix=.yml)
trap 'rm -f "$override"' EXIT
printf 'services:\n  ollama:\n    mem_limit: 8g\n    memswap_limit: 8g\n' >"$override"

load() { # LABEL COMPOSE-ARGS...: recreate Ollama, time one load, print one Markdown row
  local label=$1
  shift
  docker compose "$@" up -d --force-recreate --no-deps ollama >/dev/null 2>&1
  until curl -sf http://127.0.0.1:11434/api/version >/dev/null; do sleep 1; done
  local start end
  start=$(date +%s.%N)
  curl -sf --max-time 600 http://127.0.0.1:11434/api/generate -d "{\"model\":\"$model\",\"keep_alive\":-1,\"stream\":false}" >/dev/null
  end=$(date +%s.%N)
  # cgroup v2 (Docker Desktop): memory.peak and memory.stat; cgroup v1: max_usage_in_bytes and total_cache/total_rss
  read -r peak file anon < <(docker exec voice-ollama sh -c '
    if [ -f /sys/fs/cgroup/memory.peak ]; then
      p=$(cat /sys/fs/cgroup/memory.peak); s=/sys/fs/cgroup/memory.stat; f=file; a=anon
    else
      p=$(cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes); s=/sys/fs/cgroup/memory/memory.stat; f=total_cache; a=total_rss
    fi
    echo "$p $(awk -v k=$f "\$1==k{print \$2}" $s) $(awk -v k=$a "\$1==k{print \$2}" $s)"')
  local limit
  limit=$(docker inspect -f '{{.HostConfig.Memory}}' voice-ollama)
  printf '| %s | %d | %.1f | %d | %d | %d |\n' "$label" $((limit / 1048576)) "$(echo "$end - $start" | bc)" \
    $((peak / 1048576)) $((file / 1048576)) $((anon / 1048576))
}

echo "# Ollama cold load (M5, D25)"
echo
echo "\`$model\`, $(date -u '+%Y-%m-%d %H:%M UTC'), \`scripts/measure_ollama_load.sh\`."
echo
echo "| Run | Limit MiB | Load s | Peak MiB | File cache MiB | Process MiB |"
echo "|---|---|---|---|---|---|"
load "1: compose limit, model file not cached"
load "2: compose limit, model file cached"
load "3: 8 GiB limit, model file cached" -f docker-compose.yml -f "$override"
docker compose up -d --force-recreate --no-deps ollama >/dev/null 2>&1
until curl -sf http://127.0.0.1:11434/api/version >/dev/null; do sleep 1; done
curl -sf --max-time 600 http://127.0.0.1:11434/api/generate -d "{\"model\":\"$model\",\"keep_alive\":-1,\"stream\":false}" >/dev/null
echo
echo "Ollama is back on the compose limit with the model loaded."