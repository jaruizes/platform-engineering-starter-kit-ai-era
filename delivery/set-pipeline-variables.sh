#!/usr/bin/env bash
# Sets the Gitea Actions variables of the "platform" organization, which the
# pipelines of every service repository read as vars.<NAME>:
#   delivery/set-pipeline-variables.sh NAME=value [NAME=value...]
set -euo pipefail

GIT_URL="${GIT_URL:-http://localhost:3000}"
user="$(kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.username}' | base64 -d)"
password="$(kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.password}' | base64 -d)"
api() { curl -fsS -o /dev/null -u "$user:$password" -H 'Content-Type: application/json' "$@"; }

for _ in $(seq 1 30); do api "$GIT_URL/api/v1/version" 2>/dev/null && break; sleep 2; done

for pair in "$@"; do
  name="${pair%%=*}"
  body="$(python3 -c 'import json,sys; print(json.dumps({"value": sys.argv[1]}))' "${pair#*=}")"
  url="$GIT_URL/api/v1/orgs/platform/actions/variables/$name"
  # Create it, or update it if it already exists.
  api -X POST "$url" -d "$body" 2>/dev/null || api -X PUT "$url" -d "$body"
  echo "Pipeline variable $name set."
done
