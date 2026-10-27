#!/usr/bin/env bash
# Installs the platform on the cluster of the current kubectl context:
# Crossplane v2, Kyverno, Golden Paths, policies, capabilities, platform MCP
# server, console, Git server, delivery pipeline (Gitea Actions runner and
# Argo CD) and developer portal.
#
# The same for every way of running the kit. bootstrap/local/up.sh runs it on
# a k3d cluster and bootstrap/aws/up.sh on Amazon EKS, with these settings:
#
#   PUBLIC_HOST, PUBLIC_SCHEME  where people and agents reach the platform
#                               (default localhost and http). Every
#                               http://localhost:<port> in the manifests and
#                               in the portal configuration becomes
#                               PUBLIC_SCHEME://PUBLIC_HOST:<port>.
#   IMAGE_REGISTRY              push the images there (with IMAGE_PLATFORM,
#                               e.g. linux/arm64) instead of importing them
#                               into the k3d cluster CLUSTER_NAME.
#   PORTAL_MCP_TOKEN            token agents use for the portal MCP server.
#   PLATFORM_MCP_TOKEN          token agents use for the platform MCP server
#                               (none by default: open on localhost).
#   PLATFORM_MCP_PORTAL_TOKEN   token the platform MCP server uses for the portal.
#   PLATFORM_CA_FILE            CA the pods must trust to reach PUBLIC_HOST.
#   GIT_URL                     where this script reaches the Git server
#                               (default http://localhost:3000).
#   SERVICE_IMAGE_REPOSITORY    where pipelines push service images, with
#                               JIB_FLAGS (default: a registry in the cluster).
#   PORTAL=false                skips the portal.
#   DELIVERY=false              skips the pipelines and Argo CD.
#                               With both, the Git server is skipped too.
#   BRANDING_DIR                logos, title and texts of the portal.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/bootstrap/local/versions.env"

# Overridable for mirrors or air-gapped setups.
CROSSPLANE_CHART="${CROSSPLANE_CHART:-crossplane-stable/crossplane}"
KYVERNO_CHART="${KYVERNO_CHART:-kyverno/kyverno}"
FUNCTION_REGISTRY="${FUNCTION_REGISTRY:-xpkg.crossplane.io}"
MCP_IMAGE="${MCP_IMAGE:-platform-starter-kit/platform-mcp:dev}"
PORTAL_IMAGE="${PORTAL_IMAGE:-platform-starter-kit/portal:dev}"
RUNNER_IMAGE="${RUNNER_IMAGE:-platform-starter-kit/ci-runner:dev}"
PORTAL="${PORTAL:-true}"
DELIVERY="${DELIVERY:-true}"
ARGOCD_CHART="${ARGOCD_CHART:-argo/argo-cd}"
SERVICE_IMAGE_REPOSITORY="${SERVICE_IMAGE_REPOSITORY:-}"
JIB_FLAGS="${JIB_FLAGS:-}"
BRANDING_DIR="${BRANDING_DIR:-$ROOT/portal/branding}"
PUBLIC_HOST="${PUBLIC_HOST:-localhost}"
PUBLIC_SCHEME="${PUBLIC_SCHEME:-http}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
IMAGE_PLATFORM="${IMAGE_PLATFORM:-}"
# Local demo only: on localhost these are not secrets.
PORTAL_MCP_TOKEN="${PORTAL_MCP_TOKEN:-platform-starter-kit-local-demo}"
PLATFORM_MCP_PORTAL_TOKEN="${PLATFORM_MCP_PORTAL_TOKEN:-platform-mcp-local-demo}"
PLATFORM_MCP_TOKEN="${PLATFORM_MCP_TOKEN:-}"
PLATFORM_CA_FILE="${PLATFORM_CA_FILE:-}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
public_url() { echo "$PUBLIC_SCHEME://$PUBLIC_HOST:$1"; }

