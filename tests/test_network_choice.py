"""Tests für die Wahl von Heimrouter, VPN und DNS-Server (``choose_network``).

Die Szenarien sind echten Rechnern nachgebaut, u. a. dem Windows-Test mit
NordVPN (NordLynx-Adapter, VPN-Gateway 10.5.0.1, FritzBox 192.168.178.1).
Die Regeln selbst stehen in ``docs/netzwerk.md``.
"""

from rootping.platform.common import Interface, NetworkContext, choose_network

ETHERNET = Interface("Ethernet 2", "192.168.178.1", 25, False, ("192.168.178.1",))
WLAN = Interface("WLAN", "192.168.0.1", 50, False, ("192.168.0.1",))
NORDLYNX = Interface("NordLynx", "10.5.0.1", 5, True, ("103.86.96.100", "103.86.99.100"))


def test_plain_home_network() -> None:
    ctx = choose_network([ETHERNET], "Ethernet 2")
    assert ctx == NetworkContext("192.168.178.1", "Ethernet 2")
    assert ctx is not None
    assert ctx.dns_servers == ("192.168.178.1",)


def test_vpn_keeps_home_router_and_uses_vpn_dns() -> None:
    ctx = choose_network([ETHERNET, NORDLYNX], "NordLynx")
    assert ctx is not None
    assert (ctx.gateway, ctx.interface, ctx.vpn) == ("192.168.178.1", "Ethernet 2", "NordLynx")
    assert ctx.dns_servers == ("103.86.96.100", "103.86.99.100")


def test_vpn_without_own_gateway_like_wireguard_on_linux() -> None:
    wg0 = Interface("wg0", None, 1_000_000, True)
    eth0 = Interface("eth0", "192.168.178.1", 100, False)
    ctx = choose_network([eth0, wg0], "wg0")
    assert ctx == NetworkContext("192.168.178.1", "eth0", vpn="wg0")


def test_active_card_wins_over_lower_metric() -> None:
    ctx = choose_network([ETHERNET, WLAN], "WLAN")
    assert ctx is not None
    assert ctx.interface == "WLAN"


def test_lowest_metric_when_active_card_is_unknown() -> None:
    ctx = choose_network([WLAN, ETHERNET], None)
    assert ctx is not None
    assert ctx.interface == "Ethernet 2"


def test_only_a_tunnel_falls_back_to_its_gateway() -> None:
    ctx = choose_network([NORDLYNX], "NordLynx")
    assert ctx is not None
    assert (ctx.gateway, ctx.vpn) == ("10.5.0.1", "NordLynx")


def test_no_gateway_means_no_network() -> None:
    assert choose_network([Interface("eth0", None, 100, False)], "eth0") is None
    assert choose_network([], None) is None


def test_dns_servers_do_not_change_identity() -> None:
    assert NetworkContext("192.168.178.1", "eth0", dns_servers=("1.1.1.1",)) == NetworkContext(
        "192.168.178.1", "eth0"
    )
    assert NetworkContext("192.168.178.1", "eth0", vpn="wg0") != NetworkContext(
        "192.168.178.1", "eth0"
    )
