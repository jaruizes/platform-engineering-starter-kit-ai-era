#!/usr/bin/env python3
"""Run a check and persist its exit code so the gate can report all failures."""
import json
import subprocess
import sys
from pathlib import Path

name, *command = sys.argv[1:]
result = subprocess.run(command, check=False)
path = Path(".platform/quality/command-status.json")
statuses = json.loads(path.read_text()) if path.exists() else {}
statuses[name] = result.returncode
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(statuses, indent=2, sort_keys=True) + "\n")
sys.exit(0)
