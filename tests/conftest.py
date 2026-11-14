import urllib.request

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may reach the network: sources must be given a fake opener."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("network access attempted in a test")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
