#!/usr/bin/env bash
# Puts the demo back to a clean state: no environments, services,
# capability requests, approvals, activity, repositories created from
# templates or proposed capabilities.
set -euo pipefail

echo "Deleting environments and services..."
kubectl delete apps.platform.starterkit.dev --all -A --wait=false >/dev/null 2>&1 || true
kubectl delete environments.platform.starterkit.dev --all --wait=false >/dev/null 2>&1 || true
for plural in $(kubectl get xrd -l platform.starterkit.dev/capability -o jsonpath='{.items[*].spec.names.plural}' 2>/dev/null); do
  kubectl delete "$plural.platform.starterkit.dev" --all -A --wait=false >/dev/null 2>&1 || true
done
kubectl -n platform-system delete configmap -l platform.starterkit.dev/approval-request >/dev/null 2>&1 || true
kubectl -n platform-system delete events --all >/dev/null 2>&1 || true

if kubectl -n platform-system get deployment gitea >/dev/null 2>&1; then
  echo "Deleting the repositories created from templates..."
  user="$(kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.username}' | base64 -d)"
  password="$(kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.password}' | base64 -d)"
  # On a laptop the Git server is at localhost:3000; elsewhere (AWS), through a port-forward.
  export GIT_URL="${GIT_URL:-http://localhost:3000}"
  if ! curl -fsS "$GIT_URL/api/healthz" >/dev/null 2>&1; then
    kubectl -n platform-system port-forward svc/gitea 13000:3000 >/dev/null 2>&1 &
    trap 'kill $! 2>/dev/null || true' EXIT
    export GIT_URL=http://localhost:13000
    for _ in $(seq 1 20); do curl -fsS "$GIT_URL/api/healthz" >/dev/null 2>&1 && break; sleep 1; done
  fi
  repos="$(curl -fsS -u "$user:$password" "$GIT_URL/api/v1/orgs/platform/repos?limit=50" \
    | grep -o '"full_name":"platform/[^"]*"' | cut -d'"' -f4)" || true
  for repo in $repos; do
    [[ "$repo" == platform/platform-starter-kit ]] && continue
    curl -fsS -X DELETE -u "$user:$password" "$GIT_URL/api/v1/repos/$repo" >/dev/null || true
  done
  echo "Starting the platform repository again (no proposed capabilities)..."
  "$(dirname "$0")/../../platform/delivery/git-server/seed-platform-repo.sh" --reset >/dev/null
fi

echo "Waiting for environments to be gone..."
for _ in $(seq 1 90); do
  if [[ -z "$(kubectl get environments.platform.starterkit.dev -o name 2>/dev/null)" ]] &&
     [[ -z "$(kubectl get namespaces -l platform.starterkit.dev/environment -o name 2>/dev/null)" ]]; then
    echo "Clean. Ready for the next demo."
    exit 0
  fi
  sleep 2
done
echo "Some environments are still being deleted; check 'kubectl get environments'." >&2
exit 1
