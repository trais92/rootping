"""Tests für den Scheduler mit gefälschter Probe, Router-Erkennung und Uhr."""

import asyncio

import pytest

from rootping import scheduler as scheduler_module
from rootping.platform import NetworkContext
from rootping.scheduler import Scheduler
from rootping.storage import Storage
from tests.conftest import FakeProbe, FakeSettings

HOME = NetworkContext("192.168.178.1", "eth0")


def make(storage: Storage, *probes: FakeProbe, route=lambda: HOME, **kwargs) -> Scheduler:
    return Scheduler(list(probes), storage, gap_seconds=30, route=route, **kwargs)


async def test_each_round_is_saved_with_all_targets(storage: Storage) -> None:
    probe = FakeProbe()
    await make(storage, probe).run(rounds=3)
    rows = storage.recent_measurements(limit=100)
    assert len(rows) == 6  # 3 Runden × 2 Ziele
    assert {r["target"] for r in rows} == {"a", "b"}
    assert all(r["context_id"] is not None for r in rows)


async def test_crashing_probe_becomes_probe_error_and_others_continue(storage: Storage) -> None:
    good, bad = FakeProbe(), FakeProbe(FakeSettings(targets=["x"]), behaviour="crash")
    bad.name = "kaputt"
    await make(storage, good, bad).run(rounds=2)
    rows = storage.recent_measurements(limit=100)
    errors = [r for r in rows if r["probe"] == "kaputt"]
    assert len(errors) == 2
    assert all(r["ok"] == 0 and r["error"] == "probe_error" for r in errors)
    assert sum(r["probe"] == "fake" and r["ok"] == 1 for r in rows) == 4


async def test_hanging_probe_is_stopped_after_its_time_limit(storage: Storage) -> None:
    hanging = FakeProbe(FakeSettings(targets=["x"]), behaviour="hang")
    loop = asyncio.get_running_loop()
    start = loop.time()
    await make(storage, hanging).run(rounds=1)
    assert loop.time() - start < 1.0  # Grenze 0,05 + 2 × 0,05 s, nicht eine Stunde
    [row] = storage.recent_measurements()
    assert row["error"] == "probe_error"


async def test_rounds_follow_a_fixed_clock(storage: Storage) -> None:
    probe = FakeProbe(FakeSettings(interval=0.05, targets=["x"]))
    loop = asyncio.get_running_loop()
    start = loop.time()
    await make(storage, probe).run(rounds=5)
    # 5 Runden starten bei 0, 50, …, 200 ms; ohne Drift also ~0,2 s gesamt.
    assert loop.time() - start == pytest.approx(0.2, abs=0.15)


async def test_network_change_is_recorded_once(storage: Storage) -> None:
    contexts = iter([HOME, HOME, NetworkContext("10.8.0.1", "tun0"), None])
    sched = make(storage, FakeProbe(FakeSettings(targets=["x"])), route=lambda: next(contexts))
    probe = FakeProbe(FakeSettings(targets=["x"]))
    for _ in range(4):
        await sched.run_round(probe)
    events = storage.events()
    assert [e["type"] for e in events] == ["network_change", "network_change"]
    assert events[0]["details"]["to"] == {"gateway": "10.8.0.1", "interface": "tun0", "vpn": ""}
    assert events[1]["details"]["to"] is None  # Netz weg
    rows = storage.recent_measurements(limit=10)
    assert rows[0]["context_id"] is None


async def test_router_detection_error_does_not_stop_measuring(storage: Storage) -> None:
    def broken_route() -> NetworkContext | None:
        raise OSError("kaputt")

    results = await make(storage, route=broken_route).run_round(FakeProbe())
    assert all(r.ok for r in results)


async def test_clock_jump_is_recorded_as_gap(
    storage: Storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler_module, "CLOCK_CHECK_PERIOD_S", 0.01)
    wall = iter([1000.0, 1001.0, 5000.0] + [5001.0 + i for i in range(10_000)])
    sched = make(storage, wall_clock=lambda: next(wall))
    task = asyncio.create_task(sched._watch_clock())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    [event] = storage.events()
    assert event["type"] == "gap"
    assert event["details"]["gap_seconds"] == 3999.0


async def test_results_callback_gets_each_round(storage: Storage) -> None:
    seen: list[int] = []
    await make(storage, FakeProbe(), on_results=lambda rs: seen.append(len(rs))).run(rounds=2)
    assert seen == [2, 2]
