#!/usr/bin/env bash
# Stops the agent from changing infrastructure from its shell (kubectl apply,
# helm install, terraform apply, cloud CLIs...): that goes through the
# Golden Paths, where the platform knows who asked, applies the guardrails and
# keeps the cost. Reading (kubectl get, logs, port-forward) is fine.
#
# Claude Code runs it before every Bash command with the tool call as JSON on
# stdin. Exit code 2 blocks the command and tells the agent why.
# PLATFORM_HOOKS=off turns it off, for the platform team itself.
set -uo pipefail

[[ "${PLATFORM_HOOKS:-on}" == off ]] && exit 0

input="$(cat)"
command="$(printf '%s' "$input" | sed -nE 's/.*"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')"
[[ -z "$command" ]] && exit 0

changes_infrastructure='(^|[;&|(`[:space:]])('
changes_infrastructure+='kubectl[[:space:]]+([^;&|]*[[:space:]])?(apply|create|delete|edit|patch|replace|scale|set|run|expose|label|annotate|drain|cordon|taint|rollout[[:space:]]+(restart|undo))'
changes_infrastructure+='|helm[[:space:]]+([^;&|]*[[:space:]])?(install|upgrade|uninstall|rollback)'
changes_infrastructure+='|(terraform|tofu)[[:space:]]+([^;&|]*[[:space:]])?(apply|destroy|import)'
changes_infrastructure+='|aws[[:space:]]+[a-z0-9-]+[[:space:]]+(create|delete|put|run|update|terminate|modify|attach|detach)-[a-z0-9-]+'
changes_infrastructure+='|(gcloud|az)[[:space:]]+([^;&|]*[[:space:]])?(create|delete|update|deploy)'
changes_infrastructure+=')([[:space:]]|$)'

if [[ "$command" =~ $changes_infrastructure ]]; then
  cat >&2 <<MSG
Blocked by the platform plugin: "${BASH_REMATCH[2]}" changes infrastructure by hand.
On this platform, infrastructure comes from the Golden Paths, so the platform
knows who asked, applies the guardrails and tracks the cost:
- environments: request_environment (platform MCP server)
- services: create_service, then push to main (pipeline and Argo CD deploy it)
- databases and other capabilities: request_capability
Use kubectl only to read (get, describe, logs, port-forward). If the user
really needs this command, tell them so they can run it themselves.
MSG
  exit 2
fi
exit 0
