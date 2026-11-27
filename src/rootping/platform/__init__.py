"""Alles, was vom Betriebssystem abhängt, an einer Stelle.

Der Rest von RootPing ruft nur die Funktionen dieses Pakets auf und weiß nicht,
ob er unter Windows oder Linux läuft. Beim Import wird das passende Modul
gewählt:

- ``linux.py``: Ping über ``icmplib`` (ohne root), Router aus ``/proc/net/route``
- ``windows.py``: Ping über ``IcmpSendEcho2`` (ohne Admin), Router über ``GetBestRoute``

Beide Module bieten dieselben drei Funktionen: ``echo``, ``default_route`` und
``ping_permission_problem``. Hintergrund: ADR-002, ADR-006 und ``docs/ping.md``.
"""

import sys

from rootping.platform.common import NetworkContext, PingPermissionError

if sys.platform == "win32":
    from rootping.platform import windows as _impl
elif sys.platform == "linux":
    from rootping.platform import linux as _impl
else:  # pragma: no cover - macOS u. a. sind bewusst nicht in v1 (projektplan.md)
    raise ImportError(f"RootPing unterstützt Windows und Linux, nicht {sys.platform!r}.")

echo = _impl.echo
default_route = _impl.default_route
ping_permission_problem = _impl.ping_permission_problem

__all__ = [
    "NetworkContext",
    "PingPermissionError",
    "default_route",
    "echo",
    "ping_permission_problem",
]
