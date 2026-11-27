"""Windows-spezifischer Teil: Ping ohne Adminrechte und Router-Erkennung.

Beides läuft über ``Iphlpapi.dll``, eine Systembibliothek, die in jedem
Windows steckt. Aufgerufen wird sie mit ``ctypes`` aus der Standardbibliothek,
also ohne Zusatzpaket, ohne Unterprozess und ohne sprachabhängige Textausgabe.

- **Ping:** ``IcmpSendEcho2``, derselbe Weg wie ``ping.exe``. Braucht keine
  Adminrechte, anders als ein Raw Socket (Befund B1, ADR-006). Der Aufruf
  blockiert, deshalb läuft er mit ``asyncio.to_thread`` in einem Hilfs-Thread.
- **Router, VPN, DNS:** ``GetAdaptersAddresses`` liefert alle Adapter mit
  Namen, Typ, Gateway und DNS-Servern; ``GetBestRoute`` sagt, über welchen
  Adapter ein Paket ins Internet ginge. Läuft das über einen VPN-Adapter, ist
  der Heimrouter das Gateway des physischen Adapters (``docs/netzwerk.md``).

Microsoft-Doku: IcmpSendEcho2, ICMP_ECHO_REPLY, GetBestRoute, MIB_IPFORWARDROW,
GetAdaptersAddresses, IP_ADAPTER_ADDRESSES
(Quellen Q11, Q12, Q17 in ``docs/tech-stack.md``). Erklärung: ``docs/ping.md``.
"""

import asyncio
import ctypes
import socket
import struct
import sys
from ctypes import wintypes

if sys.platform != "win32":  # pragma: no cover - Schutz vor falscher Verwendung
    raise ImportError("rootping.platform.windows läuft nur unter Windows.")

from rootping.platform.common import Interface, NetworkContext, PingPermissionError, choose_network

# Inhalt jedes Echos: 32 Bytes wie bei ping.exe.
_PAYLOAD = b"abcdefghijklmnopqrstuvwabcdefghi"

# Statuscode „Erfolg“ in ICMP_ECHO_REPLY.Status (IP_SUCCESS aus ipexport.h).
_IP_SUCCESS = 0

# Beliebige öffentliche Adresse für GetBestRoute. Es wird kein Paket dorthin
# geschickt; Windows schaut nur in der Routing-Tabelle nach, welcher Weg ins
# Internet führt.
_ROUTE_PROBE_ADDRESS = "1.1.1.1"


class _IpOptionInformation(ctypes.Structure):
    """IP_OPTION_INFORMATION aus ipexport.h (Optionen eines Echos)."""

    _fields_ = (
        ("Ttl", ctypes.c_ubyte),
        ("Tos", ctypes.c_ubyte),
        ("Flags", ctypes.c_ubyte),
        ("OptionsSize", ctypes.c_ubyte),
        ("OptionsData", ctypes.c_void_p),
    )


