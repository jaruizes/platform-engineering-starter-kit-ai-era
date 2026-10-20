---
name: postgres-database
description: Use when a service needs a PostgreSQL or relational database in an environment, for example to test a change. Requests it through the platform instead of running a database by hand.
---

# PostgreSQL databases

The platform offers PostgreSQL databases as a capability (`PostgresDatabase`).
Use it instead of writing a Deployment, a Helm chart or a docker-compose
file for a database.

1. You need an environment first. If the user has none, request one with
   `request_environment` in the `platform` MCP server.
2. Call `request_capability` with `capability: PostgresDatabase`, the
   environment, a name (for example `orders-db`) and, if needed,
   `parameters: {"size": "small", "version": "17"}`.
3. Ask for `small` unless the user says why they need more. Medium and large
   need a person to approve them: if you get `pending_approval`, tell the
   user and give them the approval id.
4. When it is ready (`get_capability_request`), the service connects with the
   Secret `<name>-connection` (`host`, `port`, `database`, `username`,
   `password`). Mount it as environment variables; never copy the password
   into code or configuration files.

Do not use it for production data: it lives and dies with the environment,
with no backups.
