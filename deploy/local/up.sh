#!/usr/bin/env bash
# Creates the local platform: a k3d cluster with everything that
# bootstrap/install.sh installs (Crossplane v2, Kyverno, Golden Paths,
# policies, platform MCP server, console and developer portal).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/bootstrap/local/versions.env"

export CLUSTER_NAME="${CLUSTER_NAME:-platform-starter-kit}"
# PORTAL=false skips the developer portal (Backstage), whose first build is slow.
# BRANDING_DIR: the logos, title and texts of the portal (interfaces/portal/branding/README.md).
# See bootstrap/install.sh for the rest of the settings.

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "Creating k3d cluster '$CLUSTER_NAME'"
if k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1; then
  echo "Cluster already exists, reusing it."
  k3d cluster start "$CLUSTER_NAME" >/dev/null
  # Clusters created by older versions of the kit do not publish every port.
  for port in 7007:30007 3000:30300 8082:30082; do
    if ! docker port "k3d-$CLUSTER_NAME-serverlb" 2>/dev/null | grep -q "^${port#*:}/"; then
      k3d cluster edit "$CLUSTER_NAME" --port-add "$port@loadbalancer"
    fi
  done
  # Nor do they know the registry of the service images.
  node="k3d-$CLUSTER_NAME-server-0"
  if ! docker exec "$node" grep -q 10.43.0.200 /etc/rancher/k3s/registries.yaml 2>/dev/null; then
    docker exec -i "$node" sh -c 'cat > /etc/rancher/k3s/registries.yaml' < "$ROOT/bootstrap/local/registries.yaml"
    k3d cluster stop "$CLUSTER_NAME" >/dev/null && k3d cluster start "$CLUSTER_NAME" >/dev/null
  fi
else
  k3d cluster create "$CLUSTER_NAME" --image "$K3S_IMAGE" \
    --config "$ROOT/bootstrap/local/k3d-config.yaml" \
    --registry-config "$ROOT/bootstrap/local/registries.yaml" --wait --timeout 180s
fi
kubectl config use-context "k3d-$CLUSTER_NAME" >/dev/null

"$ROOT/bootstrap/install.sh"

echo
echo "  Next: follow the demo script in examples/scenarios/README.md."
