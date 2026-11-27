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
=============  =========================================================
"""

import asyncio
import ipaddress

import dns.asyncresolver
import dns.exception
import dns.resolver


class DnsQueryError(Exception):
    """Die DNS-Abfrage ist fehlgeschlagen.

    Attributes:
        code: Feste Fehlerart, z. B. ``"timeout"`` (siehe Modul-Docstring).
    """

    def __init__(self, code: str) -> None:
        """Merkt sich die Fehlerart.

        Args:
            code: Feste Fehlerart.
        """
        super().__init__(code)
        self.code = code


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
        await resolver.resolve(name, "A", search=False)
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
    return (loop.time() - start) * 1000


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
