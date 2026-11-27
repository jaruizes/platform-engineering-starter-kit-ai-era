"""The Git server client pushes the rendered files as the first commit,
keeping executable bits, and never leaks its password."""

import subprocess

import pytest

from platform_api.git_server import GitServer, GitServerError, RepositoryExists
from platform_api.golden_paths import RenderedFile


def server(monkeypatch, tmp_path, existing=False):
    git = GitServer("http://gitea:3000", "http://localhost:3000", "platform", "platform-admin", "pa55/word")
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET":
            return {"name": "x"} if existing else None
        return {}

    monkeypatch.setattr(git, "_request", request)
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    monkeypatch.setattr(git, "_push_remote", lambda name: str(bare))
    return git, calls, bare


def test_creates_the_repository_and_pushes_the_first_commit(monkeypatch, tmp_path):
    git, calls, bare = server(monkeypatch, tmp_path)
    url = git.create_repository("loyalty-points", "Loyalty", [
        RenderedFile("README.md", b"# Loyalty\n"),
        RenderedFile("mvnw", b"#!/bin/sh\n", executable=True),
    ], message="Create loyalty-points")
    assert url == "http://localhost:3000/platform/loyalty-points"
    assert ("POST", "/orgs/platform/repos",
            {"name": "loyalty-points", "description": "Loyalty", "default_branch": "main", "private": False}) in calls
    tree = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "main"], capture_output=True, text=True).stdout
    assert "100755 blob" in [line for line in tree.splitlines() if line.endswith("mvnw")][0]
    assert "README.md" in tree


def test_does_not_overwrite_an_existing_repository(monkeypatch, tmp_path):
    git, _, _ = server(monkeypatch, tmp_path, existing=True)
    with pytest.raises(RepositoryExists):
        git.create_repository("loyalty-points", "Loyalty", [], message="x")


def test_push_errors_hide_the_password(monkeypatch, tmp_path):
    git, _, _ = server(monkeypatch, tmp_path)
    monkeypatch.setattr(git, "_push_remote", lambda name: "http://platform-admin:pa55/word@127.0.0.1:9/x.git")
    with pytest.raises(GitServerError) as failed:
        git.create_repository("loyalty-points", "Loyalty", [RenderedFile("a", b"a")], message="x")
    assert "pa55/word" not in str(failed.value)


def test_needs_an_account():
    with pytest.raises(GitServerError, match="no Git server account"):
        GitServer("http://gitea:3000", "http://localhost:3000", "platform", "", "")._request("GET", "/version")
