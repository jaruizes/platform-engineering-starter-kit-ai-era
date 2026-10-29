#!/usr/bin/env bash
# Publishes this kit as the platform repository in the local Git server
# (platform/platform-starter-kit), where the portal proposes new capabilities
# as pull requests. With --reset it starts it again from scratch.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
GIT_URL="${GIT_URL:-http://localhost:3000}"
REPO=platform/platform-starter-kit
user="$(kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.username}' | base64 -d)"
password="$(kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.password}' | base64 -d)"
api() { curl -fsS -u "$user:$password" -H 'Content-Type: application/json' "$@"; }

for _ in $(seq 1 30); do api "$GIT_URL/api/v1/version" >/dev/null 2>&1 && break; sleep 2; done

if api "$GIT_URL/api/v1/repos/$REPO" >/dev/null 2>&1; then
  if [[ "${1:-}" != "--reset" ]]; then
    echo "The platform repository already exists: $GIT_URL/$REPO"
    exit 0
  fi
  api -X DELETE "$GIT_URL/api/v1/repos/$REPO" >/dev/null
fi
api -X POST "$GIT_URL/api/v1/orgs/platform/repos" \
  -d '{"name":"platform-starter-kit","description":"The platform: Golden Paths, capabilities and guardrails","default_branch":"main"}' >/dev/null
# Its GitHub workflows are not for the pipelines of the Git server.
api -X PATCH "$GIT_URL/api/v1/repos/$REPO" -d '{"has_actions":false}' >/dev/null

# One commit with the files of this checkout, without its history and without
# what .gitignore leaves out (dependencies, build output). tar copies them
# with their folders and symlinks on Linux and macOS alike.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$ROOT" ls-files -z --cached --others --exclude-standard |
    while IFS= read -r -d '' file; do
      # Skip files deleted in the working copy but still in the index.
      if [[ -e "$ROOT/$file" || -L "$ROOT/$file" ]]; then printf '%s\0' "$file"; fi
    done |
    tar -C "$ROOT" --null -T - -cf - | tar -C "$work" -xf -
else
  cp -R "$ROOT/." "$work"
fi
if [[ ! -d "$work/platform/capabilities" ]]; then
  echo "Could not copy the kit into the platform repository (nothing under $work)." >&2
  exit 1
fi
(
  cd "$work"
  git init -q -b main
  git -c user.name="Platform team" -c user.email="platform@starterkit.local" add -A
  git -c user.name="Platform team" -c user.email="platform@starterkit.local" commit -q -m "Platform repository"
  git push -q "http://$user:$password@${GIT_URL#http://}/$REPO.git" main
)
echo "Platform repository: $GIT_URL/$REPO"
