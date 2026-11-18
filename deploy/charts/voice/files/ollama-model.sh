#!/bin/bash
# The chat model in Ollama, with bash and the ollama binary alone (the Ollama image has no curl and no Python).
# Used by the Helm chart (Job, init container, probes) and by docker-compose.yml (health check) (D25).
#
#   pull    Job: start a private server, pull CHAT_MODEL unless it is there, compare its id with MODEL_ID, and
#           leave the volume readable for a read-only server. The only writer of the Ollama models volume.
#   verify  init container: wait until CHAT_MODEL with id MODEL_ID is on the (read-only) volume.
#   load    startup probe / health check: load CHAT_MODEL and keep it in memory for good (keep_alive -1);
#           exit 0 once it is loaded. A cold load of a 2.5 GB model takes minutes on a laptop CPU.
#   check   readiness probe: exit 0 when CHAT_MODEL is in memory.
set -euo pipefail
model=${CHAT_MODEL:?CHAT_MODEL is not set}
api=127.0.0.1:11434

request() { # METHOD PATH BODY -> the raw response; one HTTP/1.0 request, so the server closes the connection
  exec 3<>"/dev/tcp/${api%:*}/${api#*:}"
  printf '%s %s HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s' \
    "$1" "$2" "${#3}" "$3" >&3
  cat <&3
}

progress() { # ollama's redrawn progress bar -> one line per layer per 10 %, other lines once each
  tr '\r' '\n' | sed -u 's/\x1b\[[0-9;?]*[A-Za-z]//g' | awk '
    match($0, /pulling [0-9a-f]+: +[0-9]+%/) {
      split(substr($0, RSTART, RLENGTH), f, /[: %]+/)
      if (!(f[2] in shown) || f[3] >= shown[f[2]] + 10 || (f[3] == 100 && shown[f[2]] < 100)) {
        shown[f[2]] = f[3]; print; fflush()
      }
      next
    }
    NF && $0 != last { print; fflush(); last = $0 }'
}

model_id() { # the 12-character id `ollama list` shows for CHAT_MODEL, or nothing
  ollama list 2>/dev/null | awk -v m="$model" '$1 == m { print $2 }'
}

start_server() { # a server of our own for pull/verify; stopped when the script exits
  OLLAMA_HOST=$api ollama serve >/tmp/ollama-serve.log 2>&1 &
  server=$!
  trap 'kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
  for _ in $(seq 60); do
    ollama list >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "FAIL ollama serve did not start:" >&2
  tail -5 /tmp/ollama-serve.log >&2
  exit 1
}

case "${1:-}" in
  pull)
    : "${MODEL_ID:?MODEL_ID is not set: the id of the model as \`ollama list\` shows it}"
    start_server
    if [[ -z $(model_id) ]]; then
      echo "pulling $model"
      ollama pull "$model" 2>&1 | progress || true
    fi
    got=$(model_id)
    if [[ $got != "$MODEL_ID" ]]; then
      echo "FAIL $model is ${got:-missing}, expected $MODEL_ID" >&2
      exit 1
    fi
    mkdir -p "${OLLAMA_MODELS:?}/manifests" # a read-only server still wants this directory to exist
    echo "OK   $model ($got) is on the volume"
    ;;
  verify)
    : "${MODEL_ID:?MODEL_ID is not set}"
    start_server
    until [[ $(model_id) == "$MODEL_ID" ]]; do
      echo "waiting for $model ($MODEL_ID) on the volume: the pull job writes it"
      sleep 10
    done
    echo "OK   $model ($MODEL_ID) is on the volume"
    ;;
  load | check)
    if [[ $1 == load ]]; then
      response=$(request POST /api/generate "{\"model\":\"$model\",\"keep_alive\":-1,\"stream\":false}")
      want='"done":true'
    else
      response=$(request GET /api/ps "")
      want="\"name\":\"$model\""
    fi
    status=${response%%$'\r'*}
    if [[ $status != *" 200 "* || $response != *"$want"* ]]; then
      echo "$1: $model is not loaded (${status:-no answer})" >&2
      exit 1
    fi
    ;;
  *)
    echo "usage: $0 pull|verify|load|check" >&2
    exit 2
    ;;
esac