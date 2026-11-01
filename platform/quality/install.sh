#!/usr/bin/env bash
# Install SonarQube and provision its private CI token and human admin password.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
kubectl create namespace platform-system --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -f "$ROOT/platform/quality/sonarqube.yaml"
kubectl -n quality rollout status deployment/sonarqube --timeout=600s

has_pipeline_secret=false
has_admin_secret=false
kubectl -n platform-system get secret sonar-pipeline-auth >/dev/null 2>&1 && has_pipeline_secret=true
kubectl -n platform-system get secret sonar-admin-auth >/dev/null 2>&1 && has_admin_secret=true
if [[ "$has_pipeline_secret" == true && "$has_admin_secret" == true ]]; then
  echo "SonarQube is ready; its existing CI token and admin password are retained."
  exit 0
fi
if [[ "$has_pipeline_secret" == true || "$has_admin_secret" == true ]]; then
  echo "SonarQube has only one of its two credentials. Run 'make sonar-down' and then 'make up' to reinitialize it." >&2
  exit 1
fi

kubectl -n quality port-forward svc/sonarqube 19000:9000 >/dev/null 2>&1 &
sonar_forward=$!
trap 'kill "$sonar_forward" 2>/dev/null || true' EXIT
sonar_ready=false
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:19000/api/system/status 2>/dev/null | grep -q '"status":"UP"'; then
    sonar_ready=true
    break
  fi
  sleep 2
done
[[ "$sonar_ready" == true ]] || { echo "SonarQube did not become ready." >&2; exit 1; }

sonar_password="$(openssl rand -hex 16)"
curl -fsS -u admin:admin -X POST \
  --data-urlencode "login=admin" --data-urlencode "previousPassword=admin" \
  --data-urlencode "password=$sonar_password" \
  http://localhost:19000/api/users/change_password >/dev/null
token_json="$(curl -fsS -u "admin:$sonar_password" -X POST \
  --data-urlencode "name=platform-ci" http://localhost:19000/api/user_tokens/generate)"
sonar_token="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$token_json")"
kubectl -n platform-system create secret generic sonar-pipeline-auth \
  --from-literal=token="$sonar_token" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n platform-system create secret generic sonar-admin-auth \
  --from-literal=password="$sonar_password" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kill "$sonar_forward" 2>/dev/null || true
trap - EXIT
echo "SonarQube is ready. CI token and human admin password are stored in Secrets in platform-system."
