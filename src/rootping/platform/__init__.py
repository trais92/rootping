"""Alles, was vom Betriebssystem abhängt, an einer Stelle.

Der Rest von RootPing ruft nur die Funktionen dieses Pakets auf und weiß nicht,
ob er unter Windows oder Linux läuft. Beim Import wird das passende Modul
gewählt:

- ``linux.py``: Ping über ``icmplib`` (ohne root), Karten aus ``/proc/net/route``
  und ``/sys/class/net``
- ``windows.py``: Ping über ``IcmpSendEcho2`` (ohne Admin), Karten über
  ``GetAdaptersAddresses`` und ``GetBestRoute``

Beide Module bieten dieselben drei Funktionen: ``echo``, ``current_network`` und
``ping_permission_problem``. Welche Karte der Heimrouter ist und ob ein VPN
läuft, entscheidet für beide :func:`rootping.platform.common.choose_network`.
Hintergrund: ADR-002, ADR-006, ADR-012, ``docs/ping.md`` und ``docs/netzwerk.md``.
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
current_network = _impl.current_network
ping_permission_problem = _impl.ping_permission_problem

__all__ = [
    "NetworkContext",
    "PingPermissionError",
    "current_network",
    "echo",
    "ping_permission_problem",
]
