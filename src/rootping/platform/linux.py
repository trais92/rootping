"""Linux-spezifischer Teil: Ping ohne root und Router-Erkennung.

- **Ping:** über den ICMP-Datagram-Socket des Kernels mit ``icmplib``
  (``privileged=False``). Das braucht keine root-Rechte, aber der Kernel muss
  die Gruppe des Benutzers in ``net.ipv4.ping_group_range`` erlauben (Befund B3).
- **Router und VPN:** aus ``/proc/net/route``, ``/sys/class/net`` und der
  Routing-Entscheidung des Kernels, ohne Unterprozess (``docs/netzwerk.md``).

Hintergrund: ADR-006 und ``docs/ping.md``.
"""

import fcntl
import os
import socket
import struct
import sys
from pathlib import Path

if sys.platform != "linux":  # pragma: no cover - Schutz vor falscher Verwendung
    raise ImportError("rootping.platform.linux läuft nur unter Linux.")

import icmplib

from rootping.platform.common import Interface, NetworkContext, PingPermissionError, choose_network

PROC_NET_ROUTE = Path("/proc/net/route")
PING_GROUP_RANGE = Path("/proc/sys/net/ipv4/ping_group_range")
SYS_CLASS_NET = Path("/sys/class/net")

# Öffentliche Adresse, um die aktive Route zu erfragen (es wird nichts gesendet).
_ROUTE_PROBE_ADDRESS = "1.1.1.1"

# ioctl-Nummer aus <linux/sockios.h>: IPv4-Adresse einer Karte abfragen.
_SIOCGIFADDR = 0x8915

# Karten-Typen aus <linux/if_arp.h>, die Tunnel sind: PPP (512), IPIP (768),
# SIT (776), GRE (778), IP6GRE (823) und "keine Hardware" (65534: tun, WireGuard).
_TUNNEL_ARP_TYPES = frozenset({512, 768, 776, 778, 823, 65534})

# Metrik für Karten ohne eigene Standardroute (werden nie als Heimrouter gewählt).
_NO_ROUTE_METRIC = 1_000_000

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


def current_network() -> NetworkContext | None:
    """Ermittelt Heimrouter, Netzwerkkarte und ob ein VPN aktiv ist.

    Rohdaten: Standard-Gateways aus ``/proc/net/route``, die Karte, über die
    eine Verbindung ins Internet ginge (:func:`_active_interface`), und ob eine
    Karte ein Tunnel ist (:func:`is_tunnel`). Die Entscheidung trifft
    :func:`~rootping.platform.common.choose_network`.

    Returns:
        Den Netzwerk-Kontext oder ``None`` ohne Netz. DNS-Server pro Karte
        liefert Linux nicht einfach; sie bleiben leer (``docs/netzwerk.md``).
    """
    try:
        gateways = parse_default_gateways(PROC_NET_ROUTE.read_text(encoding="ascii"))
    except OSError:
        return None
    names = [name for _, name in socket.if_nameindex() if name != "lo"]
    interfaces = [
        Interface(
            name=name,
            gateway=gateways[name][0] if name in gateways else None,
            metric=gateways[name][1] if name in gateways else _NO_ROUTE_METRIC,
            is_tunnel=is_tunnel(name),
        )
        for name in names
    ]
    return choose_network(interfaces, _active_interface())


def parse_default_gateways(text: str) -> dict[str, tuple[str, int]]:
    """Liest die Standard-Gateways aus dem Inhalt von ``/proc/net/route``.

    Die Datei hat eine Kopfzeile und dann eine Zeile pro Route. Adressen stehen
    hexadezimal in der Byte-Reihenfolge des Kernels (Little Endian), z. B.
    ``0102A8C0`` für ``192.168.2.1``. Eine Standardroute hat Ziel und Maske
    ``00000000``. Hat eine Karte mehrere, gewinnt die mit der kleinsten Metrik.

    Hinweis: VPNs wie WireGuard legen ihre Standardroute oft in eine eigene
    Routing-Tabelle, die hier nicht erscheint. Deshalb wird die aktive Karte
    zusätzlich mit :func:`_active_interface` bestimmt.

    Args:
        text: Inhalt von ``/proc/net/route``.

    Returns:
        Karte → (Gateway-Adresse, Metrik), nur für aktive Routen über einen Router.
    """
    result: dict[str, tuple[str, int]] = {}
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
        if iface not in result or int(metric) < result[iface][1]:
            result[iface] = (gateway, int(metric))
    return result


def is_tunnel(name: str) -> bool:
    """Prüft, ob eine Netzwerkkarte ein VPN- bzw. Tunnel-Adapter ist.

    Erkennt Karten ohne Ethernet-Hardware (WireGuard, tun, PPP, GRE …) am
    Typ in ``/sys/class/net/<name>/type`` und TAP-Karten an ``tun_flags``.

    Args:
        name: Name der Karte, z. B. ``"wg0"``.

    Returns:
        ``True`` für Tunnel-Adapter.
    """
    folder = SYS_CLASS_NET / name
    if (folder / "tun_flags").exists():
        return True
    try:
        arp_type = int((folder / "type").read_text(encoding="ascii").strip())
    except OSError, ValueError:
        return False
    return arp_type in _TUNNEL_ARP_TYPES


def _active_interface() -> str | None:
    """Findet die Karte, über die eine Verbindung ins Internet gerade ginge.

    Trick ohne Unterprozess: Ein UDP-Socket wird mit einer öffentlichen Adresse
    „verbunden“. Dabei wird kein Paket gesendet, aber der Kernel wählt die
    Absenderadresse nach seinen Routing-Regeln, auch nach den eigenen Tabellen
    von VPNs. Die Karte mit dieser Adresse ist die aktive.

    Returns:
        Name der Karte oder ``None``, wenn es keine Route ins Internet gibt.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((_ROUTE_PROBE_ADDRESS, 53))
            source = probe.getsockname()[0]
    except OSError:
        return None
    for _, name in socket.if_nameindex():
        if _interface_address(name) == source:
            return name
    return None


def _interface_address(name: str) -> str | None:
    """Gibt die IPv4-Adresse einer Karte zurück (``ioctl SIOCGIFADDR``) oder ``None``."""
    request = struct.pack("256s", name.encode("ascii", errors="replace")[:15])
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            answer = fcntl.ioctl(sock.fileno(), _SIOCGIFADDR, request)
    except OSError:
        return None
    return socket.inet_ntoa(answer[20:24])


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
