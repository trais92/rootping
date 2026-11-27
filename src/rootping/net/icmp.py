"""Ein einzelnes ICMP-Echo (Ping), gleich auf Windows und Linux.

Das ist die einzige Stelle, über die RootPing pingt (ADR-006). Die
eigentliche Arbeit macht das Betriebssystem-Modul in ``rootping.platform``.
Ein späterer Wechsel des Ping-Wegs (z. B. Notlösung System-``ping``) betrifft
nur dieses Modul und ``rootping.platform``.
"""

import ipaddress

from rootping import platform


async def echo(target: str, timeout: float) -> float | None:
    """Sendet ein ICMP-Echo an ``target`` und wartet höchstens ``timeout`` Sekunden.

    Ziele müssen IPv4-Adressen sein, keine Namen. So hängt eine Ping-Messung
    nie vom DNS ab und eine DNS-Störung sieht nicht wie Paketverlust aus
    (ADR-011).

    Args:
        target: IPv4-Adresse, z. B. ``"1.1.1.1"``.
        timeout: Sekunden, die höchstens auf die Antwort gewartet wird.

    Returns:
        Antwortzeit in Millisekunden oder ``None``, wenn das Paket verloren ging.

    Raises:
        ValueError: Wenn ``target`` keine IPv4-Adresse ist.
        rootping.platform.PingPermissionError: Wenn das Betriebssystem keinen Ping erlaubt.
    """
    ipaddress.IPv4Address(target)  # wirft ValueError bei Namen oder IPv6
    return await platform.echo(target, timeout)
