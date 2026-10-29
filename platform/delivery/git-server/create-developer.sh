#!/usr/bin/env bash
# Creates the "developer" account of the Git server: it can push to every
# repository of the "platform" organization (team "developers"). People and
# agents push service changes with it; a push to main deploys (GitOps).
# Its password is in the gitea-developer secret.
set -euo pipefail

GIT_URL="${GIT_URL:-http://localhost:3000}"
secret() { kubectl -n platform-system get secret "$1" -o jsonpath="{.data.$2}" | base64 -d; }
admin="$(secret gitea-admin username)"
admin_password="$(secret gitea-admin password)"
user="$(secret gitea-developer username)"
password="$(secret gitea-developer password)"
api() { curl -fsS -u "$admin:$admin_password" -H 'Content-Type: application/json' "$@"; }

if ! api "$GIT_URL/api/v1/users/$user" >/dev/null 2>&1; then
  api -X POST "$GIT_URL/api/v1/admin/users" -d "$(python3 -c '
import json,sys
print(json.dumps({"username": sys.argv[1], "password": sys.argv[2], "email": sys.argv[1] + "@starterkit.local",
                  "must_change_password": False}))' "$user" "$password")" >/dev/null
fi

team="$(api "$GIT_URL/api/v1/orgs/platform/teams/search?q=developers" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; print(d[0]["id"] if d else "")')"
if [[ -z "$team" ]]; then
  team="$(api -X POST "$GIT_URL/api/v1/orgs/platform/teams" -d '{
      "name": "developers", "description": "Push to the service repositories",
      "permission": "write", "includes_all_repositories": true,
      "units": ["repo.code", "repo.pulls", "repo.issues", "repo.actions", "repo.releases"]}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi
api -X PUT "$GIT_URL/api/v1/teams/$team/members/$user" >/dev/null
echo "Git server account '$user' can push to the repositories of the platform organization."
