#!/usr/bin/env bash
# Daemonless multi-arch Python OCI image, matching the existing Angular Golden Path.
# Needs Python 3.12 + pip, crane and registry credentials from the platform runner.
set -euo pipefail

IMAGE="${1:?Usage: scripts/build-image.sh registry/repository:tag}"
command -v crane >/dev/null || { echo "crane is required" >&2; exit 1; }
python3 -m pip --version >/dev/null || { echo "python3-pip is required on the platform runner" >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info[:2] == (3, 12), "CI Python must be 3.12"'
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -f operations.json ]] || { echo "Missing operations.json" >&2; exit 1; }

REGISTRY="${IMAGE%%/*}"
if [[ "$REGISTRY" == *.dkr.ecr.*.amazonaws.com ]]; then
  mkdir -p "$HOME/.docker"
  printf '{"credHelpers":{"%s":"ecr-login"}}\n' "$REGISTRY" > "$HOME/.docker/config.json"
fi

for ARCH in amd64 arm64; do
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  mkdir -p "$TMP/opt/app/deps" "$TMP/opt/app/rest_mcp_adapter"
  # Install compatible Linux wheels for BOTH architectures. Do not copy
  # runner-native pydantic/crypto binaries into the wrong-architecture image.
  case "$ARCH" in
    amd64) MACHINE=x86_64 ;;
    arm64) MACHINE=aarch64 ;;
  esac
  python3 -m pip install --disable-pip-version-check --quiet --no-compile \
    --ignore-installed --only-binary=:all: \
    --implementation cp --python-version 3.12 \
    --platform "manylinux_2_28_${MACHINE}" \
    --platform "manylinux_2_17_${MACHINE}" \
    --platform "manylinux2014_${MACHINE}" \
    --target "$TMP/opt/app/deps" "mcp==2.3.0"
  cp rest_mcp_adapter/*.py "$TMP/opt/app/rest_mcp_adapter/"
  cp operations.json "$TMP/opt/app/operations.json"
  tar -C "$TMP" -cf "$TMP/image.tar" opt/
  crane append --platform "linux/$ARCH" \
    --base python:3.12-slim-bookworm \
    --new_layer "$TMP/image.tar" \
    --new_tag "$IMAGE-$ARCH-unconfigured"
  crane mutate "$IMAGE-$ARCH-unconfigured" \
    --entrypoint=/usr/local/bin/python \
    --cmd=-m,rest_mcp_adapter.server \
    --env=PYTHONPATH=/opt/app/deps:/opt/app \
    --workdir=/opt/app \
    --user=10001:10001 \
    --exposed-ports=8080/tcp \
    --tag "$IMAGE-$ARCH"
  rm -rf "$TMP"
  trap - EXIT
done

crane index append \
  --manifest "$IMAGE-amd64" \
  --manifest "$IMAGE-arm64" \
  --tag "$IMAGE"
crane manifest "$IMAGE" > /dev/null
echo "Published multi-architecture MCP image: $IMAGE"
