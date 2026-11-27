"""Was beide Betriebssystem-Module (``linux.py``, ``windows.py``) gemeinsam nutzen.

Dazu gehört die Entscheidung „Welcher Router ist der Heimrouter, läuft ein
VPN?“. Sie ist hier als reine Funktion (:func:`choose_network`) geschrieben,
damit sie auf jedem System mit erfundenen Netzwerkkarten getestet werden kann.
Die Betriebssystem-Module liefern nur die Rohdaten. Hintergrund:
``docs/netzwerk.md``.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NetworkContext:
    """In welchem Netz gerade gemessen wird (Tabelle ``network_contexts``).

    Zwei Kontexte sind gleich, wenn Router, Netzwerkkarte und VPN gleich sind.
    Die DNS-Server zählen dafür nicht (``compare=False``), weil sie sich auch
    ohne Netzwechsel ändern können.

    Attributes:
        gateway: IPv4-Adresse des Heimrouters, z. B. ``"192.168.178.1"``. Bei
            aktivem VPN ist das der Router im lokalen Netz, nicht das VPN-Gateway.
        interface: Lesbarer Name der Netzwerkkarte zum Heimrouter, z. B. ``"Ethernet 2"``.
        vpn: Name des VPN-Adapters, über den der Internetverkehr läuft, oder ``""``.
        dns_servers: DNS-Server des Adapters, über den der Internetverkehr läuft
            (bei VPN also die des VPN). Leer, wenn das System sie nicht pro
            Adapter liefert (Linux).
    """

    gateway: str
    interface: str
    vpn: str = ""
    dns_servers: tuple[str, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class Interface:
    """Rohdaten einer Netzwerkkarte, wie sie das Betriebssystem-Modul ermittelt.

    Attributes:
        name: Lesbarer Name, z. B. ``"Ethernet 2"``, ``"wlan0"``, ``"NordLynx"``.
        gateway: IPv4-Adresse des Standard-Gateways dieser Karte oder ``None``.
        metric: Je kleiner, desto bevorzugt (Routing-Metrik).
        is_tunnel: Ob es ein VPN- bzw. Tunnel-Adapter ist.
        dns_servers: IPv4-DNS-Server dieser Karte (leer, wenn unbekannt).
    """

    name: str
    gateway: str | None
    metric: int
    is_tunnel: bool
    dns_servers: tuple[str, ...] = ()


def choose_network(interfaces: list[Interface], active: str | None) -> NetworkContext | None:
    """Bestimmt Heimrouter, VPN und DNS-Server aus den Netzwerkkarten.

    Regeln:

    1. ``active`` ist die Karte, über die der Internetverkehr gerade läuft.
       Ist sie ein Tunnel, ist ein VPN aktiv.
    2. Heimrouter ist das Gateway der bevorzugten Karte, die **kein** Tunnel ist
       (kleinste Metrik). Ist ``active`` selbst kein Tunnel, ist es diese Karte.
    3. Gibt es keine solche Karte, wird das Gateway von ``active`` genommen,
       falls vorhanden; sonst gibt es kein Netz (``None``).
    4. DNS-Server sind die von ``active``, sonst die der Heimrouter-Karte.

    Args:
        interfaces: Alle Karten, die gerade verbunden sind.
        active: Name der Karte, über die eine Verbindung ins Internet ginge,
            oder ``None``, wenn das unbekannt ist.

    Returns:
        Den Netzwerk-Kontext oder ``None`` ohne Netz.
    """
    by_name = {i.name: i for i in interfaces}
    active_if = by_name.get(active) if active else None

    lan_candidates = [i for i in interfaces if i.gateway and not i.is_tunnel]
    if active_if is not None and active_if in lan_candidates:
        lan = active_if
    elif lan_candidates:
        lan = min(lan_candidates, key=lambda i: i.metric)
    elif active_if is not None and active_if.gateway:
        lan = active_if
    else:
        return None

    vpn = active_if.name if active_if is not None and active_if.is_tunnel else ""
    dns_source = active_if if active_if is not None and active_if.dns_servers else lan
    assert lan.gateway is not None  # durch die Auswahl oben garantiert
    return NetworkContext(
        gateway=lan.gateway,
        interface=lan.name,
        vpn=vpn,
        dns_servers=dns_source.dns_servers,
    )


class PingPermissionError(RuntimeError):
    """Das Betriebssystem erlaubt diesem Benutzer keinen Ping.

    Die Meldung erklärt die Ursache und die Abhilfe in verständlichen Worten
    und wird so, wie sie ist, dem Benutzer angezeigt.
    """