class _IcmpEchoReply(ctypes.Structure):
    """ICMP_ECHO_REPLY aus ipexport.h (eine Antwort im Antwortpuffer).

    ``RoundTripTime`` ist in ganzen Millisekunden; Werte unter 1 ms erscheinen
    als 0, wie „<1ms“ bei ``ping.exe``.
    """

    _fields_ = (
        ("Address", wintypes.ULONG),
        ("Status", wintypes.ULONG),
        ("RoundTripTime", wintypes.ULONG),
        ("DataSize", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("Data", ctypes.c_void_p),
        ("Options", _IpOptionInformation),
    )


class _MibIpForwardRow(ctypes.Structure):
    """MIB_IPFORWARDROW aus ipmib.h (eine Zeile der IPv4-Routing-Tabelle)."""

    _fields_ = (
        ("dwForwardDest", wintypes.DWORD),
        ("dwForwardMask", wintypes.DWORD),
        ("dwForwardPolicy", wintypes.DWORD),
        ("dwForwardNextHop", wintypes.DWORD),
        ("dwForwardIfIndex", wintypes.DWORD),
        ("dwForwardType", wintypes.DWORD),
        ("dwForwardProto", wintypes.DWORD),
        ("dwForwardAge", wintypes.DWORD),
        ("dwForwardNextHopAS", wintypes.DWORD),
        ("dwForwardMetric1", wintypes.DWORD),
        ("dwForwardMetric2", wintypes.DWORD),
        ("dwForwardMetric3", wintypes.DWORD),
        ("dwForwardMetric4", wintypes.DWORD),
        ("dwForwardMetric5", wintypes.DWORD),
    )


class _SocketAddress(ctypes.Structure):
    """SOCKET_ADDRESS aus ws2def.h: Zeiger auf eine sockaddr und deren Länge."""

    _fields_ = (("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int))


class _AddressEntry(ctypes.Structure):
    """Ein Eintrag der Gateway- bzw. DNS-Server-Liste in IP_ADAPTER_ADDRESSES.

    IP_ADAPTER_GATEWAY_ADDRESS_LH und IP_ADAPTER_DNS_SERVER_ADDRESS_XP haben
    denselben Aufbau.
    """


_AddressEntry._fields_ = (
    ("Length", wintypes.ULONG),
    ("Reserved", wintypes.DWORD),
    ("Next", ctypes.POINTER(_AddressEntry)),
    ("Address", _SocketAddress),
)

type _AddressEntryPointer = ctypes._Pointer[_AddressEntry]


class _AdapterAddresses(ctypes.Structure):
    """IP_ADAPTER_ADDRESSES_LH aus iptypes.h, nur die Felder bis ``Ipv6Metric``.

    Spätere Felder werden nicht gebraucht; durch die Liste wird über ``Next``
    gegangen, die Größe der Struktur spielt deshalb keine Rolle.
    """


_AdapterAddresses._fields_ = (
    ("Length", wintypes.ULONG),
    ("IfIndex", wintypes.DWORD),
    ("Next", ctypes.POINTER(_AdapterAddresses)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.c_void_p),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.POINTER(_AddressEntry)),
    ("DnsSuffix", ctypes.c_wchar_p),
    ("Description", ctypes.c_wchar_p),
    ("FriendlyName", ctypes.c_wchar_p),
    ("PhysicalAddress", ctypes.c_ubyte * 8),
    ("PhysicalAddressLength", wintypes.ULONG),
    ("Flags", wintypes.ULONG),
    ("Mtu", wintypes.ULONG),
    ("IfType", wintypes.ULONG),
    ("OperStatus", ctypes.c_int),
    ("Ipv6IfIndex", wintypes.DWORD),
    ("ZoneIndices", wintypes.ULONG * 16),
    ("FirstPrefix", ctypes.c_void_p),
    ("TransmitLinkSpeed", ctypes.c_ulonglong),
    ("ReceiveLinkSpeed", ctypes.c_ulonglong),
    ("FirstWinsServerAddress", ctypes.c_void_p),
    ("FirstGatewayAddress", ctypes.POINTER(_AddressEntry)),
    ("Ipv4Metric", wintypes.ULONG),
    ("Ipv6Metric", wintypes.ULONG),
)

# GetAdaptersAddresses: Anycast/Multicast überspringen, Gateways mitliefern.
_GAA_FLAGS = 0x0002 | 0x0004 | 0x0080
_ERROR_BUFFER_OVERFLOW = 111
_ERROR_NO_DATA = 232
_IF_OPER_STATUS_UP = 1
_IF_TYPE_LOOPBACK = 24

# Adaptertypen (ipifcons.h), die Tunnel sind: PPP (23), "proprietär virtuell"
# (53: NordLynx, WireGuard, Wintun) und Tunnel (131).
_TUNNEL_IF_TYPES = frozenset({23, 53, 131})
# Wörter in der Beschreibung von Tunnel-Adaptern, die sich als Ethernet ausgeben.
_TUNNEL_WORDS = ("tap-windows", "wintun", "wireguard", "openvpn", "vpn")


_iphlpapi = ctypes.WinDLL("iphlpapi.dll", use_last_error=True)

_IcmpCreateFile = _iphlpapi.IcmpCreateFile
_IcmpCreateFile.argtypes = ()
_IcmpCreateFile.restype = wintypes.HANDLE

_IcmpCloseHandle = _iphlpapi.IcmpCloseHandle
_IcmpCloseHandle.argtypes = (wintypes.HANDLE,)
_IcmpCloseHandle.restype = wintypes.BOOL

_IcmpSendEcho2 = _iphlpapi.IcmpSendEcho2
_IcmpSendEcho2.argtypes = (
    wintypes.HANDLE,  # IcmpHandle
    wintypes.HANDLE,  # Event (None = synchron)
    ctypes.c_void_p,  # ApcRoutine (None)
    ctypes.c_void_p,  # ApcContext (None)
    wintypes.ULONG,  # DestinationAddress (IPAddr, Netzwerk-Byte-Reihenfolge)
    ctypes.c_void_p,  # RequestData
    wintypes.WORD,  # RequestSize
    ctypes.POINTER(_IpOptionInformation),  # RequestOptions (None = Standard)
    ctypes.c_void_p,  # ReplyBuffer
    wintypes.DWORD,  # ReplySize
    wintypes.DWORD,  # Timeout in Millisekunden
)
_IcmpSendEcho2.restype = wintypes.DWORD

_GetBestRoute = _iphlpapi.GetBestRoute
_GetBestRoute.argtypes = (wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_MibIpForwardRow))
_GetBestRoute.restype = wintypes.DWORD

_GetAdaptersAddresses = _iphlpapi.GetAdaptersAddresses
_GetAdaptersAddresses.argtypes = (
    wintypes.ULONG,  # Family (AF_INET)
    wintypes.ULONG,  # Flags
    ctypes.c_void_p,  # Reserved
    ctypes.c_void_p,  # AdapterAddresses (Puffer)
    ctypes.POINTER(wintypes.ULONG),  # SizePointer
)
_GetAdaptersAddresses.restype = wintypes.ULONG

_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Größe des Antwortpuffers laut Microsoft-Doku: eine ICMP_ECHO_REPLY-Struktur,
# die gesendeten Daten, 8 Bytes für eine ICMP-Fehlermeldung und Platz für
# einen IO_STATUS_BLOCK (16 Bytes).
_REPLY_BUFFER_SIZE = ctypes.sizeof(_IcmpEchoReply) + len(_PAYLOAD) + 8 + 16


def to_ipaddr(address: str) -> int:
    """Wandelt eine IPv4-Adresse in den Windows-Typ ``IPAddr`` um.

    ``IPAddr`` ist eine 32-Bit-Zahl, deren Bytes im Speicher in
    Netzwerk-Reihenfolge stehen. ``struct`` mit nativer Reihenfolge (``=``)
    erzeugt genau das, egal auf welcher CPU.

    Args:
        address: IPv4-Adresse, z. B. ``"192.168.178.1"``.

    Returns:
        Die Adresse als ``IPAddr``.
    """
    return struct.unpack("=L", socket.inet_aton(address))[0]


def from_ipaddr(value: int) -> str:
    """Wandelt einen ``IPAddr``-Wert zurück in Textform (Gegenstück zu :func:`to_ipaddr`)."""
    return socket.inet_ntoa(struct.pack("=L", value))


async def echo(address: str, timeout: float) -> float | None:
    """Sendet ein einzelnes ICMP-Echo und wartet auf die Antwort.

    Der blockierende Windows-Aufruf läuft in einem Hilfs-Thread, damit die
    anderen Messungen weiterlaufen.

    Args:
        address: IPv4-Adresse des Ziels.
        timeout: Sekunden, die höchstens auf die Antwort gewartet wird.

    Returns:
        Antwortzeit in Millisekunden oder ``None``, wenn keine Antwort kam.

    Raises:
        PingPermissionError: Wenn Windows den ICMP-Zugang verweigert.
    """
    return await asyncio.to_thread(_echo_blocking, address, timeout)


def _echo_blocking(address: str, timeout: float) -> float | None:
    """Blockierender Teil von :func:`echo`: ein Aufruf von ``IcmpSendEcho2``."""
    handle = _open_icmp_handle()
    try:
        reply_buffer = ctypes.create_string_buffer(_REPLY_BUFFER_SIZE)
        request = ctypes.create_string_buffer(_PAYLOAD, len(_PAYLOAD))
        replies = _IcmpSendEcho2(
            handle,
            None,
            None,
            None,
            to_ipaddr(address),
            ctypes.cast(request, ctypes.c_void_p),
            len(_PAYLOAD),
            None,
            ctypes.cast(reply_buffer, ctypes.c_void_p),
            _REPLY_BUFFER_SIZE,
            max(1, round(timeout * 1000)),
        )
        if replies == 0:
            # Keine Antwort: Zeitüberschreitung, Ziel nicht erreichbar usw.
            # Für die Statistik zählt das alles als verlorenes Paket.
            return None
        reply = _IcmpEchoReply.from_buffer(reply_buffer)
        if reply.Status != _IP_SUCCESS:
            return None
        return float(reply.RoundTripTime)
    finally:
        _IcmpCloseHandle(handle)


def _open_icmp_handle() -> int:
    """Öffnet einen ICMP-Handle oder meldet verständlich, warum das nicht geht."""
    handle = _IcmpCreateFile()
    if handle in (None, _INVALID_HANDLE_VALUE):
        code = ctypes.get_last_error()
        raise PingPermissionError(
            "Windows hat den Zugriff auf die ICMP-Schnittstelle (IcmpCreateFile) verweigert, "
            f"Fehlercode {code}. Das ist ungewöhnlich, weil ping.exe denselben Weg nutzt. "
            "Bitte prüfen, ob eine Sicherheitssoftware ICMP blockiert. Details: docs/ping.md"
        )
    return handle


def ping_permission_problem() -> str | None:
    """Prüft, ob die ICMP-Schnittstelle nutzbar ist.

    Returns:
        ``None``, wenn Ping möglich ist, sonst eine verständliche Erklärung.
    """
    try:
        handle = _open_icmp_handle()
    except PingPermissionError as err:
        return str(err)
    _IcmpCloseHandle(handle)
    return None


def current_network() -> NetworkContext | None:
    """Ermittelt Heimrouter, Netzwerkkarte, VPN und DNS-Server.

    Rohdaten: alle verbundenen Adapter mit Gateway, DNS-Servern und Typ
    (:func:`list_interfaces`) und der Adapter, über den ein Paket ins Internet
    ginge (``GetBestRoute``). Die Entscheidung trifft
    :func:`~rootping.platform.common.choose_network`.

    Returns:
        Den Netzwerk-Kontext oder ``None`` ohne Netz.
    """
    interfaces, names_by_index = list_interfaces()
    row = _MibIpForwardRow()
    result = _GetBestRoute(to_ipaddr(_ROUTE_PROBE_ADDRESS), 0, ctypes.byref(row))
    active = names_by_index.get(row.dwForwardIfIndex) if result == 0 else None
    return choose_network(interfaces, active)


def best_route_index() -> int | None:
    """Gibt den Index des Adapters zurück, über den ein Paket ins Internet ginge."""
    row = _MibIpForwardRow()
    if _GetBestRoute(to_ipaddr(_ROUTE_PROBE_ADDRESS), 0, ctypes.byref(row)) != 0:
        return None
    return int(row.dwForwardIfIndex)


def list_interfaces() -> tuple[list[Interface], dict[int, str]]:
    """Liest alle verbundenen IPv4-Adapter mit ``GetAdaptersAddresses``.

    Returns:
        Die Adapter und eine Zuordnung Index → Name (für ``GetBestRoute``).

    Raises:
        OSError: Wenn Windows die Liste nicht liefert.
    """
    size = wintypes.ULONG(16_384)
    buffer = ctypes.create_string_buffer(0)
    result = _ERROR_BUFFER_OVERFLOW
    for _ in range(3):  # Puffer zu klein → Windows nennt die nötige Größe
        buffer = ctypes.create_string_buffer(size.value)
        result = _GetAdaptersAddresses(socket.AF_INET, _GAA_FLAGS, None, buffer, ctypes.byref(size))
        if result != _ERROR_BUFFER_OVERFLOW:
            break
    if result == _ERROR_NO_DATA:
        return [], {}
    if result != 0:
        raise OSError(f"GetAdaptersAddresses fehlgeschlagen, Code {result}")

    interfaces: list[Interface] = []
    names: dict[int, str] = {}
    entry = ctypes.cast(buffer, ctypes.POINTER(_AdapterAddresses))
    while entry:
        adapter = entry.contents
        name = adapter.FriendlyName or f"ifindex-{adapter.IfIndex}"
        if adapter.OperStatus == _IF_OPER_STATUS_UP and adapter.IfType != _IF_TYPE_LOOPBACK:
            gateways = _ipv4_addresses(adapter.FirstGatewayAddress)
            names[int(adapter.IfIndex)] = name
            interfaces.append(
                Interface(
                    name=name,
                    gateway=gateways[0] if gateways else None,
                    metric=int(adapter.Ipv4Metric),
                    is_tunnel=is_tunnel(int(adapter.IfType), adapter.Description or ""),
                    dns_servers=tuple(_ipv4_addresses(adapter.FirstDnsServerAddress)),
                )
            )
        entry = adapter.Next
    return interfaces, names


def is_tunnel(if_type: int, description: str) -> bool:
    """Prüft, ob ein Adapter ein VPN- bzw. Tunnel-Adapter ist.

    Erkannt am Adaptertyp (z. B. 53 bei NordLynx, WireGuard und Wintun) oder,
    für TAP-Adapter von OpenVPN, die sich als Ethernet ausgeben, an der
    Beschreibung.

    Args:
        if_type: ``IfType`` aus ``IP_ADAPTER_ADDRESSES``.
        description: Beschreibung des Adapters.

    Returns:
        ``True`` für Tunnel-Adapter.
    """
    text = description.lower()
    return if_type in _TUNNEL_IF_TYPES or any(word in text for word in _TUNNEL_WORDS)


def _ipv4_addresses(entry: _AddressEntryPointer) -> list[str]:
    """Liest die IPv4-Adressen einer verketteten Adressliste (Gateways, DNS-Server)."""
    addresses: list[str] = []
    while entry:
        sockaddr = entry.contents.Address
        if sockaddr.lpSockaddr and sockaddr.iSockaddrLength >= 8:
            raw = ctypes.string_at(sockaddr.lpSockaddr, 8)
            family = struct.unpack_from("=H", raw)[0]
            address = socket.inet_ntoa(raw[4:8])
            if family == socket.AF_INET and address != "0.0.0.0":
                addresses.append(address)
        entry = entry.contents.Next
    return addresses
