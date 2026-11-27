"""Typen, die beide Betriebssystem-Module (``linux.py``, ``windows.py``) gemeinsam nutzen."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkContext:
    """In welchem Netz gerade gemessen wird (Tabelle ``network_contexts``).

    Attributes:
        gateway: IPv4-Adresse des Routers (Standardroute), z. B. ``"192.168.178.1"``.
        interface: Name der Netzwerkkarte, über die die Standardroute läuft.
    """

    gateway: str
    interface: str


class PingPermissionError(RuntimeError):
    """Das Betriebssystem erlaubt diesem Benutzer keinen Ping.

    Die Meldung erklärt die Ursache und die Abhilfe in verständlichen Worten
    und wird so, wie sie ist, dem Benutzer angezeigt.
    """
