#!/bin/bash
# The stt autoscaler under load (M5 Step 4, D28): switch the chart's load test on, watch the HPA scale stt up while
# it runs and back down after it, switch it off, and write the evidence.
#   ./scripts/hpa_demo.sh [namespace] [release] > docs/evidence/m5-hpa.md
# About 8 minutes: up to 1 for the load test pod, 4 of load, up to 3 for the scale-down. Prints progress on stderr.
set -euo pipefail
ns=${1:-voice}
release=${2:-voice}
chart=$(dirname "$0")/../deploy/charts/voice
watch_file=$(mktemp)
trap 'kill "$watcher" 2>/dev/null || true; rm -f "$watch_file"' EXIT

kubectl -n "$ns" get hpa stt --watch --output-watch-events=false >"$watch_file" 2>&1 &
watcher=$!
echo "load test on" >&2
helm upgrade "$release" "$chart" -n "$ns" --reuse-values --set loadtest.enabled=true >/dev/null
kubectl -n "$ns" wait --for=condition=complete job/loadtest --timeout=10m >/dev/null
echo "load test done; waiting for stt to scale back to 1" >&2
for _ in $(seq 60); do
  [[ $(kubectl -n "$ns" get deploy stt -o jsonpath='{.status.replicas}') == 1 ]] && break
  sleep 5
done
sleep 15 # one more HPA period in the watch
load_log=$(kubectl -n "$ns" logs job/loadtest)
events=$(kubectl -n "$ns" get events --field-selector involvedObject.kind=HorizontalPodAutoscaler,reason=SuccessfulRescale \
  -o custom-columns=TIME:.lastTimestamp,MESSAGE:.message --no-headers)
helm upgrade "$release" "$chart" -n "$ns" --reuse-values --set loadtest.enabled=false >/dev/null
echo "load test off" >&2

cat <<MARKDOWN
# The stt autoscaler under load (M5, D28)

$(date -u '+%Y-%m-%d %H:%M UTC'), \`scripts/hpa_demo.sh\`: the chart's load test (\`loadtest.enabled=true\`) against
\`stt\`, CPU request $(kubectl -n "$ns" get deploy stt -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}'), target $(kubectl -n "$ns" get hpa stt -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}') %, replicas $(kubectl -n "$ns" get hpa stt -o jsonpath='{.spec.minReplicas}')–$(kubectl -n "$ns" get hpa stt -o jsonpath='{.spec.maxReplicas}').

The HPA, as \`kubectl get hpa stt --watch\` printed it (one line per change):
\`\`\`
$(cat "$watch_file")
\`\`\`

Rescale events:
\`\`\`
$events
\`\`\`

The load test (calls completed per 15 s window, \`503 busy\`, other errors, median time per call):
\`\`\`
$load_log
\`\`\`
MARKDOWN