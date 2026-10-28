#!/usr/bin/env bash
# Runs what CI runs for a capability, and writes its TRACEABILITY.md.
#   platform/capabilities/tools/check.sh NAME [--no-e2e]
#
# 1. The definition follows the schema and the generated files keep it (capctl).
# 2. Every example renders with its composition (crossplane render).
# 3. The guardrails pass their policy tests (kyverno test).
# 4. With a cluster from `make up`: installs it and runs the acceptance tests,
#    as a person and as an agent.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$ROOT/bootstrap/local/versions.env"
NAME="${1:?usage: check.sh NAME [--no-e2e]}"
E2E=true
[[ "${2:-}" == "--no-e2e" ]] && E2E=false
FOLDER="$ROOT/platform/capabilities/$NAME"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
failed=0

step "Definition and generated files ($NAME)"
python3 "$ROOT/platform/capabilities/tools/capctl.py" validate "$NAME" || exit 1

step "Rendering every example with the composition"
sed "s|\${FUNCTION_GO_TEMPLATING_VERSION}|$FUNCTION_GO_TEMPLATING_VERSION|" \
  "$ROOT/platform/control-plane/crossplane/functions.yaml" > "$OUT/functions.yaml"
render=PASS
for example in "$FOLDER"/examples/*.yaml; do
  # CROSSPLANE_RENDER_ARGS lets you point to mirrored images.
  if crossplane render ${CROSSPLANE_RENDER_ARGS:-} "$example" "$FOLDER/composition.yaml" "$OUT/functions.yaml" > "$OUT/rendered.yaml"; then
    echo "✓ $(basename "$example"): $(grep -c '^kind:' "$OUT/rendered.yaml") resources"
  else
    echo "✗ $(basename "$example")"; render=FAIL; failed=1
  fi
done

step "Policy tests"
kyverno=PASS
kyverno test "$FOLDER/tests/kyverno" --remove-color || { kyverno=FAIL; failed=1; }

junit=()
if [[ "$E2E" == "true" ]]; then
  if kubectl get xrd >/dev/null 2>&1; then
    step "Installing $NAME in the cluster"
    "$ROOT/platform/capabilities/tools/install.sh" "$NAME" || failed=1
    step "Acceptance tests, as a person and as an agent"
    python3 -m pytest "$FOLDER/tests/e2e" -v --rootdir "$ROOT/capabilities" -p no:cacheprovider \
      --junitxml "$OUT/e2e.xml" || failed=1
    junit=(--junit "$OUT/e2e.xml")
  else
    echo "No platform cluster: skipping the acceptance tests (run 'make up' first, or pass --no-e2e)."
    failed=1
  fi
fi

step "Traceability"
python3 "$ROOT/platform/capabilities/tools/capctl.py" trace "$NAME" "${junit[@]}" --kyverno "$kyverno" --render "$render" || failed=1

if [[ $failed -ne 0 ]]; then
  printf '\n\033[1;31m%s is not ready: see the errors above and %s\033[0m\n' "$NAME" "platform/capabilities/$NAME/TRACEABILITY.md"
  exit 1
fi
printf '\n\033[1;32m%s passed every check. Next: a person on the platform team reviews it.\033[0m\n' "$NAME"
