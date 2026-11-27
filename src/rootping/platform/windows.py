"""Windows-spezifischer Teil: Ping ohne Adminrechte und Router-Erkennung.

Beides läuft über ``Iphlpapi.dll``, eine Systembibliothek, die in jedem
Windows steckt. Aufgerufen wird sie mit ``ctypes`` aus der Standardbibliothek,
also ohne Zusatzpaket, ohne Unterprozess und ohne sprachabhängige Textausgabe.

- **Ping:** ``IcmpSendEcho2``, derselbe Weg wie ``ping.exe``. Braucht keine
  Adminrechte, anders als ein Raw Socket (Befund B1, ADR-006). Der Aufruf
  blockiert, deshalb läuft er mit ``asyncio.to_thread`` in einem Hilfs-Thread.
- **Router:** ``GetBestRoute`` liefert die Route, über die ein Paket ins
  Internet gehen würde; deren nächster Hop ist der Router.

Microsoft-Doku: IcmpSendEcho2, ICMP_ECHO_REPLY, GetBestRoute, MIB_IPFORWARDROW
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

from rootping.platform.common import NetworkContext, PingPermissionError

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


def default_route() -> NetworkContext | None:
    """Ermittelt Router und Netzwerkkarte der Route ins Internet.

    Returns:
        Den Netzwerk-Kontext oder ``None``, wenn es keine Route gibt (kein Netz)
        oder sie direkt ohne Router hinausgeht (z. B. bei manchen VPNs).
    """
    row = _MibIpForwardRow()
    result = _GetBestRoute(to_ipaddr(_ROUTE_PROBE_ADDRESS), 0, ctypes.byref(row))
    if result != 0 or row.dwForwardNextHop == 0:
        return None
    try:
        interface = socket.if_indextoname(row.dwForwardIfIndex)
    except OSError:
        interface = f"ifindex-{row.dwForwardIfIndex}"
    return NetworkContext(gateway=from_ipaddr(row.dwForwardNextHop), interface=interface)
