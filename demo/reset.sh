#!/usr/bin/env bash
# Puts the demo back to a clean state: no environments, services,
# approvals or activity.
set -euo pipefail

echo "Deleting environments and services..."
kubectl delete apps.platform.starterkit.dev --all -A --wait=false >/dev/null 2>&1 || true
kubectl delete environments.platform.starterkit.dev --all --wait=false >/dev/null 2>&1 || true
kubectl -n platform-system delete configmap -l platform.starterkit.dev/approval-request >/dev/null 2>&1 || true
kubectl -n platform-system delete events --all >/dev/null 2>&1 || true

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
