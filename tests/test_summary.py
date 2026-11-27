"""Tests für summarize(): feste Beispiele und Eigenschaften mit Hypothesis."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rootping.probes.summary import summarize

rtt = st.floats(min_value=0, max_value=10_000, allow_nan=False)
rtt_or_lost = st.one_of(st.none(), rtt)


def test_example_from_docs() -> None:
    # Beispiel aus docs/diagnose.md: 20, 25, verloren, 22 → Differenzen 5 und 3 → Jitter 4.
    s = summarize([20.0, 25.0, None, 22.0])
    assert s.sent == 4
    assert s.received == 3
    assert s.loss_pct == 25.0
    assert s.avg_ms == pytest.approx(67 / 3)
    assert s.max_ms == 25.0
    assert s.jitter_ms == pytest.approx(4.0)


def test_two_of_ten_lost_is_twenty_percent() -> None:
    assert summarize([10.0] * 8 + [None, None]).loss_pct == 20.0


def test_all_lost() -> None:
    s = summarize([None, None, None])
    assert (s.received, s.loss_pct, s.avg_ms, s.max_ms, s.jitter_ms) == (0, 100.0, None, None, None)


def test_single_reply_has_no_jitter() -> None:
    s = summarize([None, 12.0])
    assert s.jitter_ms is None
    assert s.avg_ms == s.max_ms == 12.0


def test_empty_round_is_an_error() -> None:
    with pytest.raises(ValueError, match="mindestens ein Echo"):
        summarize([])


@given(st.lists(rtt_or_lost, min_size=1, max_size=50))
def test_properties_hold_for_any_round(rtts: list[float | None]) -> None:
    s = summarize(rtts)
    assert 0.0 <= s.loss_pct <= 100.0
    assert s.sent == len(rtts)
    assert s.received == sum(r is not None for r in rtts)
    if s.received == 0:
        assert s.loss_pct == 100.0
        assert s.avg_ms is None
    else:
        assert s.avg_ms is not None
        assert s.max_ms is not None
        assert s.max_ms >= s.avg_ms or math.isclose(s.max_ms, s.avg_ms)
    if s.jitter_ms is not None:
        assert s.jitter_ms >= 0.0


@given(st.lists(rtt, min_size=2, max_size=50), st.floats(min_value=0, max_value=1000))
def test_constant_offset_does_not_change_jitter(rtts: list[float], offset: float) -> None:
    # Jitter misst Schwankung, nicht Höhe: alle Werte um denselben Betrag verschieben ändert nichts.
    a = summarize(list(rtts))
    b = summarize([r + offset for r in rtts])
    assert a.jitter_ms is not None
    assert b.jitter_ms is not None
    assert b.jitter_ms == pytest.approx(a.jitter_ms, abs=1e-6)
