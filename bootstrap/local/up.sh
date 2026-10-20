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
# No provenance attestations: with Docker Desktop's containerd image store they
# break 'k3d image import'. Each build gets its own tag so pods always roll.
BUILD_FLAGS=""
if docker buildx version >/dev/null 2>&1; then
  BUILD_FLAGS="--provenance=false --sbom=false"
fi
docker build $BUILD_FLAGS -t "$MCP_IMAGE" ${MCP_BUILD_ARGS:-} "$ROOT/mcp-server"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$MCP_IMAGE")"
IMAGE="${MCP_IMAGE%:*}:${IMAGE_ID:7:12}"
docker tag "$MCP_IMAGE" "$IMAGE"
k3d image import "$IMAGE" --cluster "$CLUSTER_NAME"

NODE="k3d-$CLUSTER_NAME-server-0"
if ! docker exec "$NODE" crictl inspecti "$IMAGE" >/dev/null 2>&1; then
  echo "The image did not reach the cluster, loading it directly into $NODE."
  docker save "$IMAGE" | docker exec -i "$NODE" ctr -n k8s.io images import -
fi

for manifest in "$ROOT"/mcp-server/deploy/*.yaml; do echo "---"; cat "$manifest"; done \
  | sed "s|image: platform-starter-kit/platform-mcp:dev|image: $IMAGE|" \
  | kubectl apply -f -

diagnose() {
  echo
  echo "The $1 did not start. This is what the cluster says:"
  kubectl -n platform-system get pods -l "app.kubernetes.io/name=$1" -o wide || true
  kubectl -n platform-system describe pods -l "app.kubernetes.io/name=$1" | sed -n '/^Events:/,$p' || true
  kubectl -n platform-system logs "deployment/$1" --tail=30 || true
  exit 1
}
kubectl -n platform-system rollout status deployment/platform-mcp --timeout=180s || diagnose platform-mcp
kubectl -n platform-system rollout status deployment/platform-console --timeout=180s || diagnose platform-console

step "Platform ready"
cat <<MSG
  Console (dashboard and approvals): http://localhost:8080
  MCP server for agents:             http://localhost:8081/mcp

  Next: 'make demo' loads the sample organization. See demo/README.md.
MSG
