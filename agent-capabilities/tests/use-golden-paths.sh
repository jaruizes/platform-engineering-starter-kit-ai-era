#!/usr/bin/env bash
# Checks which commands the platform plugin's hook lets agents run.
#   agent-capabilities/tests/use-golden-paths.sh
set -uo pipefail

HOOK="$(cd "$(dirname "$0")/.." && pwd)/platform/hooks/use-golden-paths.sh"
failed=0

check() {
  local expected="$1" command="$2" input code
  input="$(python3 -c 'import json,sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1], "description": "test"}}))' "$command")"
  printf '%s' "$input" | "$HOOK" 2>/dev/null
  code=$?
  if { [[ "$expected" == allow && $code -eq 0 ]] || [[ "$expected" == block && $code -eq 2 ]]; }; then
    printf 'ok    %-5s %s\n' "$expected" "$command"
  else
    printf 'FAIL  %-5s %s (exit %s)\n' "$expected" "$command" "$code"
    failed=1
  fi
}

check allow 'kubectl get pods -n env-checkout'
check allow 'kubectl -n env-checkout logs deploy/discount-service --tail=50'
check allow 'kubectl -n env-checkout port-forward svc/discount-service 8080:80'
check allow 'kubectl describe app discount-service'
check allow './mvnw verify'
check allow 'git commit -m "Apply the discount rules" && git push origin main'
check allow 'helm template x ./chart'
check allow 'grep -rn "kubectl apply" docs/'
check allow 'aws sts get-caller-identity'
check block 'kubectl apply -f deploy/app.yaml'
check block 'kubectl -n env-checkout delete pod discount-service-1'
check block 'kubectl --context prod create namespace payments'
check block 'cd infra && terraform apply -auto-approve'
check block 'tofu destroy'
check block 'helm upgrade --install redis bitnami/redis'
check block 'aws rds create-db-instance --db-instance-identifier x'
check block 'echo ok; kubectl scale deploy/x --replicas=3'
check block 'kubectl rollout restart deploy/discount-service'
PLATFORM_HOOKS=off check allow 'kubectl apply -f deploy/app.yaml'

exit $failed
