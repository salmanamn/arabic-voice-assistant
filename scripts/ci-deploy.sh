#!/usr/bin/env bash
# Dispatch deploy.yml from the laptop, show the plan, approve the `azure` environment, follow the run (D49).
# Same flow as Project 3's ci-deploy.sh.
#
# Usage: scripts/ci-deploy.sh apply | destroy | deploy-chart [CI_RUN_ID]
#   apply          the whole stack: AKS, ACR, Azure OpenAI, roles, diagnostics
#   deploy-chart   CI's tested images -> ACR, the chart -> AKS, helm test + network flows (after apply)
#   destroy        everything, then checks that both resource groups are gone
set -euo pipefail

ACTION=${1:?usage: $0 apply | destroy | deploy-chart [CI_RUN_ID]}
IMAGES_RUN=${2:-}
[[ $ACTION =~ ^(apply|destroy|deploy-chart)$ ]] || { echo "unknown action $ACTION"; exit 2; }
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)

since=$(date -u -d "-60 sec" +%Y-%m-%dT%H:%M:%SZ) # tolerate a little clock skew vs GitHub
gh workflow run deploy.yml --ref main -f action="$ACTION" -f images_run="$IMAGES_RUN"
RUN_ID=""
for _ in $(seq 1 20); do
  sleep 3
  RUN_ID=$(gh run list --workflow deploy.yml --event workflow_dispatch --limit 5 --json databaseId,createdAt \
    --jq "[.[] | select(.createdAt >= \"$since\")][0].databaseId // empty")
  [[ -n $RUN_ID ]] && break
done
[[ -n $RUN_ID ]] || { echo "the dispatched run didn't show up"; exit 1; }
URL="https://github.com/$REPO/actions/runs/$RUN_ID"
echo "run: $URL ($ACTION)"

if [[ $ACTION != deploy-chart ]]; then
  job() { gh run view "$RUN_ID" --json jobs --jq ".jobs[] | select(.name==\"plan\") | .$1"; }
  until [[ $(job status) == completed ]]; do sleep 10; done
  # Job logs via API: available as soon as the job finishes, even while the run waits for approval.
  gh api "repos/$REPO/actions/jobs/$(job databaseId)/logs" | grep -E 'Plan:|No changes|tests,|^.{29}FAIL' | cut -c30- || true
  [[ $(job conclusion) == success ]] || { echo "plan failed: $URL"; exit 1; }
fi

for _ in $(seq 1 30); do
  [[ $(gh api "repos/$REPO/actions/runs/$RUN_ID/pending_deployments" --jq length) -gt 0 ]] && break
  if [[ $(gh run view "$RUN_ID" --json status --jq .status) == completed ]]; then
    echo "no changes, nothing to approve"
    exit 0
  fi
  sleep 5
done

read -rp "Approve $ACTION? [y/N] " ok
STATE=$([[ ${ok:-n} == y ]] && echo approved || echo rejected)
ENV_ID=$(gh api "repos/$REPO/environments/azure" --jq .id)
BODY=$(printf '{"environment_ids":[%s],"state":"%s","comment":"%s via ci-deploy.sh"}' "$ENV_ID" "$STATE" "$ACTION")
STATUS=$(gh api -X POST -i "repos/$REPO/actions/runs/$RUN_ID/pending_deployments" --input - <<<"$BODY" 2>&1 | head -n 1) || true
echo "approval POST: $STATUS"

sleep 3
RECORDED=$(gh api "repos/$REPO/actions/runs/$RUN_ID/approvals" --jq "[.[] | select(.state==\"$STATE\")] | length")
[[ $RECORDED -gt 0 ]] || { echo "approval not recorded; approve in the browser: $URL"; exit 1; }
echo "$STATE"

[[ $STATE == approved ]] && gh run watch "$RUN_ID" --exit-status --interval 15 >/dev/null && echo "run succeeded: $URL"
