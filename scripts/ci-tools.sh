#!/bin/bash
# Pinned tools for CI (D36), each checked against a SHA-256 before it is installed into ~/.local/bin.
#   ./scripts/ci-tools.sh helm conftest trivy k3s kubelogin
# Conftest's, Trivy's, k3s's and kubelogin's checksums are written here (taken from their GitHub releases); Helm publishes its
# binaries only on get.helm.sh, so its checksum file comes from there too (catches a broken download, not a
# compromised release; same caveat as D22). Bump a version: change it and its checksum together.
set -euo pipefail
HELM_VERSION=v4.3.2
CONFTEST_VERSION=0.71.1
CONFTEST_SHA256=c3f6b2a753bd56e377a1e51a95ae3e057f926f2e9139f7d5b5dfbbaf810f7985
TRIVY_VERSION=0.76.2
TRIVY_SHA256=bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf
K3S_VERSION=v1.36.6+k3s1
K3S_SHA256=66ceb8e67edfa547195135d74783bfadc2ecc04a91059e90ae5f70a3dbc98c15
KUBELOGIN_VERSION=v0.2.22 # Entra ID sign-in for kubectl on AKS (local accounts are off, D41)
KUBELOGIN_SHA256=716cbcb1880bca8f0e976b8917d06fcfe04de2c1e737eaaabbb26e2782330119

bin=${CI_TOOLS_BIN:-$HOME/.local/bin}
mkdir -p "$bin"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

fetch() { # URL SHA256 FILE
  curl -fsSL --retry 5 --retry-all-errors -o "$work/$3" "$1"
  echo "$2  $work/$3" | sha256sum -c --quiet -
}

for tool in "$@"; do
  case $tool in
    helm)
      file=helm-$HELM_VERSION-linux-amd64.tar.gz
      sum=$(curl -fsSL --retry 5 "https://get.helm.sh/$file.sha256sum" | awk '{print $1}')
      fetch "https://get.helm.sh/$file" "$sum" "$file"
      tar -xzf "$work/$file" -C "$work" linux-amd64/helm && install -m 0755 "$work/linux-amd64/helm" "$bin/helm"
      ;;
    conftest)
      file=conftest_${CONFTEST_VERSION}_Linux_x86_64.tar.gz
      fetch "https://github.com/open-policy-agent/conftest/releases/download/v$CONFTEST_VERSION/$file" "$CONFTEST_SHA256" "$file"
      tar -xzf "$work/$file" -C "$work" conftest && install -m 0755 "$work/conftest" "$bin/conftest"
      ;;
    trivy)
      file=trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz
      fetch "https://github.com/aquasecurity/trivy/releases/download/v$TRIVY_VERSION/$file" "$TRIVY_SHA256" "$file"
      tar -xzf "$work/$file" -C "$work" trivy && install -m 0755 "$work/trivy" "$bin/trivy"
      ;;
    k3s)
      fetch "https://github.com/k3s-io/k3s/releases/download/${K3S_VERSION//+/%2B}/k3s" "$K3S_SHA256" k3s
      install -m 0755 "$work/k3s" "$bin/k3s"
      ;;
    kubelogin)
      fetch "https://github.com/Azure/kubelogin/releases/download/$KUBELOGIN_VERSION/kubelogin-linux-amd64.zip" "$KUBELOGIN_SHA256" kubelogin.zip
      unzip -q -j "$work/kubelogin.zip" bin/linux_amd64/kubelogin -d "$work" && install -m 0755 "$work/kubelogin" "$bin/kubelogin"
      ;;
    *)
      echo "unknown tool: $tool" >&2
      exit 2
      ;;
  esac
  echo "installed $tool: $bin/$tool"
done
