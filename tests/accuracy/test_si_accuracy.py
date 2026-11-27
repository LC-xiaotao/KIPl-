"""Single-ended receiver and TDR results against travelling-wave and RC solutions."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from kipi.core.model.board import Track, Via
from kipi.core.model.snapshot_io import load
from kipi.core.progress import NULL
from kipi.noise.extract.capacitive import split_tracks
from kipi.si.channel import Channel, Section, _topology, extract_channel
from kipi.si.solver import Settings, simulate

DEMO = Path(__file__).parents[2] / "examples/validation/single_ended_si/stepped_line.kipi.json"


def stepped(second_z=75.):
    return Channel([Section(0, 1, (0, 0), (60, 0), 3, 50., .4),
                    Section(1, 2, (60, 0), (90, 0), 3, second_z, .2)], 2)


def test_steps_and_source_termination_sweep():
    cfg = Settings(rise_ps=100, load_pf=0., series_ohm=(0., 32.), eye_gbps=1.)
    r = simulate(stepped(), cfg)
    # 50 -> 75 ohm, first reflection +0.2; returns at 0.8 ns. RX is open and doubles V+.
    assert np.interp([.6, 1.08, 3.], r.time_ns, r.tdr_ohm) == pytest.approx([50., 75., 50.], abs=.02)
    assert r.receiver_v.max(axis=1) == pytest.approx(2 * 1.2 * 1.8 * 50 / np.array([68, 100]), abs=.002)
    assert r.channel.locate(.8)[1:] == ((60., 0.), 60.)
    assert r.channel.locate(1.5) is None
    phase, traces, opening = r.eye
    assert opening == pytest.approx(1.79, abs=.02)
    assert traces.shape == (127, len(phase))
    assert np.count_nonzero(traces[:, 64] > .9) == 64
    assert np.min(traces[traces[:, 64] > .9, 64]) > 1.75


def test_uniform_line_capacitive_rx_and_matched_rx():
    cfg = Settings(rise_ps=80., driver_ohm=50., series_ohm=(0.,), load_pf=4.)
    r = simulate(stepped(50.), cfg)
    # An open-ended capacitor behind a matched source sees a delayed single-pole step.
    # Time constant 50 ohm * 4 pF = .2 ns; drive integrates a .1 ns linear ramp.
    tau, ramp = .2, .1
    t = r.time_ns

    def integrated_step(dt):
        dt = np.maximum(dt, 0.)
        return dt + tau * np.expm1(-dt / tau)

    expected = 1.8 / ramp * (integrated_step(t - .6) - integrated_step(t - .6 - ramp))
    np.testing.assert_allclose(r.receiver_v[0], expected, atol=3e-4)
    m = simulate(stepped(50.), replace(cfg, load_pf=0., load_ohm=50.))
    np.testing.assert_allclose(m.tdr_ohm, 50., atol=.002)
    assert m.receiver_v[0, -1] == pytest.approx(.9, abs=2e-4)
    assert np.interp(.3, m.time_ns, m.source_v[0]) == pytest.approx(.9, abs=2e-4)


def test_open_stub_contributes_to_reflection():
    c = stepped(50.)
    c.sections.append(Section(1, 3, (60, 0), (60, 90), 3, 50., .6))
    r = simulate(c, Settings(load_ohm=50., load_pf=0., rise_ps=50.))
    # Two 50 ohm branches initially look like 25 ohms at the tee.
    assert np.interp(1., r.time_ns, r.tdr_ohm) == pytest.approx(25., abs=.02)
    assert len(c.route()) == 2


def test_real_board_cross_sections_and_ports():
    snap = load(DEMO)
    c = extract_channel(snap, "CLK", "GND", "TX.1", "RX.1")
    assert c.sections[0].ohms == pytest.approx(50., abs=3.)
    assert c.sections[-1].ohms == pytest.approx(75., abs=4.)
    assert sum(s.flight_ns for s in c.route()) == pytest.approx(.51, abs=.04)
    assert c.locate(.1)[0].layer == 3
    snap.zones.clear()
    snap.invalidate_index()
    with pytest.raises(ValueError, match="参考网络"):
        extract_channel(snap, "CLK", "GND", "TX.1", "RX.1")


def test_disconnected_layers_require_a_physical_via():
    snap = load(DEMO)
    snap.tracks[1].layer = 34
    snap.pads[1].shapes[34] = snap.pads[1].shapes.pop(3)
    segs = split_tracks(snap, "CLK", 2.)
    with pytest.raises(ValueError, match="没有连续"):
        _topology(snap, "CLK", segs, "TX.1", "RX.1", NULL)
    snap.vias.append(Via("v", "CLK", (60., 0.), .2, .45, [3, 34]))
    snap.invalidate_index()
    ordered, _ = _topology(snap, "CLK", segs, "TX.1", "RX.1", NULL)
    assert {edge[2].layer for edge in ordered} == {3, 34}


def test_via_in_pad_reaches_a_track_on_another_layer():
    snap = load(DEMO)
    for track in snap.tracks:
        track.layer = 34
    snap.pads[1].shapes[34] = snap.pads[1].shapes.pop(3)
    snap.vias.append(Via("in-pad", "CLK", (0., 0.), .2, .45, [3, 34]))
    snap.invalidate_index()
    ordered, _ = _topology(snap, "CLK", split_tracks(snap, "CLK", 2.), "TX.1", "RX.1", NULL)
    assert {edge[2].layer for edge in ordered} == {34}


def test_mid_track_tee_kept_and_loops_reported():
    snap = load(DEMO)
    snap.tracks.append(Track("CLK", 3, .25, (15., 0.), (15., 5.)))
    snap.invalidate_index()
    ordered, _ = _topology(snap, "CLK", split_tracks(snap, "CLK", 2.), "TX.1", "RX.1", NULL)
    assert any(s.b == (15., 5.) for _, _, s, _ in ordered)
    snap.tracks.append(Track("CLK", 3, .25, (15., 5.), (20., 0.)))
    snap.invalidate_index()
    with pytest.raises(ValueError, match="闭环"):
        _topology(snap, "CLK", split_tracks(snap, "CLK", 2.), "TX.1", "RX.1", NULL)
