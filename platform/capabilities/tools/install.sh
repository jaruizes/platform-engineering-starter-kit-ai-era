#!/usr/bin/env bash
# Installs capabilities in the current cluster: the platform API (XRD), what
# Crossplane needs to build it, how it is built and its guardrails.
#   platform/capabilities/tools/install.sh [NAME ...]   (all of them by default)
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
names=("$@")
if [[ ${#names[@]} -eq 0 ]]; then
  for definition in "$DIR"/*/definition.yaml; do names+=("$(basename "$(dirname "$definition")")"); done
fi

for name in "${names[@]}"; do
  folder="$DIR/$name"
  if [[ ! -f "$folder/definition.yaml" ]]; then
    echo "Skipping $name: it has a definition but has not been built yet."
    continue
  fi
  echo "Installing capability $name"
  kubectl apply -f "$folder/definition.yaml"
  xrd="$(kubectl get -f "$folder/definition.yaml" -o jsonpath='{.metadata.name}')"
  kubectl wait "xrd/$xrd" --for=condition=Established --timeout=120s
  [[ -f "$folder/rbac.yaml" ]] && kubectl apply -f "$folder/rbac.yaml"
  kubectl apply -f "$folder/composition.yaml" -f "$folder/policy.yaml"
done
