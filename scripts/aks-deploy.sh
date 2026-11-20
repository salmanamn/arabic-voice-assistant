#!/usr/bin/env bash
# The chart on AKS (D38, D49). deploy.yml's deploy-chart job runs these in order; on the laptop (az login as yourself)
# `credentials`, `test` and `logs` work too: your operator role is AKS RBAC Admin on the voice namespace (D46).
#
#   ./scripts/aks-deploy.sh settings           read the chart settings from Terraform's output (remote state)
#   ./scripts/aks-deploy.sh images [RUN_ID]    stt/tts: CI artifact of that ci.yml run (default: the last green main
#                                              push) -> ACR; gateway/models: az acr import from GHCR by digest
#   ./scripts/aks-deploy.sh credentials        kubeconfig for the cluster, converted to Entra sign-in (kubelogin)
#   ./scripts/aks-deploy.sh install            namespace (restricted PSS) + helm upgrade --install --wait
#   ./scripts/aks-deploy.sh test               helm test (one spoken turn, real Azure OpenAI) + every network flow
#   ./scripts/aks-deploy.sh logs               pods, events and logs, for a failed step
#
# Needs az (signed in), terraform (envs/azure initialised with its backend), jq, helm, kubectl, kubelogin, python3;
# `images` also needs docker and gh (GH_TOKEN with actions:read and packages:read).
set -euo pipefail
cd "$(dirname "$0")/.."

WORK=${RUNNER_TEMP:-$HOME/.cache}/voice-aks # laptop: under ~, which a WSL restart keeps (/tmp it clears)
SETTINGS=$WORK/settings.json
RUN_VALUES=$WORK/azure-run.yaml # what this script adds to deploy/azure-values.yaml (shape: deploy/policy/fixtures)
OWNER=${GHCR_OWNER:-salmanamn}
mkdir -p "$WORK"

setting() { jq -er ".$1" "$SETTINGS"; }

settings() {
  terraform -chdir=infra/envs/azure output -json summary | jq '.chart_settings' >"$SETTINGS"
  [[ -n $(setting cluster) && -n $(setting openai_endpoint) ]] || { echo "FAIL the stack is not up (no cluster or OpenAI in the output)"; exit 1; }
  jq -r 'to_entries[] | "OK   \(.key): \(.value)"' "$SETTINGS"
}

images() {
  local run=${1:-} sha short registry name i digest
  if [[ -z $run ]]; then
    run=$(gh run list --workflow ci.yml --branch main --event push --status success --limit 1 --json databaseId --jq '.[0].databaseId')
  fi
  sha=$(gh run view "$run" --json headSha --jq .headSha)
  short=${sha::12}
  registry=$(setting registry)
  name=$(setting registry_name)
  echo "OK   images of ci.yml run $run (main @ $short)"

  # stt and tts: the bytes CI tested (k3s e2e), never published anywhere public (D23, D38).
  gh run download "$run" --name images --dir "$WORK"
  zstd -dc "$WORK/images.tar.zst" | docker load -q
  az acr login --name "$name" --output none
  for i in stt tts; do
    docker tag "voice-$i:ci" "$registry/voice-$i:sha-$short"
    docker push -q "$registry/voice-$i:sha-$short" >/dev/null
  done

  # gateway and models: what ci.yml's publish job pushed to GHCR, copied by digest (a tag can move; a digest can't).
  echo "$GH_TOKEN" | docker login ghcr.io -u "$OWNER" --password-stdin >/dev/null
  for i in gateway models; do
    digest=$(docker buildx imagetools inspect "ghcr.io/$OWNER/voice-$i:sha-$short" --format '{{.Manifest.Digest}}')
    az acr import --name "$name" --source "ghcr.io/$OWNER/voice-$i@$digest" --image "voice-$i:sha-$short" \
      --username "$OWNER" --password "$GH_TOKEN" --force --output none
  done
  docker logout ghcr.io >/dev/null

  {
    echo "images:"
    echo "  registry: $registry"
    echo "  digests:"
    for i in stt tts gateway models; do
      digest=$(az acr repository show --name "$name" --image "voice-$i:sha-$short" --query digest -o tsv)
      echo "    $i: $digest"
      echo "OK   $registry/voice-$i@$digest (sha-$short)" >&2
    done
    echo "azureOpenAI:"
    echo "  endpoint: $(setting openai_endpoint)"
    echo "  deployment: $(setting chat_deployment)"
    echo "  clientId: $(setting gateway_client_id)"
    # The optional Azure AI Speech account (D59): the gateway may reach it; stt/tts stay on the pods until switched.
    if [[ -n $(jq -r '.speech_resource_id // ""' "$SETTINGS") ]]; then
      echo "azureSpeech:"
      echo "  enabled: true"
      echo "  resourceId: $(setting speech_resource_id)"
      echo "  region: $(setting speech_region)"
    fi
  } >"$RUN_VALUES"
}

credentials() {
  az aks get-credentials --resource-group "$(setting resource_group)" --name "$(setting cluster)" --overwrite-existing --only-show-errors
  kubelogin convert-kubeconfig -l azurecli # Entra token from the az CLI's sign-in (local accounts are off, D41)
  kubectl auth whoami
  # Nodes are cluster-scoped: CI's deployer (cluster admin) sees them, the operator's namespace role doesn't (D46, D52).
  kubectl get nodes -o wide 2>/dev/null || echo "OK   nodes not visible to this identity (role scoped to namespace $(setting namespace))"
}

install() {
  [[ -f $RUN_VALUES ]] || { echo "FAIL run './scripts/aks-deploy.sh images' first"; exit 1; }
  kubectl apply -f deploy/namespace.yaml
  helm upgrade --install voice deploy/charts/voice -n "$(setting namespace)" \
    -f deploy/azure-values.yaml -f "$RUN_VALUES" --wait --timeout 25m
  kubectl -n "$(setting namespace)" get pods,jobs,pvc
  # What the one node has left (D42): requests of every pod, ours and the cluster's. Cluster admin only (CI).
  kubectl describe nodes 2>/dev/null | sed -n '/^Allocated resources:/,/^Events:/p' || true
}

test_() {
  local ns host region speech=()
  ns=$(setting namespace)
  host=$(setting openai_endpoint | sed -E 's|^https://([^/]+)/.*|\1|')
  region=$(jq -r '.speech_region // ""' "$SETTINGS")
  [[ -n $region ]] && speech=(--speech-host "$region.stt.speech.microsoft.com" --speech-host "$region.tts.speech.microsoft.com")
  helm test voice -n "$ns" --logs --timeout 10m
  python3 scripts/check_netpol.py --namespace "$ns" --egress fqdn --chat-host "$host" "${speech[@]}" --evidence "$WORK/netpol.md"
}

logs() {
  local ns pod
  ns=$(setting namespace)
  kubectl -n "$ns" get pods,jobs,events -o wide || true
  for pod in $(kubectl -n "$ns" get pods -o name 2>/dev/null); do
    echo "::group::$pod"
    kubectl -n "$ns" describe "$pod" | tail -25 || true
    kubectl -n "$ns" logs "$pod" --all-containers --tail=50 || true
    echo "::endgroup::"
  done
}

case ${1:-} in
  settings) settings ;;
  images) images "${2:-}" ;;
  credentials) credentials ;;
  install) install ;;
  test) test_ ;;
  logs) logs ;;
  *) echo "usage: $0 settings | images [RUN_ID] | credentials | install | test | logs" >&2; exit 2 ;;
esac