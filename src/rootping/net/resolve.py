"""Hostnamen über den Resolver des Betriebssystems in eine IPv4-Adresse übersetzen.

Gebraucht nur für Ping-Ziele, die als Name eingetragen sind (Opt-in
``allow_hostnames``, ADR-011). Es wird bewusst der Resolver des Systems
benutzt (``getaddrinfo``), also derselbe Weg wie im Browser oder im Spiel:
Man misst die Adresse, die man beim Aufruf der Website auch bekäme.

Schlägt die Übersetzung fehl, ist das ein eigener Fehler (``resolve_failed``)
und kein Paketverlust. So bleibt sichtbar, ob die Leitung oder DNS das Problem ist.
"""

import asyncio
import socket


class ResolveError(Exception):
    """Der Name ließ sich nicht in eine IPv4-Adresse übersetzen."""


async def resolve_ipv4(name: str, timeout: float) -> str:
    """Gibt die erste IPv4-Adresse zurück, die das Betriebssystem für ``name`` liefert.

    Args:
        name: Hostname, z. B. ``"www.ea.com"``.
        timeout: Sekunden, die höchstens gewartet wird.

    Returns:
        Die IPv4-Adresse als Text.

    Raises:
        ResolveError: Bei unbekanntem Namen, Zeitüberschreitung oder ohne IPv4-Adresse.
    """
    loop = asyncio.get_running_loop()
    try:
        async with asyncio.timeout(timeout):
            infos = await loop.getaddrinfo(
                name, None, family=socket.AF_INET, type=socket.SOCK_DGRAM
            )
    except (TimeoutError, OSError) as err:
        raise ResolveError(f"{name}: {err or 'Zeitüberschreitung'}") from err
    for _family, _type, _proto, _canon, sockaddr in infos:
        return str(sockaddr[0])
    raise ResolveError(f"{name}: keine IPv4-Adresse")
