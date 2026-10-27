#!/usr/bin/env bash
# Creates the platform on AWS for a demo: a VPC, an EKS cluster with the
# control plane and the portal, and a load balancer with HTTPS in front of
# them, reachable only from ALLOWED_CIDRS. make aws-down deletes it all.
#
# Credentials come from the environment, as for the AWS CLI:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN (temporary
#   credentials only) and AWS_REGION (default eu-west-1).
# ALLOWED_CIDRS: comma-separated addresses that can reach the platform
#   (default: the public IP of this computer).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AWS_DIR="$ROOT/bootstrap/aws"
STATE="$AWS_DIR/.state"
TOFU="${TOFU:-$(command -v tofu || command -v terraform || true)}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { echo "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing $1. $2"; }

need aws "Install the AWS CLI v2."
need kubectl "Install kubectl."
need helm "Install Helm."
need docker "Install Docker with buildx."
need openssl "Install OpenSSL."
need curl "Install curl."
[[ -n "$TOFU" ]] || fail "Missing OpenTofu (tofu) or Terraform."

: "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (and AWS_SESSION_TOKEN for temporary credentials).}"
: "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY.}"
export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-1}}"
# Only the variables above: no profile from ~/.aws gets in the way.
unset AWS_PROFILE

step "Checking the AWS credentials"
aws sts get-caller-identity --query '[Account, Arn]' --output text \
  || fail "The credentials in AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY do not work."
echo "Region: $AWS_REGION"

if [[ -z "${ALLOWED_CIDRS:-}" ]]; then
  ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  ALLOWED_CIDRS="$ip/32"
fi
echo "Allowed addresses: $ALLOWED_CIDRS"

mkdir -p "$STATE"
chmod 700 "$STATE"
# The CA that signs the load balancer certificate. Created once and kept, so
# you trust it once on your computer (see README.md) for every demo.
if [[ ! -f "$STATE/ca.pem" ]]; then
  step "Creating the CA of the demo (kept in bootstrap/aws/.state)"
  openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 825 \
    -keyout "$STATE/ca.key" -out "$STATE/ca.pem" -subj "/CN=Platform Starter Kit demo CA" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
fi
# The tokens of the MCP servers, kept too so .mcp.json survives a new demo.
if [[ ! -f "$STATE/tokens.env" ]]; then
  cat > "$STATE/tokens.env" <<TOKENS
PORTAL_MCP_TOKEN=$(openssl rand -hex 24)
PLATFORM_MCP_TOKEN=$(openssl rand -hex 24)
PLATFORM_MCP_PORTAL_TOKEN=$(openssl rand -hex 24)
TOKENS
fi
set -a
source "$STATE/tokens.env"
set +a

step "Creating the AWS infrastructure with OpenTofu (VPC, EKS, ECR, load balancer: about 20 minutes)"
export TF_VAR_allowed_cidrs="[\"${ALLOWED_CIDRS//,/\",\"}\"]"
export TF_VAR_ca_cert_pem="$(cat "$STATE/ca.pem")"
export TF_VAR_ca_key_pem="$(cat "$STATE/ca.key")"
"$TOFU" -chdir="$AWS_DIR" init -input=false >/dev/null
"$TOFU" -chdir="$AWS_DIR" apply -input=false -auto-approve
out() { "$TOFU" -chdir="$AWS_DIR" output -raw "$1"; }

step "Connecting kubectl to the cluster"
aws eks update-kubeconfig --name "$(out cluster_name)" --region "$AWS_REGION" --alias platform-starter-kit-aws
kubectl apply -f - <<SC
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
parameters:
  type: gp3
SC

step "Logging in to the image registry (ECR)"
registry="$(out image_registry)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"

PUBLIC_HOST="$(out public_host)"
export PUBLIC_HOST PUBLIC_SCHEME=https
export IMAGE_REGISTRY="$registry/$(out image_repository_prefix)" IMAGE_PLATFORM="$(out image_platform)"
export PLATFORM_CA_FILE="$STATE/ca.pem"
# The pipelines push the service images to ECR, with the runner's Pod Identity role.
export SERVICE_IMAGE_REPOSITORY="$(out service_image_repository)" JIB_FLAGS="-Djib.to.credHelper=ecr-login"
"$ROOT/bootstrap/install.sh"

base="https://$PUBLIC_HOST"
cat <<MSG

  Trust the CA of the demo once, so the browser shows no warning (macOS):
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $STATE/ca.pem

  Connect Claude Code to the MCP servers on AWS (local scope: it takes
  precedence over .mcp.json in this folder; make aws-down removes them):
    claude mcp add --scope local --transport http platform $base:8081/mcp \\
      --header "Authorization: Bearer $PLATFORM_MCP_TOKEN"
    claude mcp add --scope local --transport http portal $base:7007/api/mcp-actions/v1/context \\
      --header "Authorization: Bearer $PORTAL_MCP_TOKEN"
  and start it so it trusts the CA:
    NODE_EXTRA_CA_CERTS=$STATE/ca.pem claude

  To clone the repositories of the Git server:
    git config --global http.$base:3000/.sslCAInfo $STATE/ca.pem

  Next: follow the demo script in demo/README.md. When you are done: make aws-down
MSG
