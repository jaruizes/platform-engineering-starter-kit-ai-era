#!/usr/bin/env python3
"""Writes the sample organization (organization.yaml) into the Keycloak realm
and the portal catalog, so both always have the same teams and people.

    python3 platform/access/identity/sync-organization.py          # write
    python3 platform/access/identity/sync-organization.py --check  # fail if they drift
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORGANIZATION = HERE / "organization.yaml"
REALM = HERE / "realm" / "platform-realm.json"
CATALOG = ROOT / "platform/access/portal/catalog/org.yaml"
EMAIL_DOMAIN = "starterkit.local"

CATALOG_HEADER = """\
# Sample organization of the demo, generated from
# platform/access/identity/organization.yaml (the Keycloak realm has the same
# teams and people): run platform/access/identity/sync-organization.py after
# changing it. In a real setup this comes from your identity provider.
"""


def load() -> dict:
    org = yaml.safe_load(ORGANIZATION.read_text())
    teams = {t["name"] for t in org["teams"]}
    for person in org["people"]:
        unknown = set(person["teams"]) - teams
        if unknown:
            raise SystemExit(f"{person['name']} is in unknown teams: {', '.join(sorted(unknown))}")
    return org


def realm(org: dict) -> str:
    data = json.loads(REALM.read_text())
    data["groups"] = [{"name": t["name"], "path": f"/{t['name']}"} for t in sorted(org["teams"], key=lambda t: t["name"])]
    machines = [u for u in data["users"] if u.get("serviceAccountClientId")]
    people = []
    for p in org["people"]:
        first, _, last = p["displayName"].partition(" ")
        people.append({
            "username": p["name"], "enabled": True, "emailVerified": True,
            "firstName": first, "lastName": last, "email": f"{p['name']}@{EMAIL_DOMAIN}",
            "groups": [f"/{t}" for t in p["teams"]],
            # Imported users get only the roles listed here, not the realm's
            # default roles. offline_access lets MCP clients such as Claude
            # Code get the refresh token they ask for (scope offline_access).
            "realmRoles": ["offline_access", *p["roles"]],
            "credentials": [{"type": "password", "value": "${DEMO_PASSWORD}", "temporary": False}],
        })
    data["users"] = people + machines
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def catalog(org: dict) -> str:
    docs = []
    for t in org["teams"]:
        members = [p["name"] for p in org["people"] if t["name"] in p["teams"]]
        docs.append({
            "apiVersion": "backstage.io/v1alpha1", "kind": "Group",
            "metadata": {"name": t["name"], "title": t["title"], "description": t["description"]},
            "spec": {"type": "team", "children": [], "members": members},
        })
    for p in org["people"]:
        docs.append({
            "apiVersion": "backstage.io/v1alpha1", "kind": "User",
            "metadata": {"name": p["name"], "description": p["purpose"],
                         "annotations": {"platform.starterkit.dev/roles": ",".join(p["roles"])}},
            "spec": {"profile": {"displayName": p["displayName"], "email": f"{p['name']}@{EMAIL_DOMAIN}"},
                     "memberOf": list(p["teams"])},
        })
    body = "---\n".join(yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=100) for d in docs)
    return CATALOG_HEADER + body


def main() -> int:
    org = load()
    wanted = {REALM: realm(org), CATALOG: catalog(org)}
    if "--check" in sys.argv:
        stale = [str(p.relative_to(ROOT)) for p, text in wanted.items() if p.read_text() != text]
        if stale:
            print("Out of date with organization.yaml (run platform/access/identity/sync-organization.py): "
                  + ", ".join(stale))
            return 1
        return 0
    for path, text in wanted.items():
        path.write_text(text)
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
