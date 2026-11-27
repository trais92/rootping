"""Tests für die Namensauflösung über das Betriebssystem (ohne Internet)."""

import pytest

from rootping.net.resolve import ResolveError, resolve_ipv4


async def test_localhost_resolves_to_loopback() -> None:
    assert (await resolve_ipv4("localhost", 2)).startswith("127.")


async def test_reserved_invalid_name_fails() -> None:
    # ".invalid" ist laut RFC 2606 reserviert und wird nie aufgelöst.
    with pytest.raises(ResolveError):
        await resolve_ipv4("rootping-test.invalid", 2)
