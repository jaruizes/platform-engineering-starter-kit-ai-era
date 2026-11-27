"""The Git provider of the platform (Gitea in the kit).

The platform creates repositories for code Golden Paths and opens pull
requests with capability definitions through the provider's API, with the
platform's own account. Another provider (GitHub, GitLab) is another
implementation of these two operations.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .golden_paths import RenderedFile


class GitServerError(RuntimeError):
    """The Git server refused or failed an operation."""


class RepositoryExists(GitServerError):
    """There is already a repository with that name."""


@dataclass
class GitServer:
    # Where the platform reaches the Git server (inside the cluster).
    api_url: str
    # Where people and agents browse and clone (the public address).
    public_url: str
    owner: str
    username: str
    password: str

    @classmethod
    def from_environment(cls) -> "GitServer":
        public = os.environ.get("GIT_URL", "http://localhost:3000").rstrip("/")
        return cls(
            api_url=os.environ.get("GIT_API_URL", public).rstrip("/"),
            public_url=public,
            owner=os.environ.get("GIT_OWNER", "platform"),
            username=os.environ.get("GIT_USERNAME", ""),
            password=os.environ.get("GIT_PASSWORD", ""),
        )

    # --- HTTP API --------------------------------------------------------------

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if not (self.username and self.password):
            raise GitServerError("The platform has no Git server account (GIT_USERNAME, GIT_PASSWORD).")
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        request = urllib.request.Request(
            f"{self.api_url}/api/v1{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                return json.loads(payload) if payload else None
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:300]
            if err.code == 409:
                raise RepositoryExists(detail) from err
            if err.code == 404 and method == "GET":
                return None
            raise GitServerError(f"{method} {path} answered {err.code}: {detail}") from err
        except urllib.error.URLError as err:
            raise GitServerError(f"The Git server is not reachable: {err.reason}") from err

    def repository_url(self, name: str) -> str:
        return f"{self.public_url}/{self.owner}/{name}"

    def _push_remote(self, name: str) -> str:
        scheme, rest = self.api_url.split("://", 1)
        user, password = quote(self.username, safe=""), quote(self.password, safe="")
        return f"{scheme}://{user}:{password}@{rest}/{self.owner}/{quote(name)}.git"

    # --- Code Golden Paths -----------------------------------------------------

    def create_repository(self, name: str, description: str, files: list[RenderedFile], message: str,
                          author: tuple[str, str] = ("Platform", "platform@starterkit.local")) -> str:
        """Creates the repository and pushes the files as its first commit on main."""
        if self._request("GET", f"/repos/{self.owner}/{quote(name)}") is not None:
            raise RepositoryExists(f"The repository {self.owner}/{name} already exists.")
        self._request("POST", f"/orgs/{self.owner}/repos", {
            "name": name, "description": description, "default_branch": "main", "private": False,
        })
        with tempfile.TemporaryDirectory(prefix="golden-path-") as work:
            root = Path(work)
            for f in files:
                target = root / f.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(f.content)
                if f.executable:
                    target.chmod(0o755)
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1],
                "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1],
                "GIT_TERMINAL_PROMPT": "0", "HOME": work,
            }
            self._git(root, env, "init", "-q", "-b", "main")
            self._git(root, env, "add", "-A")
            self._git(root, env, "commit", "-q", "-m", message)
            self._git(root, env, "push", "-q", self._push_remote(name), "main")
        return self.repository_url(name)

    def _git(self, cwd: Path, env: dict[str, str], *args: str) -> None:
        result = subprocess.run(["git", "-c", "credential.helper=", *args], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            # Never echo the push URL, it carries the password.
            output = (result.stderr or result.stdout).replace(self.password, "***")
            raise GitServerError(f"git {args[0]} failed: {output.strip()[:300]}")

    # --- Capability proposals --------------------------------------------------

    def propose_file(self, repository: str, path: str, content: str, title: str, body: str,
                     author: tuple[str, str]) -> dict[str, Any]:
        """Opens a pull request that adds or changes one file of a repository."""
        repo = f"/repos/{self.owner}/{repository}"
        branch = f"capability/{Path(path).parent.name}-{base36(int(time.time() * 1000))}"
        existing = self._request("GET", f"{repo}/contents/{quote(path)}?ref=main")
        payload: dict[str, Any] = {
            "content": base64.b64encode(content.encode()).decode(),
            "message": title,
            "branch": "main",
            "new_branch": branch,
            "author": {"name": author[0], "email": author[1]},
            "committer": {"name": author[0], "email": author[1]},
        }
        if existing and existing.get("sha"):
            payload["sha"] = existing["sha"]
        self._request("PUT" if "sha" in payload else "POST", f"{repo}/contents/{quote(path)}", payload)
        pull = self._request("POST", f"{repo}/pulls", {"head": branch, "base": "main", "title": title, "body": body})
        return {"number": pull["number"], "url": pull["html_url"], "title": pull["title"]}


def base36(number: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while number:
        number, rest = divmod(number, 36)
        out = digits[rest] + out
    return out or "0"
