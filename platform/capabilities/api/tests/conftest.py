from pathlib import Path

import pytest
import yaml

from platform_api import golden_paths
from platform_api.golden_paths import RenderedFile

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def catalog():
    return golden_paths.catalog()


@pytest.fixture
def postgres_definition():
    return yaml.safe_load((ROOT / "platform/capabilities/infrastructure/postgres-database/capability.yaml").read_text())


class FakeGit:
    """Records what the platform asks the Git server to do."""

    def __init__(self):
        self.repositories: dict[str, tuple[str, list[RenderedFile], str]] = {}
        self.proposals: list[dict] = []

    def repository_url(self, name):
        return f"http://localhost:3000/platform/{name}"

    def create_repository(self, name, description, files, message, author=None):
        from platform_api.git_server import RepositoryExists

        if name in self.repositories:
            raise RepositoryExists(f"The repository platform/{name} already exists.")
        self.repositories[name] = (description, files, message)
        return self.repository_url(name)

    def propose_file(self, repository, path, content, title, body, author):
        self.proposals.append(dict(repository=repository, path=path, content=content, title=title,
                                   body=body, author=author))
        number = len(self.proposals)
        return {"number": number, "url": f"http://localhost:3000/platform/{repository}/pulls/{number}", "title": title}


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, action, message, subject, actor, kind, warning=False):
        self.events.append(dict(action=action, message=message, subject=subject, actor=actor, kind=kind,
                                warning=warning))


@pytest.fixture
def platform(catalog):
    from platform_api.service import Platform

    environments = {"checkout-dev"}
    services = {("orders-service", "checkout-dev")}
    return Platform(
        git=FakeGit(),
        state=golden_paths.State(lambda e: e in environments, lambda s, e: (s, e) in services),
        record=Recorder(),
        catalog=catalog,
    )
