#!/usr/bin/env bash
# Deletes the local platform.
set -euo pipefail
kind delete cluster --name "${CLUSTER_NAME:-platform-starter-kit}"
