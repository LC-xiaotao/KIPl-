"""Extract a single-ended, tree-shaped routed net and its local quasi-TEM line constants."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import dist, sqrt

from scipy.cluster.hierarchy import DisjointSet
from shapely import STRtree
from shapely.geometry import LineString, Point

from kipi.core.geometry.copper import poly_to_shapely
from kipi.core.progress import NULL
from kipi.noise.extract.capacitive import BoardCuts, Segment, split_tracks
from kipi.noise.extract.xsection import Cache, GROUND


@dataclass(frozen=True)
class Section:
    parent: int
    child: int
    a: tuple
    b: tuple
    layer: int
    ohms: float
    flight_ns: float


@dataclass
class Channel:
    # Root is node 0. Every section is visited after its parent.
    sections: list[Section]
    receiver: int

    def route(self):
        incoming = {s.child: s for s in self.sections}
        node = self.receiver
        out = []
        while node:
            section = incoming[node]
            out.append(section)
            node = section.parent
        return out[::-1]

    def locate(self, round_trip_ns):
        """First-arrival estimate on the selected TX–RX path, excluding later echoes."""
        elapsed = 0.0
        length = 0.0
        for s in self.route():
            dt = 2 * s.flight_ns
            if elapsed <= round_trip_ns <= elapsed + dt:
                f = (round_trip_ns - elapsed) / dt
                xy = tuple(a + f * (b - a) for a, b in zip(s.a, s.b))
                return s, xy, length + f * dist(s.a, s.b)
            elapsed += dt
            length += dist(s.a, s.b)
        return None


def _topology(snap, net, segments, tx, rx, progress):
    """Node the copper centre lines by layer, then join actual pads and plated vias."""
    _, vias, pads, _ = snap.items_on_net(net)
    by_layer = defaultdict(list)
    for s in segments:
        by_layer[s.layer].append(s)
    copper_contacts = defaultdict(list)
    for pad in pads:
        for layer, polys in pad.shapes.items():
            key = ("pad", pad.id, "plated" if pad.pad_type == "pth" else layer)
            for poly in polys:
                geom = poly_to_shapely(poly)
                if geom is not None and not geom.is_empty:
                    copper_contacts[layer].append((geom, key))
    for via in vias:
        key = ("via", via.id, tuple(via.position))
        for layer in via.layers:
            diameter = via.pad_diameter(layer)
            if diameter > 0:
                copper_contacts[layer].append((Point(via.position).buffer(diameter / 2), key))
    joins = DisjointSet()
    edges = []

    def vertex(layer, xy):
        key = (layer, round(xy[0], 6), round(xy[1], 6))
        joins.add(key)
        return key

    for layer in sorted(by_layer.keys() | copper_contacts.keys()):
        progress.check_cancel()
        tracks = by_layer[layer]
        lines = [LineString([s.a, s.b]) for s in tracks]
        tree = STRtree(lines)
        breaks = [{0., line.length} for line in lines]
        for i, line in enumerate(lines):
            for j in tree.query(line, predicate="intersects"):
                if j <= i:
                    continue
                hit = line.intersection(lines[j])
                if hit.geom_type != "Point":
                    raise ValueError("所选网络有重叠走线，请先合并重叠铜线。")
                breaks[i].add(line.project(hit))
                breaks[j].add(lines[j].project(hit))

        contacts = copper_contacts[layer]
        contact_tree = STRtree([shape for shape, _ in contacts])
        for index, (contact, key) in enumerate(contacts):
            joins.add(key)
            # A via in a surface pad may immediately escape on a different layer.
            for j in contact_tree.query(contact, predicate="intersects"):
                if j < index:
                    joins.merge(key, contacts[j][1])
            for i in tree.query(contact, predicate="intersects"):
                portion = lines[i].intersection(contact)
                for part in getattr(portion, "geoms", (portion,)):
                    for xy in (part.coords[0], part.coords[-1]):
                        breaks[i].add(lines[i].project(Point(xy)))
                        joins.merge(key, vertex(layer, xy))
        for i, (line, s) in enumerate(zip(lines, tracks)):
            cuts = sorted(breaks[i])
            for lo, hi in zip(cuts, cuts[1:]):
                a, b = line.interpolate(lo).coords[0], line.interpolate(hi).coords[0]
                if hi - lo > 1e-6:
                    edges.append((vertex(layer, a), vertex(layer, b), Segment(a, b, layer, s.width_mm)))

    graph = defaultdict(list)
    for i, (a, b, s) in enumerate(edges):
        a, b = joins[a], joins[b]
        if a != b:
            graph[a].append((b, i, s, False))
            graph[b].append((a, i, s, True))

    def port(pad_id):
        roots = {joins[k] for k in joins if k[:2] == ("pad", pad_id) and joins[k] in graph}
        if len(roots) != 1:
            raise ValueError(f"焊盘 {pad_id} 缺少唯一的走线连接，请检查焊盘铜形状和层。")
        return roots.pop()

    start, end = port(tx), port(rx)
    if start == end:
        raise ValueError("两个端口位于同一个电气节点。")
    nodes = {start: 0}
    queue = deque([(start, -1)])
    ordered = []
    while queue:
        a, previous = queue.popleft()
        for b, index, s, reverse in graph[a]:
            if index == previous:
                continue
            if b in nodes:
                raise ValueError("当前仅支持点对点或树形分支，所选信号网络含有闭环。")
            nodes[b] = len(nodes)
            queue.append((b, index))
            ordered.append((nodes[a], nodes[b], s, reverse))
    if end not in nodes:
        raise ValueError("发送端和接收端之间没有连续的铜线或过孔。")
    return ordered, nodes[end]


def extract_channel(snap, net, reference, tx, rx, default_er=4.3, progress=NULL):
    if not reference or net == reference or tx == rx:
        raise ValueError("请选择不同的信号与参考网络，以及两个不同的收发焊盘。")
    if not snap.stackup.copper:
        raise ValueError("板数据缺少铜层叠层。")
    if any(any(zone.filled.values()) for zone in snap.items_on_net(net)[3]):
        raise ValueError("信号网络带有铺铜，本版仅能求解由走线、焊盘和过孔组成的信号通道。")
    progress.stage("提取信号网络连接")
    segments = split_tracks(snap, net, 2.0)
    edges, receiver = _topology(snap, net, segments, tx, rx, progress)
    progress.stage("计算走线截面阻抗和延迟")
    cuts = BoardCuts(snap, net, [], max(3., 4 * snap.stackup.board_thickness_mm),
                     default_er=default_er, reference_net=reference)
    cache = Cache()
    sections = []
    for i, (a, b, seg, reverse) in enumerate(edges):
        progress.check_cancel()
        rects, bands, box = cuts.section(seg)
        if not any(rect.group == GROUND for rect in rects):
            raise ValueError(f"坐标 {seg.a} 附近缺少参考网络 {reference} 的铜，无法提取局部阻抗。")
        result = cache.solve(rects, bands, box)
        delay = seg.length_mm * sqrt(result.l_h_per_mm * result.c_f_per_mm) * 1e9
        xy = (seg.b, seg.a) if reverse else (seg.a, seg.b)
        sections.append(Section(a, b, *xy, seg.layer, result.z0_ohm, delay))
        if i % 32 == 0:
            progress.fraction((i + 1) / len(edges))
    return Channel(sections, receiver)
