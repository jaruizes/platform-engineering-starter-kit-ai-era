"""The console is a read-only backup screen: decisions go through the platform API."""

from platform_api import console


def test_the_console_only_reads():
    methods = {m for route in console.app.routes for m in (getattr(route, "methods", None) or ())}
    assert methods <= {"GET", "HEAD"}
    assert "Your name" not in console.INDEX and "platformctl approve" in console.INDEX
