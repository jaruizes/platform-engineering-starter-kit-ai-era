# Identity (Keycloak)

Who people and agents are. One Keycloak realm, `platform`, issues the tokens
that every channel sends to the [platform API](../../capabilities/api): the
platform MCP server (agents), [`platformctl`](../cli) (people and Codex) and,
from increment B, the portal. The design is in
[identity and access](../../../docs/identity-and-access.md).

| In the realm | What it is |
|---|---|
| Groups `checkout`, `payments`, `platform-team` | Teams, with the names of the catalog groups. A token carries them in `groups` |
| Realm roles `developer`, `approver` | Roles. Approvals by role arrive with increment B |
| People `ana` (platform-team, approver), `marta` (checkout), `luis` (payments, approver) | The sample organization of the demo. Password `demo` locally (`DEMO_PASSWORD`), random on AWS |
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

## Run it

`make up` deploys it ([`deploy/keycloak.yaml`](deploy/keycloak.yaml)) on
<http://localhost:8180> and imports [`realm/platform-realm.json`](realm/platform-realm.json)
on every start (development mode, with its embedded database: sessions do not
survive a restart). Secrets in `platform-system`: `keycloak-admin` (the `admin`
console user), `identity-demo` (password of the sample people), `ci-agent-client`
and `capability-tests-client`.

The issuer people, agents and the platform API agree on is the public address
(`KC_HOSTNAME`, `http://localhost:8180/realms/platform` locally); pods reach
Keycloak inside the cluster and still get tokens for that issuer.

## In a customer

Keycloak brokers the corporate identity provider (Entra ID, Okta, Google):
people sign in with their usual account, and a mapper turns their corporate
groups into the platform teams. Nothing else in the platform changes.
