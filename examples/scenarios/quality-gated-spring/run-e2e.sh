#!/usr/bin/env bash
# Black-box acceptance test for the discount-service demo, after the platform
# pipeline and GitOps report the deployment as ready.
set -euo pipefail

SERVICE="${1:-discount-service}"
ENVIRONMENT="${2:?usage: run-e2e.sh [service] <environment-name>}"
NAMESPACE="env-$ENVIRONMENT"
LOCAL_PORT="${LOCAL_PORT:-18080}"
forward=""
trap '[[ -n "$forward" ]] && kill "$forward" 2>/dev/null || true' EXIT

kubectl -n "$NAMESPACE" port-forward "svc/$SERVICE" "$LOCAL_PORT:80" >/dev/null 2>&1 &
forward=$!
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:$LOCAL_PORT/actuator/health" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS "http://localhost:$LOCAL_PORT/actuator/health" >/dev/null

check_discount() {
  customer="$1" expected="$2"
  body="$(curl -fsS "http://localhost:$LOCAL_PORT/discounts/$customer")"
  actual="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["discount"])' <<<"$body")"
  [[ "$actual" == "$expected" ]] || {
    echo "$customer: expected $expected%, received $actual% ($body)" >&2
    exit 1
  }
  echo "$customer: $actual%"
}

echo "Checking $SERVICE in $NAMESPACE"
check_discount C001 0
check_discount C002 5
check_discount C003 10
check_discount C004 10
check_discount C005 15
check_discount C999 0
echo "All discount-service E2E acceptance checks passed."
