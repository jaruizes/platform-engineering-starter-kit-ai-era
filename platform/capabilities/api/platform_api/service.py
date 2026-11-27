"""The operations of the platform API, independent of any channel.

The HTTP server (server.py) exposes them; the portal, the platform MCP server
and the CLI call them. Each operation records who asked for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import golden_paths, proposals
from .git_server import GitServer, GitServerError

Recorder = Callable[..., None]

PLATFORM_REPOSITORY = "platform-starter-kit"


class Forbidden(PermissionError):
    """The requester may not do this."""


@dataclass
class Platform:
    git: GitServer
    state: golden_paths.State
    record: Recorder
    catalog: dict[str, golden_paths.CodeGoldenPath]

    # --- Code Golden Paths -----------------------------------------------------

    def list_golden_paths(self) -> list[dict[str, Any]]:
        return [path.describe() for path in self.catalog.values()]

    def create_repository(self, golden_path: str, parameters: dict[str, Any], requester: str) -> dict[str, Any]:
        """Runs a code Golden Path: renders its skeleton and creates the repository."""
        path = self.catalog.get(golden_path)
        if path is None:
            raise golden_paths.InvalidRequest(
                f"There is no code Golden Path '{golden_path}'. Available: {', '.join(self.catalog) or 'none'}.")
        resolved = golden_paths.resolve_parameters(path, parameters, self.state)
        values = golden_paths.render_values(path, resolved, requester)
        repository = golden_paths.render_repository(path, resolved)
        name = repository.get("name") or resolved["name"]
        files = golden_paths.render_skeleton(path, values)
        try:
            url = self.git.create_repository(
                name, repository.get("description", ""), files,
                message=f"Create {name} from the {path.name} Golden Path\n\nRequested-by: {requester}")
        except GitServerError as failed:
            self.record("RequestFailed", f"{requester} could not create {name} ({path.name}): {failed}",
                        name, actor=requester, kind="Component", warning=True)
            raise
        team = resolved.get("owner", "").split("/")[-1]
        self.record("RequestAccepted",
                    f"{requester} created {name} for team {team} from the {path.title} Golden Path",
                    name, actor=requester, kind="Component")
        return {
            "status": "created",
            "goldenPath": path.name,
            "name": name,
            "repository": url,
            "cloneUrl": f"{url}.git",
            "catalogEntity": f"component:default/{name}",
            "environment": resolved.get("environment") or None,
            "requestedBy": requester,
        }

    # --- Capability proposals --------------------------------------------------

    def propose_capability(self, definition: dict[str, Any], requester: str,
                           requester_name: str | None = None) -> dict[str, Any]:
        """Validates a capability definition and opens its pull request."""
        if requester.startswith("agent:"):
            # People decide what the platform needs; agents build it.
            raise Forbidden("Capability definitions are proposed by people on the platform team, not by agents.")
        if not golden_paths.REQUESTER.match(requester):
            raise golden_paths.InvalidRequest("requester must be user:default/<name>.")
        proposals.validate(definition)
        name = definition["metadata"]["name"]
        person = requester_name or requester
        title = f"New platform capability: {definition['metadata']['title']}"
        pull = self.git.propose_file(
            PLATFORM_REPOSITORY,
            proposals.DEFINITION_PATH.format(name=name),
            proposals.file_content(definition),
            title,
            proposals.pull_request_body(definition, person),
            author=(person, "platform@starterkit.local"),
        )
        self.record("CapabilityProposed", f"{person} proposed the capability {name} (pull request #{pull['number']})",
                    name, actor=requester, kind="CapabilityDefinition")
        return {
            "status": "proposed",
            "name": name,
            "pullRequestUrl": pull["url"],
            "pullRequestNumber": pull["number"],
            "entityRef": f"resource:default/{name}.pr-{pull['number']}",
        }
