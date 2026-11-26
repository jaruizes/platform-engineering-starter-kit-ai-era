#!/usr/bin/env bash
# Deletes the platform on AWS, everything make aws-up created. The CA and the
# tokens stay in bootstrap/aws/.state for the next demo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AWS_DIR="$ROOT/bootstrap/aws"
STATE="$AWS_DIR/.state"
TOFU="${TOFU:-$(command -v tofu || command -v terraform || true)}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

: "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (and AWS_SESSION_TOKEN for temporary credentials).}"
: "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY.}"
export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-1}}"
unset AWS_PROFILE
[[ -f "$STATE/terraform.tfstate" ]] || { echo "Nothing to delete: there is no platform on AWS."; exit 0; }

# The EBS volumes of the Git server and the databases are created by the
# cluster, not by OpenTofu: delete them first so none is left behind.
k() { kubectl --context platform-starter-kit-aws "$@"; }
if k get nodes >/dev/null 2>&1; then
  step "Deleting the volumes created in the cluster"
  # Crossplane would recreate the databases of the capabilities.
  k -n crossplane-system scale deployment --all --replicas=0 >/dev/null 2>&1 || true
  for ns in $(k get pvc -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\n"}{end}' | sort -u); do
    k -n "$ns" delete deployments,statefulsets --all --wait=true --timeout=120s || true
  done
  k delete pvc --all -A --wait=true --timeout=300s || true
  for _ in $(seq 1 60); do
    [[ -z "$(k get pv -o name 2>/dev/null)" ]] && break
    sleep 5
  done
fi

step "Deleting the AWS infrastructure with OpenTofu (about 15 minutes)"
export TF_VAR_allowed_cidrs='["127.0.0.1/32"]'
export TF_VAR_ca_cert_pem="$(cat "$STATE/ca.pem")"
export TF_VAR_ca_key_pem="$(cat "$STATE/ca.key")"
"$TOFU" -chdir="$AWS_DIR" init -input=false >/dev/null
"$TOFU" -chdir="$AWS_DIR" destroy -input=false -auto-approve

kubectl config delete-context platform-starter-kit-aws >/dev/null 2>&1 || true
if command -v claude >/dev/null 2>&1; then
  claude mcp remove --scope local platform >/dev/null 2>&1 || true
  claude mcp remove --scope local portal >/dev/null 2>&1 || true
fi
echo "Deleted. The CA and the tokens are still in $STATE for the next demo."
