#!/usr/bin/env bash
# Creates the local platform: k3d cluster, Crossplane v2, Kyverno,
# Golden Paths, policies, platform MCP server, console and developer portal.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/bootstrap/local/versions.env"

CLUSTER_NAME="${CLUSTER_NAME:-platform-starter-kit}"
# Overridable for mirrors or air-gapped setups.
CROSSPLANE_CHART="${CROSSPLANE_CHART:-crossplane-stable/crossplane}"
KYVERNO_CHART="${KYVERNO_CHART:-kyverno/kyverno}"
FUNCTION_REGISTRY="${FUNCTION_REGISTRY:-xpkg.crossplane.io}"
MCP_IMAGE="${MCP_IMAGE:-platform-starter-kit/platform-mcp:dev}"
PORTAL_IMAGE="${PORTAL_IMAGE:-platform-starter-kit/portal:dev}"
# PORTAL=false skips the developer portal (Backstage), whose first build is slow.
PORTAL="${PORTAL:-true}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "Creating k3d cluster '$CLUSTER_NAME'"
if k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1; then
  echo "Cluster already exists, reusing it."
  k3d cluster start "$CLUSTER_NAME" >/dev/null
  # Clusters created by older versions of the kit do not publish every port.
  for port in 7007:30007 3000:30300; do
    if ! docker port "k3d-$CLUSTER_NAME-serverlb" 2>/dev/null | grep -q "^${port#*:}/"; then
      k3d cluster edit "$CLUSTER_NAME" --port-add "$port@loadbalancer"
    fi
  done
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
# The CRD watcher lets Kyverno enforce a new capability's guardrails as soon
# as it is installed, instead of after its next 15-minute resync.
helm upgrade --install kyverno "$KYVERNO_CHART" --version "$KYVERNO_CHART_VERSION" \
  --namespace kyverno --create-namespace --wait \
  --set admissionController.crdWatcher=true ${KYVERNO_HELM_ARGS:-}

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

step "Installing platform capabilities (capabilities/)"
"$ROOT/capabilities/tools/install.sh"

# Builds an image and loads it into the cluster. No provenance attestations:
# with Docker Desktop's containerd image store they break 'k3d image import'.
# Each build gets its own tag so pods always roll. Prints the tag.
load_image() {
  local image="$1" context="$2" build_args="${3:-}" flags="" id tagged node
  if docker buildx version >/dev/null 2>&1; then
    flags="--provenance=false --sbom=false"
  fi
  docker build $flags -t "$image" $build_args "$context" >&2
  id="$(docker image inspect --format '{{.Id}}' "$image")"
  tagged="${image%:*}:${id:7:12}"
  docker tag "$image" "$tagged"
  k3d image import "$tagged" --cluster "$CLUSTER_NAME" >&2
  node="k3d-$CLUSTER_NAME-server-0"
  if ! docker exec "$node" crictl inspecti "$tagged" >/dev/null 2>&1; then
    echo "The image did not reach the cluster, loading it directly into $node." >&2
    docker save "$tagged" | docker exec -i "$node" ctr -n k8s.io images import - >&2
  fi
  echo "$tagged"
}

# Applies the manifests in a folder with the given image.
deploy() {
  local dir="$1" placeholder="$2" image="$3"
  for manifest in "$dir"/*.yaml; do echo "---"; cat "$manifest"; done \
    | sed "s|image: $placeholder|image: $image|" \
    | kubectl apply -f -
}

diagnose() {
  echo
  echo "The $1 did not start. This is what the cluster says:"
  kubectl -n platform-system get pods -l "app.kubernetes.io/name=$1" -o wide || true
  kubectl -n platform-system describe pods -l "app.kubernetes.io/name=$1" | sed -n '/^Events:/,$p' || true
  kubectl -n platform-system logs "deployment/$1" --tail=30 || true
  exit 1
}

step "Building and deploying the platform MCP server and console"
IMAGE="$(load_image "$MCP_IMAGE" "$ROOT/mcp-server" "${MCP_BUILD_ARGS:-}")"
deploy "$ROOT/mcp-server/deploy" platform-starter-kit/platform-mcp:dev "$IMAGE"
kubectl -n platform-system rollout status deployment/platform-mcp --timeout=180s || diagnose platform-mcp
kubectl -n platform-system rollout status deployment/platform-console --timeout=180s || diagnose platform-console

if [[ "$PORTAL" == "true" ]]; then
  step "Deploying the local Git server (Gitea): service repositories and the platform repository"
  if ! kubectl -n platform-system get secret gitea-admin >/dev/null 2>&1; then
    kubectl -n platform-system create secret generic gitea-admin \
      --from-literal=username=platform-admin \
      --from-literal=password="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)"
  fi
  kubectl apply -f "$ROOT/git-server/gitea.yaml"
  kubectl -n platform-system rollout status deployment/gitea --timeout=180s || diagnose gitea
  # Where the portal proposes new capabilities as pull requests.
  "$ROOT/git-server/seed-platform-repo.sh"

  step "Building and deploying the developer portal (Backstage, the first build takes several minutes)"
  IMAGE="$(load_image "$PORTAL_IMAGE" "$ROOT/portal" "--build-context standards=$ROOT/standards --build-context capabilities=$ROOT/capabilities ${PORTAL_BUILD_ARGS:-}")"
  deploy "$ROOT/portal/deploy" platform-starter-kit/portal:dev "$IMAGE"
  kubectl -n platform-system rollout status deployment/portal --timeout=300s || diagnose portal
fi

step "Platform ready"
cat <<MSG
  Developer portal (Backstage):      http://localhost:7007
  Console (dashboard and approvals): http://localhost:8080
  MCP server for agents:             http://localhost:8081/mcp
  Portal MCP server (context):       http://localhost:7007/api/mcp-actions/v1/context
  Git server (repositories):         http://localhost:3000 (read-only without signing in)
  Platform repository (capabilities): http://localhost:3000/platform/platform-starter-kit

  Next: follow the demo script in demo/README.md.
MSG
