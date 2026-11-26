#!/usr/bin/env bash
# Installs capabilities in the current cluster: the platform API (XRD), what
# Crossplane needs to build it, how it is built and its guardrails.
#   platform/capabilities/tools/install.sh [NAME ...]   (contract-defined capabilities by default)
# Golden Path runtime (e.g. environments) is installed separately by deploy/install.sh.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/../infrastructure" && pwd)"
names=("$@")
if [[ ${#names[@]} -eq 0 ]]; then
  for definition in "$DIR"/*/capability.yaml; do
    [[ -f "$definition" ]] || continue
    names+=("$(basename "$(dirname "$definition")")")
  done
fi

for name in "${names[@]}"; do
  folder="$DIR/$name"
  if [[ ! -f "$folder/capability.yaml" ]]; then
    echo "Unknown declarative capability: $name (expected $folder/capability.yaml)" >&2
    exit 1
  fi
  if [[ ! -f "$folder/definition.yaml" ]]; then
    echo "Skipping $name: capability contract exists, but runtime has not been built yet."
    continue
  fi
  echo "Installing capability $name"
  kubectl apply -f "$folder/definition.yaml"
  xrd="$(kubectl get -f "$folder/definition.yaml" -o jsonpath='{.metadata.name}')"
  kubectl wait "xrd/$xrd" --for=condition=Established --timeout=120s
  [[ -f "$folder/rbac.yaml" ]] && kubectl apply -f "$folder/rbac.yaml"
  [[ -f "$folder/composition.yaml" ]] || { echo "Missing composition for $name" >&2; exit 1; }
  kubectl apply -f "$folder/composition.yaml"
  [[ -f "$folder/policy.yaml" ]] && kubectl apply -f "$folder/policy.yaml"
done
