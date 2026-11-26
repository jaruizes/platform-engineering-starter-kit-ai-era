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
    'platform/control-plane', 'platform/capabilities', 'platform/governance',
    'platform/delivery', 'interfaces/portal', 'interfaces/mcp',
    'engineering/standards', 'engineering/golden-paths', 'agents/skills',
    'agents/instructions', 'agents/clients', 'examples/scenarios', 'bootstrap',
):
    check((ROOT / folder).is_dir(), f'Missing responsibility directory: {folder}')

for folder in ('.claude/skills', '.agents/skills', '.gemini/skills'):
    check((ROOT / folder).resolve() == ROOT / 'agents/skills', f'{folder} must link to the shared skills')

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

for capability in (ROOT / 'platform/capabilities').glob('*/capability.yaml'):
    skill = capability.parent / 'SKILL.md'
    check(skill.is_symlink(), f'{skill.relative_to(ROOT)} must link to the canonical skill')
    check(skill.resolve() == ROOT / 'agents/skills' / capability.parent.name / 'SKILL.md',
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

if errors:
    raise SystemExit('\n'.join(errors))
print('Repository paths, shell/Python syntax, skill links and MCP adapters are consistent.')
