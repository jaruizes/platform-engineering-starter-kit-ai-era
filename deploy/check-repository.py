#!/usr/bin/env python3
"""Check repository paths and shared agent adapters without a running cluster."""
import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []


def check(ok, message):
    if not ok:
        errors.append(message)


for folder in (
    'platform/integrations/crossplane', 'platform/capabilities', 'platform/governance/policies',
    'platform/capabilities/delivery', 'platform/access/portal', 'platform/access/mcp',
    'platform/access/identity', 'platform/access/cli', 'platform/capabilities/api',
    'platform/cognitive/knowledge/standards', 'platform/capabilities/golden-paths', 'platform/capabilities/infrastructure',
    'platform/ai/agent-tooling/skills', 'platform/ai/agent-tooling/instructions',
    'platform/ai/agent-tooling/clients', 'examples/scenarios', 'deploy',
):
    check((ROOT / folder).is_dir(), f'Missing responsibility directory: {folder}')

for folder in ('.claude/skills', '.agents/skills', '.gemini/skills'):
    check((ROOT / folder).resolve() == ROOT / 'platform/ai/agent-tooling/skills', f'{folder} must link to the shared skills')

for path in ROOT.rglob('*'):
    if any(part in {'.git', 'node_modules', '.venv', '__pycache__', '.pytest_cache'} for part in path.parts):
        continue
    if path.is_symlink():
        check(path.exists(), f'Broken link: {path.relative_to(ROOT)}')
        continue
    if not path.is_file():
        continue
    if path.suffix == '.py':
        ast.parse(path.read_text(), filename=str(path))
    if path.suffix == '.sh':
        result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
        check(result.returncode == 0, result.stderr)
        # Installer paths must resolve in the repository, not just parse.
        for target in re.findall(r'\$ROOT/([\w./-]+)', path.read_text()):
            check((ROOT / target).exists(), f'{path.relative_to(ROOT)}: missing $ROOT/{target}')

for capability in (ROOT / 'platform/capabilities/infrastructure').glob('*/capability.yaml'):
    skill = capability.parent / 'SKILL.md'
    check(skill.is_symlink(), f'{skill.relative_to(ROOT)} must link to the canonical skill')
    check(skill.resolve() == ROOT / 'platform/ai/agent-tooling/skills' / capability.parent.name / 'SKILL.md',
          f'Wrong canonical skill for {capability.parent.name}')

claude = json.loads((ROOT / '.mcp.json').read_text())['mcpServers']
gemini = json.loads((ROOT / '.gemini/settings.json').read_text())['mcpServers']
codex = tomllib.loads((ROOT / '.codex/config.toml').read_text())['mcp_servers']
check(set(claude) == set(gemini) == set(codex) == {'platform', 'portal'}, 'Client server names differ')
for name, server in claude.items():
    check(server['type'] == 'http', f'{name}: expected HTTP transport')
    check(server['url'] == gemini[name]['httpUrl'] == codex[name]['url'], f'{name}: client URLs differ')
    check(server.get('headers', {}) == gemini[name].get('headers', {}) == codex[name].get('http_headers', {}),
          f'{name}: client headers differ')

# The platform MCP server is an OAuth resource server: each client signs in
# with its own Keycloak client, which must exist in the realm.
realm = json.loads((ROOT / 'platform/access/identity/realm/platform-realm.json').read_text())
clients = {c['clientId']: c for c in realm['clients']}
for agent, client_id in (('claude', claude['platform'].get('oauth', {}).get('clientId')),
                         ('gemini', gemini['platform'].get('oauth', {}).get('clientId'))):
    check(client_id in clients, f'{agent}: the platform server must sign in with a client of the platform realm')
check(codex['platform'].get('bearer_token_env_var') == 'PLATFORM_TOKEN', 'codex: platform needs PLATFORM_TOKEN')
check('codex' in clients and 'ci-agent' in clients, 'The realm needs the codex and ci-agent clients')
callback = claude['platform'].get('oauth', {}).get('callbackPort')
check(any(f':{callback}/' in uri for uri in clients.get('claude-code', {}).get('redirectUris', [])),
      'claude-code: the callback port must be a redirect URI of its Keycloak client')

# People sign in to the portal with Keycloak, and the portal calls the platform
# API with their token: the realm has the portal's client, the realm and the
# catalog have the same people and teams, and every template that runs a
# platform action sends the person's token (form decorator platform-identity).
portal_client = clients.get('portal', {})
check(not portal_client.get('publicClient', True) and
      '${PORTAL_URL}/api/auth/oidc/handler/frame' in portal_client.get('redirectUris', []),
      'The realm needs the confidential portal client with the OIDC callback of the portal')
check(any(m.get('config', {}).get('claim.value') == 'person' for m in portal_client.get('protocolMappers', [])),
      'portal: its tokens must say client_kind=person (people, never agents)')
sync = subprocess.run(['python3', str(ROOT / 'platform/access/identity/sync-organization.py'), '--check'],
                      capture_output=True, text=True)
check(sync.returncode == 0, sync.stdout.strip() or sync.stderr.strip())
templates = [ROOT / 'platform/access/portal/catalog/templates/environment/template.yaml',
             ROOT / 'platform/access/portal/catalog/templates/service/template.yaml',
             *sorted((ROOT / 'platform/capabilities/golden-paths').glob('*/template.yaml'))]
for template in templates:
    text = template.read_text()
    if 'action: platform:' in text:
        check(re.search(r'formDecorators:\s*\n\s*- id: platform-identity', text) is not None,
              f'{template.relative_to(ROOT)}: declare formDecorators: [{{id: platform-identity}}]')
generated = (ROOT / 'platform/access/portal/plugins/platform-backend/src/capabilities.ts').read_text()
check(generated.count("formDecorators: [{ id: 'platform-identity' }]") >= 2,
      'capabilities.ts: generated templates must declare the platform-identity form decorator')
secret = re.compile(r"TOKEN_SECRET = '([a-zA-Z]+)'")
front = secret.search((ROOT / 'platform/access/portal/plugins/platform/src/identity.tsx').read_text())
back = secret.search((ROOT / 'platform/access/portal/plugins/platform-backend/src/scaffolder.ts').read_text())
check(front and back and front.group(1) == back.group(1),
      'The portal frontend and backend must agree on the name of the token secret')

if errors:
    raise SystemExit('\n'.join(errors))
print('Repository paths, shell/Python syntax, skill links and MCP adapters are consistent.')
