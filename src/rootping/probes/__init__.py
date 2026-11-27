"""Liste aller verfügbaren Messungen (Probes).

Eine neue Probe = eine neue Zeile hier, ein neues Feld in
``rootping.config.ProbesSettings`` und ein Abschnitt in ``config.example.toml``.
Scheduler und Speicherung bleiben unverändert. Anleitung: ``docs/probes.md``.
"""

from typing import Any

from rootping.probes.base import Probe, ProbeResult, ProbeSettings
from rootping.probes.dns import DnsProbe
from rootping.probes.ping import PingGatewayProbe, PingInternetProbe

PROBES: dict[str, type[Probe[Any]]] = {
    "ping_gateway": PingGatewayProbe,
    "ping_internet": PingInternetProbe,
    "dns_lookup": DnsProbe,
}
"""Name → Klasse. Der Name ist zugleich der Abschnitt ``[probes.<name>]`` der Konfiguration."""

__all__ = ["PROBES", "Probe", "ProbeResult", "ProbeSettings"]