if [[ "$CROSSPLANE_CHART" == crossplane-stable/* || "$KYVERNO_CHART" == kyverno/* ]]; then
  step "Adding Helm repositories"
  helm repo add crossplane-stable https://charts.crossplane.io/stable --force-update >/dev/null
  helm repo add kyverno https://kyverno.github.io/kyverno --force-update >/dev/null
fi
if [[ "$DELIVERY" == "true" && "$ARGOCD_CHART" == argo/* ]]; then
  helm repo add argo https://argoproj.github.io/argo-helm --force-update >/dev/null
fi
if [[ "$CROSSPLANE_CHART" == crossplane-stable/* || "$KYVERNO_CHART" == kyverno/* || "$ARGOCD_CHART" == argo/* ]]; then
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

# Builds an image and makes it available to the cluster: pushed to
# IMAGE_REGISTRY, or imported into k3d. No provenance attestations: with
# Docker Desktop's containerd image store they break 'k3d image import'.
# Each build gets its own tag so pods always roll. Prints the tag.
load_image() {
  local image="$1" context="$2" build_args="${3:-}" flags="" id tagged node
  if [[ -n "$IMAGE_REGISTRY" ]]; then
    tagged="$IMAGE_REGISTRY/$(basename "${image%:*}"):$(date +%Y%m%d%H%M%S)"
    docker buildx build --provenance=false --sbom=false ${IMAGE_PLATFORM:+--platform "$IMAGE_PLATFORM"} \
      -t "$tagged" $build_args --push "$context" >&2
    echo "$tagged"
    return
  fi
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

# The manifests use the local addresses. Off localhost, they become the
# public ones, and the images come from the registry.
publish() {
  if [[ "$PUBLIC_HOST" == localhost && "$PUBLIC_SCHEME" == http ]]; then
    cat
  else
    sed -e "s|http://localhost:|$PUBLIC_SCHEME://$PUBLIC_HOST:|g" \
        -e "s|value: localhost\$|value: $PUBLIC_HOST|" \
        -e "s|value: \"localhost:\*,|value: \"$PUBLIC_HOST:*,localhost:*,|"
  fi | if [[ -n "$IMAGE_REGISTRY" ]]; then sed 's|imagePullPolicy: Never|imagePullPolicy: IfNotPresent|'; else cat; fi
}

# Applies the manifests in a folder with the given image.
deploy() {
  local dir="$1" placeholder="$2" image="$3"
  for manifest in "$dir"/*.yaml; do echo "---"; cat "$manifest"; done \
    | sed "s|image: $placeholder|image: $image|" | publish \
    | kubectl apply -f -
}

secret() {
  kubectl -n platform-system create secret generic "$1" "${@:2}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
}

diagnose() {
  echo
  echo "The $1 did not start. This is what the cluster says:"
  kubectl -n platform-system get pods -l "app.kubernetes.io/name=$1" -o wide || true
  kubectl -n platform-system describe pods -l "app.kubernetes.io/name=$1" | sed -n '/^Events:/,$p' || true
  kubectl -n platform-system logs "deployment/$1" --tail=30 || true
  exit 1
}

step "Creating the tokens of the MCP servers"
kubectl apply -f "$ROOT/mcp-server/deploy/00-namespace.yaml"
secret portal-mcp-token --from-literal=token="$PORTAL_MCP_TOKEN"
secret platform-mcp-portal-token --from-literal=token="$PLATFORM_MCP_PORTAL_TOKEN"
secret platform-mcp-token --from-literal=token="$PLATFORM_MCP_TOKEN"
# The Git server's accounts and the registration token of the pipeline runner.
random() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
if ! kubectl -n platform-system get secret gitea-admin >/dev/null 2>&1; then
  secret gitea-admin --from-literal=username=platform-admin --from-literal=password="$(random 20)"
fi
if ! kubectl -n platform-system get secret gitea-developer >/dev/null 2>&1; then
  secret gitea-developer --from-literal=username=developer --from-literal=password="$(random 20)"
fi
if ! kubectl -n platform-system get secret gitea-runner-token >/dev/null 2>&1; then
  secret gitea-runner-token --from-literal=token="$(random 40)"
fi
if [[ -n "$PLATFORM_CA_FILE" ]]; then
  # The pods that call PUBLIC_HOST trust its certificate.
  kubectl -n platform-system create configmap platform-ca --from-file=ca.crt="$PLATFORM_CA_FILE" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
fi

step "Building and deploying the platform MCP server and console"
IMAGE="$(load_image "$MCP_IMAGE" "$ROOT/mcp-server" "${MCP_BUILD_ARGS:-}")"
deploy "$ROOT/mcp-server/deploy" platform-starter-kit/platform-mcp:dev "$IMAGE"
kubectl -n platform-system rollout status deployment/platform-mcp --timeout=180s || diagnose platform-mcp
kubectl -n platform-system rollout status deployment/platform-console --timeout=180s || diagnose platform-console

if [[ "$PORTAL" == "true" || "$DELIVERY" == "true" ]]; then
  step "Deploying the Git server (Gitea): service repositories, their pipelines and the platform repository"
  publish < "$ROOT/git-server/gitea.yaml" | kubectl apply -f -
  kubectl -n platform-system rollout status deployment/gitea --timeout=180s || diagnose gitea
  # Off localhost, this script reaches the Git server through a port-forward.
  forward=""
  if [[ -z "${GIT_URL:-}" && "$PUBLIC_HOST" != localhost ]]; then
    kubectl -n platform-system port-forward svc/gitea 13000:3000 >/dev/null 2>&1 &
    forward=$!
    export GIT_URL=http://localhost:13000
    sleep 2
  fi
  # Where the portal proposes new capabilities as pull requests.
  "$ROOT/git-server/seed-platform-repo.sh"
  # The account people and agents push service changes with.
  "$ROOT/git-server/create-developer.sh"

  if [[ "$DELIVERY" == "true" ]]; then
    step "Installing the delivery pipeline: Gitea Actions runner and service image registry"
    if [[ -z "$SERVICE_IMAGE_REPOSITORY" ]]; then
      kubectl apply -f "$ROOT/delivery/registry.yaml"
      kubectl -n platform-system rollout status deployment/service-images --timeout=120s || diagnose service-images
      SERVICE_IMAGE_REPOSITORY=10.43.0.200:5000/services
      JIB_FLAGS="${JIB_FLAGS:--Djib.allowInsecureRegistries=true}"
    fi
    # What the pipelines of every service repository read (vars.* in .gitea/workflows).
    "$ROOT/delivery/set-pipeline-variables.sh" \
      PLATFORM_GIT_HOST=gitea.platform-system.svc:3000 \
      SERVICE_IMAGE_REPOSITORY="$SERVICE_IMAGE_REPOSITORY" \
      JIB_FLAGS="$JIB_FLAGS"
    IMAGE="$(load_image "$RUNNER_IMAGE" "$ROOT/delivery/runner" "${RUNNER_BUILD_ARGS:-}")"
    deploy "$ROOT/delivery/deploy" platform-starter-kit/ci-runner:dev "$IMAGE"
    kubectl -n platform-system rollout status deployment/platform-ci-runner --timeout=180s || diagnose platform-ci-runner

    step "Installing Argo CD (chart $ARGOCD_CHART_VERSION): GitOps for the service repositories"
    helm upgrade --install argocd "$ARGOCD_CHART" --version "$ARGOCD_CHART_VERSION" \
      --namespace argocd --create-namespace --wait --timeout 10m \
      -f "$ROOT/delivery/argocd/values.yaml" ${ARGOCD_HELM_ARGS:-} || {
      echo "Argo CD did not start. This is what the cluster says:"
      kubectl -n argocd get pods -o wide || true
      kubectl -n argocd get events --sort-by=.lastTimestamp | tail -30 || true
      exit 1
    }
    kubectl apply -f "$ROOT/delivery/argocd/services.yaml"
  fi
  if [[ -n "$forward" ]]; then kill "$forward" 2>/dev/null || true; unset GIT_URL; fi
fi

if [[ "$PORTAL" == "true" ]]; then
  step "Building and deploying the developer portal (Backstage, the first build takes several minutes)"
  [[ -f "$BRANDING_DIR/branding.yaml" ]] || { echo "No branding.yaml in BRANDING_DIR=$BRANDING_DIR" >&2; exit 1; }
  BRANDING_DIR="$(cd "$BRANDING_DIR" && pwd)"
  echo "Branding: $BRANDING_DIR"
  IMAGE="$(load_image "$PORTAL_IMAGE" "$ROOT/portal" "--build-context standards=$ROOT/standards --build-context capabilities=$ROOT/capabilities --build-context branding=$BRANDING_DIR ${PORTAL_BUILD_ARGS:-}")"
  deploy "$ROOT/portal/deploy" platform-starter-kit/portal:dev "$IMAGE"
  kubectl -n platform-system rollout status deployment/portal --timeout=300s || diagnose portal
fi

step "Platform ready"
cat <<MSG
  Developer portal (Backstage):       $(public_url 7007)
  Console (dashboard and approvals):  $(public_url 8080)
  MCP server for agents:              $(public_url 8081)/mcp
  Portal MCP server (context):        $(public_url 7007)/api/mcp-actions/v1/context
  Git server (repositories):          $(public_url 3000) (read-only without signing in)
  Argo CD (GitOps, read-only):        $(public_url 8082)
  Platform repository (capabilities): $(public_url 3000)/platform/platform-starter-kit

  Push to the service repositories as "developer"; its password:
    kubectl -n platform-system get secret gitea-developer -o jsonpath='{.data.password}' | base64 -d
MSG
