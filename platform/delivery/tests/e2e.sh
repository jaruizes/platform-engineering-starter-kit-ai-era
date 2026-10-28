#!/usr/bin/env bash
# End-to-end test of delivery on a local platform (make up): a service created
# from the Spring service template, as an agent would with create_service, is
# built by its pipeline, deployed by Argo CD with its database, answers on
# its port, and a second push deploys again.
#
#   platform/delivery/tests/e2e.sh
#
# It renders the template itself, so it does not need the portal.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
GIT_URL="${GIT_URL:-http://localhost:3000}"
SERVICE=loyalty-points
ENVIRONMENT=checkout-e2e
NS="env-$ENVIRONMENT"

# Who commits, as an agent would.
export GIT_AUTHOR_NAME=e2e GIT_AUTHOR_EMAIL=e2e@starterkit.local
export GIT_COMMITTER_NAME=e2e GIT_COMMITTER_EMAIL=e2e@starterkit.local

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
secret() { kubectl -n platform-system get secret "$1" -o jsonpath="{.data.$2}" | base64 -d; }
admin="$(secret gitea-admin username):$(secret gitea-admin password)"
developer="$(secret gitea-developer username):$(secret gitea-developer password)"
work="$(mktemp -d)"
forward=""
trap 'rm -rf "$work"; [[ -n "$forward" ]] && kill "$forward" 2>/dev/null || true' EXIT

diagnose() {
  echo "::group::Diagnostics"
  kubectl -n argocd get applications -o wide || true
  kubectl -n argocd get application "$SERVICE" -o jsonpath='{.status.conditions}{"\n"}{.status.operationState.message}{"\n"}' || true
  kubectl -n "$NS" get apps.platform.starterkit.dev,postgresdatabases,pods,secrets -o wide || true
  kubectl -n "$NS" describe pods -l "app.kubernetes.io/name=$SERVICE" | sed -n '/^Events:/,$p' || true
  kubectl -n "$NS" logs -l "app.kubernetes.io/name=$SERVICE" --tail=50 || true
  kubectl -n platform-system logs deploy/platform-ci-runner --tail=30 || true
  echo "::endgroup::"
}

# Waits until the latest pipeline run is done; prints its log if it failed.
wait_for_pipeline() {
  local title="$1" run status
  for _ in $(seq 1 120); do
    run="$(curl -fsS "$GIT_URL/api/v1/repos/platform/$SERVICE/actions/tasks?limit=1" \
      | python3 -c 'import json,sys; r=(json.load(sys.stdin).get("workflow_runs") or [{}])[0]; print(r.get("status",""), r.get("id",""), r.get("display_title",""), sep="|")')"
    status="${run%%|*}"
    if [[ "$run" == *"|$title" && "$status" != running && "$status" != waiting && -n "$status" ]]; then
      echo "Pipeline: $status"
      if [[ "$status" != success ]]; then
        curl -fsS -u "$admin" "$GIT_URL/api/v1/repos/platform/$SERVICE/actions/jobs/$(echo "$run" | cut -d'|' -f2)/logs" \
          | grep -v "evaluat\|rewritten" | tail -80 || true
        exit 1
      fi
      return
    fi
    sleep 10
  done
  echo "The pipeline did not finish in 20 minutes." >&2
  exit 1
}

# Waits until Argo CD has deployed the image the pipeline built and the
# service is ready.
wait_for_deployment() {
  local image
  for _ in $(seq 1 90); do
    image="$(curl -fsS "$GIT_URL/platform/$SERVICE/raw/branch/main/deploy/app.yaml" | sed -n 's/^  image: //p')"
    if [[ -n "$image" && "$image" != '""' ]] \
      && [[ "$(kubectl -n "$NS" get apps.platform.starterkit.dev "$SERVICE" -o jsonpath='{.spec.image}' 2>/dev/null)" == "$image" ]] \
      && kubectl -n "$NS" rollout status "deployment/$SERVICE" --timeout=5s >/dev/null 2>&1 \
      && [[ "$(kubectl -n "$NS" get deployment "$SERVICE" -o jsonpath='{.spec.template.spec.containers[0].image}')" == "$image" ]]; then
      echo "Deployed $image"
      return
    fi
    sleep 10
  done
  echo "The service was not deployed in 15 minutes." >&2
  diagnose
  exit 1
}

step "Requesting environment $ENVIRONMENT"
kubectl apply -f - <<EOF
apiVersion: platform.starterkit.dev/v1alpha1
kind: Environment
metadata:
  name: $ENVIRONMENT
spec:
  team: checkout
  purpose: delivery end-to-end test
  size: small
  ttlHours: 2
EOF
kubectl wait "environment.platform.starterkit.dev/$ENVIRONMENT" --for=condition=Ready --timeout=180s

step "Creating $SERVICE from the Spring service template, as an agent"
python3 "$ROOT/platform/delivery/tests/render_skeleton.py" "$work/$SERVICE" name="$SERVICE" \
  description="Loyalty points of the customers" owner=group:default/checkout module=points \
  environment="$ENVIRONMENT" requestedBy=agent:e2e
curl -fsS -u "$admin" -H 'Content-Type: application/json' -o /dev/null \
  -d "{\"name\":\"$SERVICE\",\"default_branch\":\"main\"}" "$GIT_URL/api/v1/orgs/platform/repos"
remote="${GIT_URL/:\/\//://$developer@}/platform/$SERVICE.git"
git -C "$work/$SERVICE" init -q -b main
git -C "$work/$SERVICE" add -A
git -C "$work/$SERVICE" commit -qm "Create $SERVICE"
git -C "$work/$SERVICE" push -q "$remote" main

step "Waiting for the pipeline: tests, architecture rules and image"
wait_for_pipeline "Create $SERVICE"

step "Waiting for Argo CD to deploy it with its database"
wait_for_deployment

step "Calling the service"
kubectl -n "$NS" port-forward "svc/$SERVICE" 18080:80 >/dev/null 2>&1 &
forward=$!
sleep 3
health="$(curl -fsS --retry 5 --retry-delay 2 --retry-all-errors http://localhost:18080/actuator/health)"
echo "$health"
[[ "$health" == *'"status":"UP"'* ]]

step "Checking who is recorded as the requester"
annotations="$(kubectl -n "$NS" get apps.platform.starterkit.dev "$SERVICE" -o jsonpath='{.metadata.annotations}')"
echo "$annotations"
[[ "$annotations" == *'"platform.starterkit.dev/requested-by":"e2e"'* ]]
[[ "$annotations" == *'"platform.starterkit.dev/requester-type":"agent"'* ]]
[[ "$annotations" == *'"platform.starterkit.dev/delivered-by":"gitops"'* ]]

step "Asking the platform MCP server how the service is doing"
kubectl -n platform-system exec deploy/platform-mcp -- python -c "
import json
from platform_mcp import delivery, platform
platform.load_kube_config()
status = delivery.status('$SERVICE', '$ENVIRONMENT')
print(json.dumps({k: status[k] for k in ('state', 'pipeline', 'gitops', 'next_step')}, indent=2))
assert status['state'] == 'ready', status
"

step "Pushing a change: it is built and deployed again"
echo "Delivered by the platform." >> "$work/$SERVICE/README.md"
git -C "$work/$SERVICE" commit -qam "Change the README"
git -C "$work/$SERVICE" pull -q --rebase "$remote" main
git -C "$work/$SERVICE" push -q "$remote" main
wait_for_pipeline "Change the README"
wait_for_deployment

step "Delivery works end to end"
