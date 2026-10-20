#!/usr/bin/env bash
# Creates the local platform: k3d cluster, Crossplane v2, Kyverno,
# Golden Paths, policies, platform MCP server and console.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/bootstrap/local/versions.env"

CLUSTER_NAME="${CLUSTER_NAME:-platform-starter-kit}"
# Overridable for mirrors or air-gapped setups.
CROSSPLANE_CHART="${CROSSPLANE_CHART:-crossplane-stable/crossplane}"
KYVERNO_CHART="${KYVERNO_CHART:-kyverno/kyverno}"
FUNCTION_REGISTRY="${FUNCTION_REGISTRY:-xpkg.crossplane.io}"
MCP_IMAGE="${MCP_IMAGE:-platform-starter-kit/platform-mcp:dev}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "Creating k3d cluster '$CLUSTER_NAME'"
if k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1; then
  echo "Cluster already exists, reusing it."
  k3d cluster start "$CLUSTER_NAME" >/dev/null
else
  k3d cluster create "$CLUSTER_NAME" --image "$K3S_IMAGE" \
    --config "$ROOT/bootstrap/local/k3d-config.yaml" --wait --timeout 180s
fi
kubectl config use-context "k3d-$CLUSTER_NAME" >/dev/null

if [[ "$CROSSPLANE_CHART" == crossplane-stable/* || "$KYVERNO_CHART" == kyverno/* ]]; then
  step "Adding Helm repositories"
  helm repo add crossplane-stable https://charts.crossplane.io/stable --force-update >/dev/null
  helm repo add kyverno https://kyverno.github.io/kyverno --force-update >/dev/null
  helm repo update >/dev/null
fi

step "Installing Crossplane $CROSSPLANE_VERSION"
helm upgrade --install crossplane "$CROSSPLANE_CHART" --version "$CROSSPLANE_VERSION" \
  --namespace crossplane-system --create-namespace --wait ${CROSSPLANE_HELM_ARGS:-}

step "Installing Kyverno (chart $KYVERNO_CHART_VERSION)"
helm upgrade --install kyverno "$KYVERNO_CHART" --version "$KYVERNO_CHART_VERSION" \
  --namespace kyverno --create-namespace --wait ${KYVERNO_HELM_ARGS:-}

step "Installing composition functions"
kubectl apply -f "$ROOT/control-plane/crossplane/rbac.yaml"
sed -e "s|xpkg.crossplane.io|$FUNCTION_REGISTRY|" \
    -e "s|\${FUNCTION_GO_TEMPLATING_VERSION}|$FUNCTION_GO_TEMPLATING_VERSION|" \
    "$ROOT/control-plane/crossplane/functions.yaml" | kubectl apply -f -
kubectl wait function.pkg.crossplane.io --all --for=condition=Healthy --timeout=300s

step "Installing Golden Paths"
kubectl apply -f "$ROOT/golden-paths/environment/definition.yaml" -f "$ROOT/golden-paths/app/definition.yaml"
kubectl wait xrd --all --for=condition=Established --timeout=120s
kubectl apply -f "$ROOT/golden-paths/environment/composition.yaml" -f "$ROOT/golden-paths/app/composition.yaml"

step "Installing guardrails (policies for humans and agents)"
kubectl apply -f "$ROOT/policies/"

step "Building and deploying the platform MCP server and console"
docker build -t "$MCP_IMAGE" ${MCP_BUILD_ARGS:-} "$ROOT/mcp-server"
k3d image import "$MCP_IMAGE" --cluster "$CLUSTER_NAME"
kubectl apply -f "$ROOT/mcp-server/deploy/"
kubectl -n platform-system set image deployment/platform-mcp platform="$MCP_IMAGE" >/dev/null
kubectl -n platform-system set image deployment/platform-console platform="$MCP_IMAGE" >/dev/null
kubectl -n platform-system rollout status deployment/platform-mcp --timeout=180s
kubectl -n platform-system rollout status deployment/platform-console --timeout=180s

step "Platform ready"
cat <<MSG
  Console (dashboard and approvals): http://localhost:8080
  MCP server for agents:             http://localhost:8081/mcp

  Next: 'make demo' loads the sample organization. See demo/README.md.
MSG
