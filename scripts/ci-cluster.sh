#!/bin/bash
# The cluster test in CI (D34): k3s on the runner, the workflow's own images, the chart with deploy/ci-values.yaml.
#   ./scripts/ci-cluster.sh up              start k3s (k3s from ./scripts/ci-tools.sh) and wait for the node
#   ./scripts/ci-cluster.sh load FILE       import images saved with `docker save | zstd` into k3s's containerd
#   ./scripts/ci-cluster.sh install [ARGS]  namespace (restricted PSS) + helm install --wait; ARGS go to helm
#   ./scripts/ci-cluster.sh test            helm test (one spoken turn) + every network flow (scripts/check_netpol.py)
#   ./scripts/ci-cluster.sh logs            what to look at when a step failed: pods, events, logs of each pod
# Needs sudo (k3s runs as root), helm, kubectl, zstd and python3 on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
ns=voice

case ${1:-} in
  up)
    # shellcheck disable=SC2024 # the log is the runner user's file, written by this shell
    sudo "$(command -v k3s)" server --disable=traefik --write-kubeconfig-mode=644 >/tmp/k3s.log 2>&1 &
    for _ in $(seq 90); do
      kubectl get nodes 2>/dev/null | grep -q ' Ready ' && break
      sleep 2
    done
    kubectl get nodes
    for _ in $(seq 60); do kubectl -n kube-system get deploy coredns >/dev/null 2>&1 && break; sleep 2; done # k3s creates it a few s after the node is Ready
    kubectl -n kube-system wait --for=condition=Available deploy/coredns --timeout=5m
    ;;
  load)
    zstd -dc "${2:?image archive}" | sudo "$(command -v k3s)" ctr -n k8s.io images import -
    sudo "$(command -v k3s)" ctr -n k8s.io images ls -q | grep -E '/voice-[a-z]+:'
    ;;
  install)
    shift
    kubectl apply -f deploy/namespace.yaml
    helm install voice deploy/charts/voice -n "$ns" -f deploy/ci-values.yaml --wait --timeout 15m "$@"
    kubectl -n "$ns" get pods,jobs
    ;;
  test)
    helm test voice -n "$ns" --logs --timeout 10m
    python3 scripts/check_netpol.py --namespace "$ns" --outside "${OUTSIDE:-1.1.1.1:443}"
    ;;
  logs)
    kubectl -n "$ns" get pods,jobs,events -o wide || true
    for pod in $(kubectl -n "$ns" get pods -o name 2>/dev/null); do
      echo "::group::$pod"
      kubectl -n "$ns" describe "$pod" | tail -25 || true
      kubectl -n "$ns" logs "$pod" --all-containers --tail=50 || true
      echo "::endgroup::"
    done
    tail -30 /tmp/k3s.log 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 up|load FILE|install [HELM ARGS]|test|logs" >&2
    exit 2
    ;;
esac