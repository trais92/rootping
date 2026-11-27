"""Linux-spezifischer Teil: Ping ohne root und Router-Erkennung.

- **Ping:** über den ICMP-Datagram-Socket des Kernels mit ``icmplib``
  (``privileged=False``). Das braucht keine root-Rechte, aber der Kernel muss
  die Gruppe des Benutzers in ``net.ipv4.ping_group_range`` erlauben (Befund B3).
- **Router:** aus ``/proc/net/route`` gelesen, ohne Unterprozess.

Hintergrund: ADR-006 und ``docs/ping.md``.
"""

import os
import socket
import struct
import sys
from pathlib import Path

if sys.platform != "linux":  # pragma: no cover - Schutz vor falscher Verwendung
    raise ImportError("rootping.platform.linux läuft nur unter Linux.")

import icmplib

from rootping.platform.common import NetworkContext, PingPermissionError

PROC_NET_ROUTE = Path("/proc/net/route")
PING_GROUP_RANGE = Path("/proc/sys/net/ipv4/ping_group_range")

# Flags aus <linux/route.h>: Route ist aktiv (RTF_UP) und führt über einen Router (RTF_GATEWAY).
_RTF_UP = 0x0001
_RTF_GATEWAY = 0x0002

# Empfohlener Bereich: derselbe Wert, den systemd auf den meisten Distributionen setzt.
_RECOMMENDED_RANGE = "0 2147483647"


async def echo(address: str, timeout: float) -> float | None:
    """Sendet ein einzelnes ICMP-Echo und wartet auf die Antwort.

    Args:
        address: IPv4-Adresse des Ziels.
        timeout: Sekunden, die höchstens auf die Antwort gewartet wird.

    Returns:
        Antwortzeit in Millisekunden oder ``None``, wenn keine Antwort kam
        (verloren, Zeitüberschreitung, Ziel nicht erreichbar, kein Netz).

    Raises:
        PingPermissionError: Wenn der Kernel den Ping-Socket nicht erlaubt.
    """
    try:
        # icmplib nimmt laut Doku auch Kommazahlen als timeout; Pyright leitet aus dem
        # Standardwert (2) nur int ab.
        host = await icmplib.async_ping(
            address,
            count=1,
            timeout=timeout,  # pyright: ignore[reportArgumentType]
            privileged=False,
        )
    except icmplib.SocketPermissionError as err:
        raise PingPermissionError(_permission_help()) from err
    # Fehler beim Senden (z. B. kein Netz) fängt icmplib selbst ab und zählt sie als verloren.
    return float(host.avg_rtt) if host.packets_received else None


def ping_permission_problem() -> str | None:
    """Prüft, ob dieser Benutzer ohne root pingen darf.

    Öffnet probeweise einen ICMP-Datagram-Socket. Das ist die eigentliche
    Prüfung; ``ping_group_range`` wird nur für die Erklärung gelesen.

    Returns:
        ``None``, wenn Ping möglich ist, sonst eine verständliche Erklärung mit Abhilfe.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
    except PermissionError:
        return _permission_help()
    sock.close()
    return None


def default_route() -> NetworkContext | None:
    """Ermittelt Router und Netzwerkkarte der Standardroute.

    Returns:
        Den Netzwerk-Kontext oder ``None``, wenn es keine Standardroute gibt (kein Netz).
    """
    try:
        text = PROC_NET_ROUTE.read_text(encoding="ascii")
    except OSError:
        return None
    return parse_proc_net_route(text)


def parse_proc_net_route(text: str) -> NetworkContext | None:
    """Liest die Standardroute aus dem Inhalt von ``/proc/net/route``.

    Die Datei hat eine Kopfzeile und dann eine Zeile pro Route. Adressen stehen
    hexadezimal in der Byte-Reihenfolge des Kernels (Little Endian), z. B.
    ``0102A8C0`` für ``192.168.2.1``. Die Standardroute hat Ziel und Maske
    ``00000000``. Gibt es mehrere, gewinnt die mit der kleinsten Metrik.

    Args:
        text: Inhalt von ``/proc/net/route``.

    Returns:
        Den Netzwerk-Kontext oder ``None``, wenn keine Standardroute über einen Router führt.
    """
    best: tuple[int, NetworkContext] | None = None
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8:
            continue
        iface, destination, gateway_hex, flags_hex, _refcnt, _use, metric, mask = fields[:8]
        flags = int(flags_hex, 16)
        is_default = destination == "00000000" and mask == "00000000"
        if not is_default or flags & (_RTF_UP | _RTF_GATEWAY) != (_RTF_UP | _RTF_GATEWAY):
            continue
        gateway = socket.inet_ntoa(struct.pack("<L", int(gateway_hex, 16)))
        candidate = (int(metric), NetworkContext(gateway=gateway, interface=iface))
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best[1] if best else None


def _permission_help() -> str:
    """Erklärt, warum Ping ohne root nicht geht, und wie man es freigibt."""
    try:
        current = " ".join(PING_GROUP_RANGE.read_text(encoding="ascii").split())
    except OSError:
        current = "unbekannt"
    groups = sorted({os.getgid(), *os.getgroups()})
    return (
        "Ping ohne root-Rechte ist auf diesem System nicht freigegeben.\n"
        "Der Linux-Kernel erlaubt Ping-Sockets nur den Gruppen im Bereich "
        f"net.ipv4.ping_group_range (aktuell: {current}; deine Gruppen: "
        f"{', '.join(map(str, groups))}).\n\n"
        "Abhilfe (einmalig, mit Admin-Rechten):\n"
        f'  sudo sysctl -w net.ipv4.ping_group_range="{_RECOMMENDED_RANGE}"\n'
        "Dauerhaft (übersteht einen Neustart):\n"
        f"  echo 'net.ipv4.ping_group_range = {_RECOMMENDED_RANGE}' "
        "| sudo tee /etc/sysctl.d/99-rootping.conf\n\n"
        "Das ist dieselbe Einstellung, die systemd auf den meisten Distributionen setzt. "
        "RootPing braucht danach keine root-Rechte. Details: docs/ping.md"
    )
