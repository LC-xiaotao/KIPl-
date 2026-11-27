"""Lossless distributed lines on a tree, driven by a linear 0-to-V ramp.

Admittances are reduced from the leaves to the source. A second propagation along
the selected path gives the loaded receiver voltage. Units here are ohms, ns and pF.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

import numpy as np
from scipy.fft import irfft, next_fast_len, rfftfreq

from kipi.core.progress import NULL
from kipi.si.channel import Channel


@dataclass(frozen=True)
class Settings:
    high_v: float = 1.8
    rise_ps: float = 200.0        # 10%–90%
    driver_ohm: float = 18.0
    series_ohm: tuple = (0., 22., 33.)
    load_ohm: float = np.inf
    load_pf: float = 3.0
    reference_ohm: float = 50.0
    threshold_v: float = 0.9
    eye_gbps: float = 0.0         # zero disables the PRBS7 eye

    def validate(self):
        positive = [self.high_v, self.rise_ps, self.reference_ohm]
        nonnegative = [self.driver_ohm, self.load_pf, self.eye_gbps, *self.series_ohm]
        if (not self.series_ohm or not all(np.isfinite(x) and x > 0 for x in positive)
                or not all(np.isfinite(x) and x >= 0 for x in nonnegative)
                or not self.load_ohm > 0 or not 0 < self.threshold_v < self.high_v):
            raise ValueError("请检查阻抗、边沿时间和电压。判定门限应在 0 V 与驱动高电平之间。")


@dataclass
class Result:
    channel: Channel
    settings: Settings
    time_ns: np.ndarray
    receiver_v: np.ndarray       # one row per source series resistor
    source_v: np.ndarray         # at the trace side of the source series resistor
    tdr_ohm: np.ndarray
    eye: tuple | None            # phase, voltage traces, vertical opening at 0.5 UI
    eye_note: str


def _merge_uniform(channel):
    """Equivalent series sections can share one propagation factor at every frequency."""
    degree = Counter(line.parent for line in channel.sections)
    incoming = {}
    reduced = []
    for line in channel.sections:
        parent_index = incoming.get(line.parent)
        if parent_index is not None and degree[line.parent] == 1 and line.parent != channel.receiver:
            previous = reduced[parent_index]
            if abs(previous.ohms - line.ohms) < 1e-9:
                reduced[parent_index] = replace(previous, child=line.child, b=line.b,
                                                flight_ns=previous.flight_ns + line.flight_ns)
                incoming[line.child] = parent_index
                continue
        incoming[line.child] = len(reduced)
        reduced.append(line)
    return Channel(reduced, channel.receiver)


def _transfer(channel, path_nodes, s, load_y):
    """Input admittance and Vrx/Vport. exp(-s·delay) stays bounded for Re(s) > 0."""
    branches = {channel.receiver: load_y}
    gain = 1.
    for line in reversed(channel.sections):
        y = branches.pop(line.child, 0.)
        p = np.exp(-s * line.flight_ns)
        # expm1 avoids subtracting nearly equal values for electrically short segments.
        diff = -np.expm1(-2 * s * line.flight_ns)
        add = 2 - diff
        yz = y * line.ohms
        den = add + yz * diff
        yin = (diff + yz * add) / (line.ohms * den)
        branches[line.parent] = branches.get(line.parent, 0.) + yin
        if line.child in path_nodes:
            gain = gain * (2 * p / den)
    return branches[0], gain


def _eye(t, step, ui, delay, final_v):
    """Superpose positive and negative PRBS7 transitions of the band-limited step."""
    # Do not truncate an appreciable reflection and draw a misleading open eye.
    if np.max(np.abs(step[-max(2, len(t) // 10):] - final_v)) > 0.005 * final_v:
        return None, "当前时间窗内阶跃尚未稳定，未生成眼图。"
    state = 127
    bits = []
    for _ in range(127):
        bits.append((state >> 6) & 1)
        state = ((state << 1) & 127) | (((state >> 6) ^ (state >> 5)) & 1)
    phase = np.linspace(0., 2., 257)
    traces = np.zeros((127, len(phase)))
    # At a given transition age k*UI, all bits see the same shifted response.
    bits = np.asarray(bits)
    changes = bits - np.roll(bits, 1)
    history = int(np.ceil(t[-1] / ui)) + 1
    if history > 4096:
        return None, "通道记忆超过 4096 个单位间隔，跳过眼图。"
    traces += np.roll(bits, history + 1)[:, None] * final_v
    future = int(np.ceil(delay / ui)) + 2
    for k in range(-future, history + 1):
        response = np.interp(delay + (phase + k) * ui, t, step, left=0., right=final_v)
        traces += np.roll(changes, k)[:, None] * response
    centre = traces[:, len(phase) // 4]
    opening = centre[bits == 1].min() - centre[bits == 0].max()
    return (phase, traces, float(opening)), ""


def simulate(channel, settings, progress=NULL):
    settings.validate()
    electrical = _merge_uniform(channel)
    paths = {line.child for line in electrical.route()}
    times = {0: 0.}
    for line in channel.sections:
        if not (np.isfinite(line.flight_ns) and line.flight_ns > 0
                and np.isfinite(line.ohms) and line.ohms > 0):
            raise ValueError("提取的传播延迟或走线阻抗无效。")
        times[line.child] = times[line.parent] + line.flight_ns
    arrival = times[channel.receiver]
    rise = settings.rise_ps / 1000. / .8
    rs = np.asarray(settings.series_ohm) + settings.driver_ohm
    tau = max(max(rs), max(line.ohms for line in channel.sections)) * settings.load_pf * .001
    span = max(18 * max(times.values()), 8 * rise, 12 * tau)
    dt_target = min(rise / 32., arrival / 32.)
    if settings.eye_gbps:
        dt_target = min(dt_target, 1 / (32 * settings.eye_gbps))
    n = next_fast_len(int(np.ceil(2 * span / dt_target)), real=True)
    if n > 131072:
        raise ValueError("所选边沿与通道延迟相差过大，请增大边沿时间或缩小负载电容。")
    period = 2 * span
    dt = period / n
    t = np.arange(n // 2) * dt
    sigma = 18. / period
    s = sigma + 2j * np.pi * rfftfreq(n, dt)
    drive = -np.expm1(-s * rise) / (rise * s * s)
    n_cases = len(rs)
    out = np.empty((2 * n_cases + 1, len(s)), complex)
    progress.stage("求解接收波形和 TDR")
    for i in range(0, len(s), 128):
        progress.check_cancel()
        sl = slice(i, i + 128)
        k = s[sl]
        y, h = _transfer(electrical, paths, k, 1 / settings.load_ohm + k * settings.load_pf * .001)
        source = settings.high_v * drive[sl] / (1 + rs[:, None] * y)
        out[:n_cases, sl] = source * h
        out[n_cases:-1, sl] = source
        ref = settings.reference_ohm
        yt, _ = _transfer(electrical, set(), k, 1 / ref)
        out[-1, sl] = drive[sl] * (1 - ref * yt) / (1 + ref * yt)
        progress.fraction(min((i + 128) / len(s), 1.))
    frames = irfft(out, n=n, axis=-1)[:, :len(t)] * (np.exp(sigma * t) / dt)
    rho = frames[-1]
    z = np.divide(ref * (1 + rho), 1 - rho, out=np.full_like(rho, np.nan), where=(1 - rho) > 1e-7)
    eye, note = None, ""
    if settings.eye_gbps:
        final = settings.high_v / (1 + rs[-1] / settings.load_ohm)
        eye, note = _eye(t, frames[n_cases - 1], 1 / settings.eye_gbps, arrival, final)
    return Result(channel, settings, t, frames[:n_cases], frames[n_cases:-1], z, eye, note)
