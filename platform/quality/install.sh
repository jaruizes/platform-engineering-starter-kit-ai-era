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
if [[ "$has_pipeline_secret" == true && "$has_admin_secret" == false ]]; then
  echo "The SonarQube CI token exists, but the admin password is missing. Run 'make sonar-down' and 'make sonar-up' to reinitialize it." >&2
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

sonar_api_post() {
  local label="$1" credentials="$2" endpoint="$3" response status
  shift 3
  response="$(mktemp)"
  status="$(curl -sS -u "$credentials" -o "$response" -w '%{http_code}' -X POST "$@" "http://localhost:19000$endpoint")" || {
    rm -f "$response"
    echo "SonarQube request failed: $label" >&2
    return 1
  }
  if [[ "$status" != 2* ]]; then
    echo "SonarQube request failed: $label (HTTP $status): $(cat "$response")" >&2
    rm -f "$response"
    return 1
  fi
  cat "$response"
  rm -f "$response"
}

if [[ "$has_admin_secret" == true ]]; then
  sonar_password="$(kubectl -n platform-system get secret sonar-admin-auth -o jsonpath='{.data.password}' | base64 -d)"
else
  # Current SonarQube Community Build enforces a mixed-character password
  # policy. Hex-only random passwords can be rejected with HTTP 400.
  sonar_password="S$(openssl rand -hex 16)a7!"
  echo "Changing the default SonarQube administrator password."
  sonar_api_post "change administrator password" admin:admin /api/users/change_password \
    --data-urlencode "login=admin" --data-urlencode "previousPassword=admin" \
    --data-urlencode "password=$sonar_password" >/dev/null
  # Persist this before token creation so a transient token API failure is
  # recoverable on the next installer run.
  kubectl -n platform-system create secret generic sonar-admin-auth \
    --from-literal=password="$sonar_password" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
fi

if [[ "$has_pipeline_secret" == false ]]; then
  echo "Creating the CI analysis token."
  token_name="platform-ci-$(openssl rand -hex 4)"
  token_json="$(sonar_api_post "create CI analysis token" "admin:$sonar_password" /api/user_tokens/generate \
    --data-urlencode "name=$token_name")"
  sonar_token="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$token_json")"
  kubectl -n platform-system create secret generic sonar-pipeline-auth \
    --from-literal=token="$sonar_token" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
fi
kill "$sonar_forward" 2>/dev/null || true
trap - EXIT
echo "SonarQube is ready. CI token and human admin password are stored in Secrets in platform-system."
