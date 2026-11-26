#!/usr/bin/env bash
# Deletes the local platform.
set -euo pipefail
k3d cluster delete "${CLUSTER_NAME:-platform-starter-kit}"
