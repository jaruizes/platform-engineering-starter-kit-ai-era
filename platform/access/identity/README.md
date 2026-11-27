# Identity (Keycloak)

Who people and agents are. One Keycloak realm, `platform`, issues the tokens
that every channel sends to the [platform API](../../capabilities/api): the
platform MCP server (agents), [`platformctl`](../cli) (people and Codex) and
the portal (people). The design is in
[identity and access](../../../docs/identity-and-access.md).

| In the realm | What it is |
|---|---|
| Groups `platform-team`, `checkout`, `payments`, `retail` | Teams, with the names of the catalog groups. A token carries them in `groups` |
| Realm roles `developer`, `approver` | Roles. An approver decides on agents' requests of their teams (platform-team approvers: every team), never on one made on their own behalf |
| Ten people: `ana`, `pablo`, `marta`, `carlos`, `luis`, `sofia`, `elena`, `diego`, `irene`, `nora` | The sample organization of the demo, in [`organization.yaml`](organization.yaml) and described in [users and teams](../../../examples/scenarios/example/demo/users-and-teams.md). Password `demo` locally (`DEMO_PASSWORD`), random on AWS |
| Client `portal` | Confidential client (authorization code) for Backstage: people sign in, and the portal sends their token to the platform API. Its only redirect is `${PORTAL_URL}/api/auth/oidc/handler/frame` |
| Clients `claude-code`, `gemini-cli` | Public clients (authorization code with PKCE) for agents acting for the person who signs in. The client is the agent identity (`azp`) |
| Client `codex` | Public client with device flow: `platformctl.py login --client codex` gets a token for Codex |
| Client `platformctl` | Public client with device flow, for people in the terminal |
| Clients `ci-agent`, `capability-tests` | Confidential clients (client credentials): autonomous agents of one owner team (`owner_team` claim). `make demo-agent` is `ci-agent` of checkout |

Every client adds three claims to its access tokens: the audience `platform`
(the platform API only accepts tokens for it), the person's `groups`, and
`client_kind` (`agent` or `person`): a client that says nothing is treated as
an agent, so the agent guardrails apply.

Tokens live 5 minutes (Codex: 1 hour, because it does not refresh them).
Disabling a person, an agent client or a session in Keycloak takes effect on
the next refresh.

## The sample organization

[`organization.yaml`](organization.yaml) is the one place for teams, people and roles. [`sync-organization.py`](sync-organization.py) writes it into the realm (groups and users; clients are left as they are) and into the portal catalog ([`org.yaml`](../portal/catalog/org.yaml)), so every sign-in resolves to a catalog user with the same teams. `python3 deploy/check-repository.py` fails if they drift apart.

```bash
python3 platform/access/identity/sync-organization.py
```

## Run it

`make up` deploys it ([`deploy/keycloak.yaml`](deploy/keycloak.yaml)) on
<http://localhost:8180> and imports [`realm/platform-realm.json`](realm/platform-realm.json)
on every start (development mode, with its embedded database: sessions do not
survive a restart). Secrets in `platform-system`: `keycloak-admin` (the `admin`
console user), `identity-demo` (password of the sample people), `portal-oidc-client`
(the portal's client secret, shared with the portal), `ci-agent-client` and
`capability-tests-client`. `PORTAL_URL` is where people reach the portal
(`http://localhost:7007`; on AWS, the load balancer).

The issuer people, agents and the platform API agree on is the public address
(`KC_HOSTNAME`, `http://localhost:8180/realms/platform` locally); pods reach
Keycloak inside the cluster and still get tokens for that issuer.

## In a customer

Keycloak brokers the corporate identity provider (Entra ID, Okta, Google):
people sign in with their usual account, and a mapper turns their corporate
groups into the platform teams. Nothing else in the platform changes.
