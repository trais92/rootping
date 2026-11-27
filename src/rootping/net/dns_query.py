"""Eine einzelne DNS-Abfrage an genau einen Server, mit fester Fehlerart.

Gebaut auf ``dnspython`` (``dns.asyncresolver``). Pro Abfrage wird ein eigener
Resolver mit genau **einem** Nameserver und ohne Cache angelegt, damit klar ist,
welcher Server wie schnell geantwortet hat (``docs/tech-stack.md`` 3.10).

Die Fehlerarten entsprechen der Spalte ``measurements.error``
(``docs/datenmodell.md``):

=============  =========================================================
``timeout``    Keine Antwort innerhalb des Timeouts
``nxdomain``   Server sagt: Name existiert nicht
``noanswer``   Name existiert, hat aber keinen A-Eintrag
``servfail``   Server meldet einen Fehler (SERVFAIL, REFUSED …)
``dns_error``  Sonstiger DNS-Fehler (z. B. kaputte Antwort)
``blocked``    Antwort kam, zeigt aber nur auf ``0.0.0.0`` o. Ä.: Ein
               Werbeblocker (z. B. Pi-hole) blockiert den abgefragten Namen.
               Der Server funktioniert, die Messung sagt aber nichts über
               eine echte Auflösung; Abhilfe: ``query`` in der Konfiguration ändern.
=============  =========================================================
"""

import asyncio
import ipaddress

import dns.asyncresolver
import dns.exception
import dns.resolver

BLOCKED_ADDRESSES = frozenset({"0.0.0.0", "127.0.0.1"})
"""Antworten, mit denen DNS-Werbeblocker einen Namen sperren (Pi-hole: ``0.0.0.0``)."""


class DnsQueryError(Exception):
    """Die DNS-Abfrage ist fehlgeschlagen.

    Attributes:
        code: Feste Fehlerart, z. B. ``"timeout"`` (siehe Modul-Docstring).
        latency_ms: Antwortzeit, falls trotz Fehler eine Antwort kam (``blocked``), sonst ``None``.
    """

    def __init__(self, code: str, latency_ms: float | None = None) -> None:
        """Merkt sich die Fehlerart.

        Args:
            code: Feste Fehlerart.
            latency_ms: Antwortzeit, falls eine Antwort kam.
        """
        super().__init__(code)
        self.code = code
        self.latency_ms = latency_ms


async def query(server: str, name: str, timeout: float, port: int = 53) -> float:
    """Fragt ``server`` nach dem A-Eintrag von ``name`` und misst die Antwortzeit.

    Args:
        server: IPv4-Adresse des DNS-Servers.
        name: Abgefragter Name, z. B. ``"example.com"``.
        timeout: Sekunden bis zur Aufgabe (inklusive Wiederholungen von dnspython).
        port: UDP-Port des Servers; nur Tests ändern ihn.

    Returns:
        Antwortzeit in Millisekunden.

    Raises:
        DnsQueryError: Mit fester Fehlerart, wenn keine gültige Antwort kam.
        ValueError: Wenn ``server`` keine IPv4-Adresse ist.
    """
    ipaddress.IPv4Address(server)
    resolver = dns.asyncresolver.Resolver(configure=False)
    resolver.nameservers = [server]
    resolver.port = port
    resolver.timeout = timeout
    resolver.lifetime = timeout
    resolver.cache = None

    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        answer = await resolver.resolve(name, "A", search=False)
    except dns.exception.Timeout as err:
        raise DnsQueryError("timeout") from err
    except dns.resolver.NXDOMAIN as err:
        raise DnsQueryError("nxdomain") from err
    except dns.resolver.NoAnswer as err:
        raise DnsQueryError("noanswer") from err
    except dns.resolver.NoNameservers as err:
        raise DnsQueryError("servfail") from err
    except dns.exception.DNSException as err:
        raise DnsQueryError("dns_error") from err
    latency = (loop.time() - start) * 1000
    addresses = {record.to_text() for record in answer}
    if addresses and addresses <= BLOCKED_ADDRESSES:
        raise DnsQueryError("blocked", latency)
    return latency


def system_nameserver() -> str | None:
    """Gibt den ersten DNS-Server des Betriebssystems zurück (nur IPv4).

    Linux: aus ``/etc/resolv.conf``. Mit systemd-resolved ist das oft der lokale
    Zwischenspeicher ``127.0.0.53``, nicht der Router (``docs/diagnose.md``).
    Windows: aus der Registry.

    Returns:
        Die IPv4-Adresse oder ``None``, wenn keiner eingerichtet ist.
    """
    try:
        servers = dns.resolver.Resolver().nameservers
    except dns.exception.DNSException:
        return None
    for server in servers:
        try:
            ipaddress.IPv4Address(str(server))
        except ValueError:
            continue
        return str(server)
    return None
