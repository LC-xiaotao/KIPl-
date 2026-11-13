"""The tools the assistant calls: KiPI's board, setup, solves and reports.

Everything runs on the UI thread, because it touches the window's panels and starts the
window's own solve tasks. A solve waits in a nested event loop until the task finishes, so
the chat stays responsive (the progress bar and the 3D view update meanwhile).
"""

from __future__ import annotations

import copy
import json
import re
import time
from typing import Any, Dict, List, Optional

from qtpy.QtCore import QEventLoop, Qt, QTimer
from qtpy.QtWidgets import QApplication

from kipi.core.model.nets import classify_nets, is_ground_name, is_power_name


def _pin(args: Dict[str, Any], prefix: str, *, required: bool = False):
    from kipi.dc.pi.model import PinRef
    net = str(args.get(f"{prefix}_net") or "")
    part = str(args.get(f"{prefix}_part") or "")
    if not net or not part:
        if required:
            raise ValueError(f"{prefix}_net and {prefix}_part are required")
        return None
    return PinRef(part, net, _pins(args.get(f"{prefix}_pins")))


def _pins(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [p.strip() for p in str(value).replace("，", ",").split(",") if p.strip()]


def _pin_dict(ref) -> Optional[dict]:
    if ref is None:
        return None
    return {"part": ref.ref, "net": ref.net, "pins": list(ref.pins)}


def _net_names(main) -> List[str]:
    snap = main.snapshot
    return sorted({n.name for n in snap.nets if n.name})


def _check_nets(main, nets) -> None:
    known = set(_net_names(main))
    missing = [n for n in nets if n not in known]
    if missing:
        raise ValueError("板卡上没有这些网络: " + ", ".join(missing[:10]))


def _check_part(main, part: str) -> None:
    refs = {f.reference for f in main.snapshot.footprints}
    if part not in refs:
        raise ValueError(f"板卡上没有位号 {part}")


def _setup(main):
    return main.solve_panel.setup


def _refresh(main) -> None:
    for panel in main._panels().values():
        try:
            panel.reload()
        except Exception:  # noqa: BLE001 - a panel not built yet, or no board
            pass
    try:
        main.solve_panel.setup_changed.emit()
    except Exception:  # noqa: BLE001
        pass


def _select_nets(main, names: List[str]) -> None:
    """Tick ``names`` in the Board panel and let the window rebuild the net selection."""
    chosen = set(names)
    main.net_list.blockSignals(True)
    try:
        for i in range(main.net_list.count()):
            item = main.net_list.item(i)
            item.setCheckState(Qt.CheckState.Checked
                               if item.data(Qt.ItemDataRole.UserRole) in chosen
                               else Qt.CheckState.Unchecked)
    finally:
        main.net_list.blockSignals(False)
    main._checked_cache = None
    main.sync_nets()


def _round(x, n=4):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


FAST_NOTE = ("快速模式：网格、扫频点或谐波已简化，结果适合快速判断；"
             "需要精确结果请关闭“快速”后重新求解。")
ATTACHMENT_READ_CHARS = 7_000


def _attachment_page(attachment, offset: int) -> Optional[int]:
    if not attachment.pages:
        return None
    text = attachment.full_text or ""
    hits = list(re.finditer(r"\[第 (\d+) 页\]", text[:offset + 1]))
    return int(hits[-1].group(1)) if hits else 1


def _thermal_dict(thermal) -> dict:
    return {
        "enabled": bool(thermal.enabled),
        "ambient_c": thermal.ambient_c,
        "iterations": thermal.iterations,
        "airflow_m_s": thermal.airflow_m_s,
        "grid_mm": thermal.grid_mm,
        "load_power": bool(thermal.load_power),
        "max_temp_c": thermal.max_temp_c,
        "max_rise_c": thermal.max_rise_c,
        "edges": [{"name": e.name, "temp_c": e.temp_c, "width_mm": e.width_mm,
                   "points": len(e.points)} for e in thermal.edges],
    }


def _fast_setup(setup):
    """A copy with coarser meshes, fewer sweep points and harmonics, no board model.

    The solve functions already freeze (deep-copy) their setup, and keep the frozen copy
    as ``solved_setup`` for reports, so the GUI's own setup is untouched.
    """
    fast = copy.deepcopy(setup)
    settings = fast.settings
    settings.max_edge_mm = max(settings.max_edge_mm, settings.max_edge_mm * 2.5)
    settings.min_edge_mm = max(settings.min_edge_mm, settings.min_edge_mm * 2.0)
    settings.tol = max(settings.tol, 1e-8)
    settings.max_iter = min(settings.max_iter, 1000)
    ac = fast.ac
    ac.points_per_decade = min(ac.points_per_decade, 50)
    ac.field_points_per_decade = min(ac.field_points_per_decade, 5)
    ac.max_edge_mm = max(ac.max_edge_mm, ac.max_edge_mm * 2.0)
    ac.min_edge_mm = max(ac.min_edge_mm, ac.min_edge_mm * 2.0)
    noise = fast.noise
    noise.max_harmonics = min(noise.max_harmonics, 400)
    noise.field_per_decade = min(noise.field_per_decade, 3)
    noise.board_model = False
    return fast


# ---------------------------------------------------------------------------
# Tool schema (OpenAI style; the Anthropic adapter converts it)
# ---------------------------------------------------------------------------

def _tool(name: str, description: str, properties: Dict[str, Any],
          required: Optional[List[str]] = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required or [], "additionalProperties": False}}}


def _pin_props(prefix: str, what: str) -> Dict[str, Any]:
    return {f"{prefix}_{k}": v for k, v in (
        ("net", {"type": "string", "description": f"{what}的网络名"}),
        ("part", {"type": "string", "description": f"{what}的元件位号"}),
        ("pins", {"type": "string", "description": f"{what}的引脚号，逗号分隔；留空表示全部"}),
    )}


TOOLS: List[dict] = [
    _tool("get_context", "查看当前板卡、分析模式、已选网络和设置概况。开始操作前先调用。", {}),
    _tool("list_nets", "列出网络，可按名称过滤；返回网络类型（电源/地/信号）和焊盘数。",
          {"filter": {"type": "string", "description": "只显示名称包含此文本的网络"},
           "power_only": {"type": "boolean", "description": "只列出电源和地网络"},
           "limit": {"type": "integer", "description": "最多返回多少个，默认 200"}}),
    _tool("list_parts", "列出元件（位号、参数、封装、电源网络）；可按网络或文本过滤。",
          {"net": {"type": "string", "description": "只列出在此网络上有焊盘的元件"},
           "filter": {"type": "string", "description": "只显示位号/参数/封装包含此文本的元件"},
           "limit": {"type": "integer", "description": "最多返回多少个，默认 120"}}),
    _tool("get_setup", "查看当前仿真的设置：VRM、负载、串联元件、干扰源、受害网络、探针和热分析。", {}),
    _tool("set_thermal", "配置 DC 电热耦合分析（PI 设置的 Thermal 页）：开启/关闭、环境温度、"
                         "气流、迭代次数、负载发热和温度限值。边缘恒温边界请在界面中配置。",
          {"enabled": {"type": "boolean", "description": "是否开启电热耦合分析"},
           "ambient_c": {"type": "number", "description": "环境温度 °C，默认 25"},
           "iterations": {"type": "integer", "description": "热迭代次数 1-10"},
           "airflow_m_s": {"type": "number", "description": "气流速度 m/s，0 为自然对流"},
           "grid_mm": {"type": "number", "description": "热网格尺寸 mm，0 为自动"},
           "load_power": {"type": "boolean", "description": "是否把负载功耗也作为热源"},
           "max_temp_c": {"type": "number", "description": "铜温上限 °C，可选"},
           "max_rise_c": {"type": "number", "description": "相对环境温升上限 °C，可选"},
           "clear_limits": {"type": "boolean", "description": "清除铜温/温升限值"}}),
    _tool("list_attachments", "列出当前对话上传的附件：名称、类型、页数或图片尺寸、"
                              "字数和是否完整。", {}),
    _tool("search_attachment", "在文本附件全文中搜索关键词，返回页码和上下文；"
                               "图片附件没有可搜索的文字。",
          {"name": {"type": "string", "description": "附件名，留空搜索全部附件"},
           "query": {"type": "string", "description": "关键词或短语"},
           "max_hits": {"type": "integer", "description": "最多返回多少条，默认 8"}},
          ["query"]),
    _tool("read_attachment", "读取文本附件的指定页或字符范围（每次最多约 7000 字）；"
                             "图片附件只返回名称、尺寸等元数据。",
          {"name": {"type": "string", "description": "附件名"},
           "start_page": {"type": "integer", "description": "起始页（PDF，从 1 开始）"},
           "end_page": {"type": "integer", "description": "结束页（含）"},
           "offset": {"type": "integer", "description": "字符偏移，非 PDF 或按字符读取"},
           "length": {"type": "integer", "description": "读取字符数，默认 7000"}},
          ["name"]),
    _tool("set_nets", "勾选要参与仿真的网络（板卡面板中的网络列表）。",
          {"nets": {"type": "array", "items": {"type": "string"},
                    "description": "要勾选的网络名列表"}}, ["nets"]),
    _tool("add_vrm", "添加一个 VRM（电源）。kind 为 source（理想源）、ldo、smps、isolated；"
                     "非 source 必须给输入引脚。",
          {"name": {"type": "string"}, "voltage": {"type": "number", "description": "目标电压 V"},
           "kind": {"type": "string", "enum": ["source", "ldo", "smps", "isolated"]},
           **_pin_props("output", "输出"), **_pin_props("input", "输入"),
           **_pin_props("ground", "地"),
           "efficiency": {"type": "number", "description": "效率 0-1，默认 0.9"}},
          ["name", "voltage", "output_net", "output_part"]),
    _tool("add_load", "添加一个负载（从电源网络汲取电流）。",
          {"name": {"type": "string"}, "current_a": {"type": "number"},
           **_pin_props("supply", "电源"), **_pin_props("ground", "地"),
           "tol_pct": {"type": "number", "description": "容差 ±%，可选"}},
          ["name", "current_a", "supply_net", "supply_part"]),
    _tool("remove_item", "删除设置中的一项。kind: vrm/load/link/probe/aggressor/victim/cap。",
          {"kind": {"type": "string"}, "name": {"type": "string"}}, ["kind", "name"]),
    _tool("solve_dc", "运行 DC 压降/电流密度求解，并返回负载、VRM 和网络组结果；"
                      "如果设置中开启了热分析，会同时做电热耦合迭代并返回温度。", {}),
    _tool("get_dc_results", "读取最近一次 DC 求解结果，不重新求解。", {}),
    _tool("add_noise_aggressor", "添加耦合噪声的干扰源（开关电源）。需要设置中已有同名 smps 类型的 VRM。",
          {"name": {"type": "string", "description": "干扰源名称"},
           "vrm": {"type": "string", "description": "设置中的 VRM 名称（smps 类型）"},
           "fsw_hz": {"type": "number", "description": "开关频率 Hz，默认 1e6"},
           "rise_ns": {"type": "number", "description": "上升沿 ns，默认 2"},
           "fall_ns": {"type": "number", "description": "下降沿 ns，默认 2"},
           "vin_v": {"type": "number", "description": "输入电压 V，可选"},
           "load_a": {"type": "number", "description": "输出负载电流 A，可选（默认取设置中的负载）"},
           "topology": {"type": "string", "enum": ["buck", "boost", "auto"]},
           "switch_net": {"type": "string", "description": "开关节点的网络名，可选（自动推断）"},
           "inductor": {"type": "string", "description": "功率电感位号，可选（自动推断）"},
           "inductance_h": {"type": "number", "description": "电感值 H，可选"},
           "dcr_ohm": {"type": "number", "description": "电感直流电阻 Ω，可选"},
           "inductor_shielded": {"type": "boolean", "description": "是否屏蔽电感，默认 true"}},
          ["name", "vrm"]),
    _tool("add_noise_victims", "把网络设为耦合噪声的受害网络；驱动/接收端自动取网络两端。",
          {"nets": {"type": "array", "items": {"type": "string"}},
           "logic_v": {"type": "number", "description": "逻辑电平 V，默认 3.3"},
           "preset": {"type": "string", "description": "端接类型：cmos/open_drain/series/parallel/"
                                                       "lvds/analog/hiz，默认 cmos"}},
          ["nets"]),
    _tool("solve_noise", "运行一个干扰源的耦合噪声求解，返回受害网络的峰值噪声与裕量。",
          {"aggressor": {"type": "string", "description": "干扰源名称，留空取当前/第一个"}}),
    _tool("get_noise_results", "读取最近一次耦合噪声结果，不重新求解。", {}),
    _tool("add_ac_probe", "添加 AC 阻抗探针（器件电源引脚对地）。",
          {"name": {"type": "string"},
           **_pin_props("rail", "电源"), **_pin_props("ground", "地"),
           "target_mohm": {"type": "number", "description": "目标阻抗 mΩ，可选"},
           "target_mhz": {"type": "number", "description": "目标适用的最高频率 MHz，可选"},
           "step_a": {"type": "number", "description": "负载阶跃 A，可选（用于瞬态估计）"},
           "slew_a_per_us": {"type": "number", "description": "负载阶跃压摆率 A/µs，可选"}},
          ["name", "rail_net", "rail_part", "ground_net", "ground_part"]),
    _tool("solve_ac", "对一条电源轨运行 AC PDN 阻抗扫频，返回各探针的最小/最差阻抗与判定。",
          {"vrm": {"type": "string", "description": "设置中的 VRM 名称（即电源轨）"},
           "ground": {"type": "string", "description": "地网络名，例如 GND"}},
          ["vrm", "ground"]),
    _tool("get_ac_results", "读取最近一次 AC 阻抗结果，不重新求解。", {}),
    _tool("set_mode", "切换分析模式：dc / ac / noise。",
          {"mode": {"type": "string", "enum": ["dc", "ac", "noise"]}}, ["mode"]),
    _tool("export_report", "把当前结果导出为 HTML 或 PDF 报告，返回文件路径。",
          {"kind": {"type": "string", "enum": ["dc", "ac", "noise"]},
           "fmt": {"type": "string", "enum": ["html", "pdf"]}}),
]


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class ToolRunner:
    def __init__(self, main, fast: bool = False):
        self.main = main
        self.fast = fast
        self.attachments = {}

    # -- waiting ----------------------------------------------------------
    def _pending(self) -> bool:
        return any(getattr(self.main, name, None)
                   for name in ("_pending_solve", "_pending_ac", "_pending_noise"))

    def wait_idle(self, timeout_s: float = 1800.0) -> bool:
        """Process events until the window's task (and any queued solve) is done."""
        if not self.main._busy() and not self._pending():
            return True
        deadline = time.monotonic() + timeout_s
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(100)

        def check():
            if (not self.main._busy() and not self._pending()) or time.monotonic() > deadline:
                loop.quit()

        timer.timeout.connect(check)
        timer.start()
        QTimer.singleShot(0, check)
        loop.exec()
        timer.stop()
        QApplication.processEvents()
        return not self.main._busy()

    # -- tools ------------------------------------------------------------
    def run(self, name: str, args: Dict[str, Any]) -> str:
        handler = getattr(self, f"tool_{name}", None)
        if handler is None:
            return json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
        try:
            result = handler(args or {})
        except Exception as e:  # noqa: BLE001 - the model gets the message and can retry
            result = {"error": f"{type(e).__name__}: {e}"}
        return json.dumps(result, ensure_ascii=False, default=str)

    def tool_get_context(self, args) -> dict:
        snap = self.main.snapshot
        setup = _setup(self.main)
        return {
            "board": None if snap is None else {
                "name": snap.board_name, "format": snap.format_name,
                "nets": len(snap.nets), "pads": len(snap.pads),
                "footprints": len(snap.footprints),
                "thickness_mm": _round(snap.stackup.board_thickness_mm, 3),
                "copper_layers": [c.name for c in snap.stackup.copper]},
            "mode": self.main.mode,
            "selected_nets": list(setup.nets or []),
            "setup": {"vrms": len(setup.vrms), "loads": len(setup.loads),
                      "links": len(setup.links), "probes": len(setup.probes),
                      "aggressors": len(setup.aggressors), "victims": len(setup.victims),
                      "thermal": bool(setup.thermal.enabled)},
            "has_dc_result": self.main._tree is not None,
            "has_noise_result": getattr(self.main.noise_panel, "result", None) is not None,
            "has_ac_result": getattr(self.main.ac_panel, "result", None) is not None,
        }

    def tool_list_nets(self, args) -> dict:
        snap = self.main.snapshot
        if snap is None:
            raise ValueError("还没有加载板卡。请先用“打开”加载板卡。")
        kinds = classify_nets(snap)
        pads: Dict[str, int] = {}
        for p in snap.pads:
            if p.net:
                pads[p.net] = pads.get(p.net, 0) + 1
        text = str(args.get("filter") or "").lower()
        power_only = bool(args.get("power_only"))
        limit = max(1, min(int(args.get("limit") or 200), 500))
        rows = []
        for n in snap.nets:
            if not n.name or (text and text not in n.name.lower()):
                continue
            if power_only and kinds.get(n.name) != "power" and not is_ground_name(n.name):
                continue
            rows.append({"name": n.name, "kind": kinds.get(n.name, "signal"),
                         "pads": pads.get(n.name, 0), "netclass": n.netclass})
        rows.sort(key=lambda r: (r["kind"] != "power", -r["pads"], r["name"]))
        return {"count": len(rows), "shown": len(rows[:limit]), "nets": rows[:limit]}

    def tool_list_parts(self, args) -> dict:
        snap = self.main.snapshot
        if snap is None:
            raise ValueError("还没有加载板卡。")
        net = str(args.get("net") or "")
        text = str(args.get("filter") or "").lower()
        limit = max(1, min(int(args.get("limit") or 120), 300))
        pads_by_ref: Dict[str, List] = {}
        for p in snap.pads:
            if p.footprint:
                pads_by_ref.setdefault(p.footprint, []).append(p)
        rows = []
        for f in snap.footprints:
            nets = {p.net for p in pads_by_ref.get(f.reference, []) if p.net}
            if net and net not in nets:
                continue
            hay = f"{f.reference} {f.value} {f.footprint}".lower()
            if text and text not in hay:
                continue
            rows.append({"ref": f.reference, "value": f.value, "footprint": f.footprint,
                         "side": f.side, "pads": len(pads_by_ref.get(f.reference, [])),
                         "power_nets": sorted(n for n in nets
                                              if is_power_name(n) or is_ground_name(n))[:8]})
        rows.sort(key=lambda r: r["ref"])
        return {"count": len(rows), "shown": len(rows[:limit]), "parts": rows[:limit]}

    def tool_get_setup(self, args) -> dict:
        setup = _setup(self.main)
        return {
            "selected_nets": list(setup.nets or []),
            "vrms": [{"name": v.name, "kind": v.kind, "voltage": v.voltage,
                      "output": _pin_dict(v.output), "input": _pin_dict(v.input),
                      "ground": _pin_dict(v.ground), "efficiency": v.efficiency,
                      "current_limit_a": v.current_limit_a} for v in setup.vrms],
            "loads": [{"name": l.name, "current_a": l.total_current(),
                       "supply": _pin_dict(l.supply), "ground": _pin_dict(l.ground),
                       "tolerance": l.tolerance_label()} for l in setup.loads],
            "links": [{"name": k.name, "a": _pin_dict(k.side_a), "b": _pin_dict(k.side_b)}
                      for k in setup.links],
            "aggressors": [{"name": a.name, "vrm": a.vrm, "fsw_hz": a.fsw_hz,
                            "topology": a.topology, "phases": len(a.phases)}
                           for a in setup.aggressors],
            "victims": [{"net": v.net, "preset": v.preset, "logic_v": v.logic_v,
                         "driver": _pin_dict(v.driver), "receiver": _pin_dict(v.receiver)}
                        for v in setup.victims],
            "probes": [{"name": p.name, "rail": _pin_dict(p.rail),
                        "ground": _pin_dict(p.ground)} for p in setup.probes],
            "thermal": _thermal_dict(setup.thermal),
        }

    def tool_set_thermal(self, args) -> dict:
        main = self.main
        if main.snapshot is None:
            raise ValueError("还没有加载板卡。")
        thermal = _setup(main).thermal
        if args.get("enabled") is not None:
            thermal.enabled = bool(args["enabled"])
        if args.get("ambient_c") is not None:
            thermal.ambient_c = max(-55.0, min(200.0, float(args["ambient_c"])))
        if args.get("iterations") is not None:
            thermal.iterations = max(1, min(10, int(args["iterations"])))
        if args.get("airflow_m_s") is not None:
            thermal.airflow_m_s = max(0.0, float(args["airflow_m_s"]))
        if args.get("grid_mm") is not None:
            thermal.grid_mm = max(0.0, float(args["grid_mm"]))
        if args.get("load_power") is not None:
            thermal.load_power = bool(args["load_power"])
        if args.get("clear_limits"):
            thermal.max_temp_c = None
            thermal.max_rise_c = None
        if args.get("max_temp_c") is not None:
            thermal.max_temp_c = float(args["max_temp_c"])
        if args.get("max_rise_c") is not None:
            thermal.max_rise_c = float(args["max_rise_c"])
        _refresh(main)
        return {"thermal": _thermal_dict(thermal)}

    def tool_list_attachments(self, args) -> dict:
        attachments = []
        for attachment in self.attachments.values():
            attachments.append({
                "name": attachment.name, "note": attachment.note,
                "kind": attachment.kind,
                "mime": attachment.mime or None,
                "width": attachment.width or None,
                "height": attachment.height or None,
                "byte_size": attachment.byte_size or None,
                "pages": len(attachment.pages) or None,
                "chars": attachment.chars,
                "sent_chars": len(attachment.text),
                "complete": attachment.complete,
                "preview": (attachment.text[:300] + "…"
                            if len(attachment.text) > 300 else attachment.text),
            })
        return {"count": len(attachments), "attachments": attachments}

    def tool_search_attachment(self, args) -> dict:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query 不能为空")
        name = str(args.get("name") or "").strip()
        limit = max(1, min(int(args.get("max_hits") or 8), 20))
        matched = [a for a in self.attachments.values()
                   if not name or a.name == name]
        if not matched:
            raise ValueError("当前对话没有这个附件")
        images = [a for a in matched if a.is_image]
        selected = [a for a in matched if not a.is_image]
        hits = []
        needle = query.lower()
        for attachment in selected:
            text = attachment.full_text or attachment.text
            lowered = text.lower()
            start = 0
            while len(hits) < limit:
                index = lowered.find(needle, start)
                if index < 0:
                    break
                left = max(0, index - 250)
                right = min(len(text), index + len(query) + 250)
                hits.append({"name": attachment.name,
                             "page": _attachment_page(attachment, index),
                             "offset": index, "snippet": text[left:right]})
                start = index + max(1, len(query))
        result = {"query": query, "count": len(hits), "hits": hits}
        if images:
            result["image_names"] = [a.name for a in images]
            result["note"] = "图片附件没有可搜索的文字；请直接查看随消息发送的图片。"
        return result

    def tool_read_attachment(self, args) -> dict:
        name = str(args.get("name") or "").strip()
        attachment = self.attachments.get(name)
        if attachment is None:
            raise ValueError(f"当前对话没有附件 {name}")
        if attachment.is_image:
            return {"name": attachment.name, "kind": "image",
                    "mime": attachment.mime, "width": attachment.width,
                    "height": attachment.height, "chars": 0, "text": "",
                    "note": "这是图片附件，没有可读取的文字内容；"
                            "请直接查看随消息发送的图片。"}
        start_page = args.get("start_page")
        end_page = args.get("end_page")
        if attachment.pages and (start_page is not None or end_page is not None):
            first = max(1, int(start_page or 1))
            last = min(len(attachment.pages), int(end_page or first))
            if first > len(attachment.pages):
                raise ValueError(f"起始页超出范围（共 {len(attachment.pages)} 页）")
            if last < first:
                raise ValueError("end_page 不能小于 start_page")
            full = "\n\n".join(f"[第 {n} 页]\n{t}" for n, t in attachment.pages
                               if first <= n <= last)
            text = full[:ATTACHMENT_READ_CHARS]
            return {"name": attachment.name, "start_page": first, "end_page": last,
                    "total_pages": len(attachment.pages), "chars": len(full),
                    "text": text, "truncated": len(text) < len(full)}
        full = attachment.full_text or attachment.text
        offset = max(0, int(args.get("offset") or 0))
        length = max(1, min(int(args.get("length") or ATTACHMENT_READ_CHARS), 20_000))
        text = full[offset:offset + length]
        return {"name": attachment.name, "offset": offset, "total_chars": len(full),
                "chars": len(text), "text": text,
                "truncated": offset + len(text) < len(full)}

    def tool_set_nets(self, args) -> dict:
        snap = self.main.snapshot
        if snap is None:
            raise ValueError("还没有加载板卡。")
        wanted = [str(n) for n in args.get("nets") or []]
        _check_nets(self.main, wanted)
        _select_nets(self.main, wanted)
        return {"selected_nets": sorted(set(wanted))}

    def tool_add_vrm(self, args) -> dict:
        from kipi.dc.pi.model import Vrm
        main = self.main
        if main.snapshot is None:
            raise ValueError("还没有加载板卡。")
        name = str(args.get("name") or "").strip()
        if not name:
            raise ValueError("name 不能为空")
        output = _pin(args, "output", required=True)
        _check_nets(main, [output.net])
        _check_part(main, output.ref)
        kind = str(args.get("kind") or "source")
        if kind not in ("source", "ldo", "smps", "isolated"):
            raise ValueError("kind 必须是 source/ldo/smps/isolated")
        inp = _pin(args, "input")
        ground = _pin(args, "ground")
        if kind != "source" and inp is None:
            raise ValueError(f"{kind} 需要 input_net 和 input_part")
        for _ref, pin in (("input", inp), ("ground", ground)):
            if pin is not None:
                _check_nets(main, [pin.net])
                _check_part(main, pin.ref)
        setup = _setup(main)
        for other in setup.vrms:
            if other.name != name and other.output.net == output.net:
                raise ValueError(f"网络 {output.net} 已由 VRM {other.name} 驱动；"
                                 f"请先用 remove_item 删除它，或改用其他网络")
        setup.vrms = [v for v in setup.vrms if v.name != name]
        setup.vrms.append(Vrm(name, output, float(args.get("voltage")), kind=kind,
                              input=inp, ground=ground,
                              efficiency=float(args.get("efficiency") or 0.9)))
        nets = set(setup.nets or [])
        nets |= {r.net for r in (output, inp, ground) if r is not None and r.net}
        _select_nets(main, sorted(nets))
        _refresh(main)
        return {"added": name, "kind": kind, "output": _pin_dict(output),
                "input": _pin_dict(inp), "ground": _pin_dict(ground)}

    def tool_add_load(self, args) -> dict:
        from kipi.dc.pi.model import Load
        main = self.main
        if main.snapshot is None:
            raise ValueError("还没有加载板卡。")
        name = str(args.get("name") or "").strip()
        supply = _pin(args, "supply", required=True)
        _check_nets(main, [supply.net])
        _check_part(main, supply.ref)
        ground = _pin(args, "ground")
        if ground is not None:
            _check_nets(main, [ground.net])
            _check_part(main, ground.ref)
        tol = args.get("tol_pct")
        setup = _setup(main)
        setup.loads = [l for l in setup.loads if l.name != name]
        setup.loads.append(Load(
            name, supply, float(args.get("current_a")),
            ground=ground,
            tol_min=None if tol is None else -abs(float(tol)),
            tol_max=None if tol is None else abs(float(tol))))
        nets = set(setup.nets or [])
        nets |= {r.net for r in (supply, ground) if r is not None and r.net}
        _select_nets(main, sorted(nets))
        _refresh(main)
        return {"added": name, "current_a": float(args.get("current_a")),
                "supply": _pin_dict(supply), "ground": _pin_dict(ground)}

    def tool_remove_item(self, args) -> dict:
        setup = _setup(self.main)
        kind = str(args.get("kind") or "").lower()
        name = str(args.get("name") or "")
        attr = {"vrm": "vrms", "load": "loads", "link": "links", "probe": "probes",
                "aggressor": "aggressors", "victim": "victims", "cap": "caps"}.get(kind)
        if attr is None:
            raise ValueError("kind 必须是 vrm/load/link/probe/aggressor/victim/cap")
        items = getattr(setup, attr)
        before = len(items)
        if kind == "victim":
            items[:] = [x for x in items if x.net != name and x.name != name]
        else:
            items[:] = [x for x in items if getattr(x, "name", None) != name]
        if len(items) == before:
            raise ValueError(f"没有找到 {kind} {name}")
        _refresh(self.main)
        return {"removed": f"{kind} {name}"}

    def tool_solve_dc(self, args) -> dict:
        main = self.main
        setup = _setup(main)
        if not setup.vrms:
            raise ValueError("设置中没有 VRM。请先 add_vrm。")
        if not setup.nets:
            raise ValueError("没有勾选网络。请先 set_nets 勾选电源轨网络。")
        used = _fast_setup(setup) if self.fast else setup
        started = time.monotonic()
        main._last_solve_error = None
        main.run_solve(used)
        if not self.wait_idle():
            raise RuntimeError("DC 求解超时或仍在运行")
        if getattr(main, "_last_solve_error", None):
            raise RuntimeError(main._last_solve_error)
        result = self.tool_get_dc_results({})
        result["elapsed_s"] = round(time.monotonic() - started, 2)
        if self.fast:
            result["fast"] = True
            result["note"] = FAST_NOTE
        return result

    def tool_get_dc_results(self, args) -> dict:
        tree = self.main._tree
        if tree is None:
            raise ValueError("还没有 DC 结果。请先 solve_dc。")
        loads = [{"name": l.name, "current_a": _round(l.current, 5),
                  "voltage_v": _round(l.v_effective, 6),
                  "drop_mv": _round(l.drop * 1e3, 4),
                  "drop_pct": _round(getattr(l, "drop_pct", 0.0), 4),
                  "worst_pin_mv": _round(getattr(l, "drop_worst", l.drop) * 1e3, 4),
                  "passed": l.passed, "status": l.status}
                 for l in tree.loads]
        vrms = [{"name": v.name, "kind": v.kind, "v_out_v": _round(v.v_out, 6),
                 "i_out_a": _round(v.i_out, 5), "v_in_v": _round(v.v_in, 5)
                 if v.v_in is not None else None,
                 "p_loss_w": _round(v.p_loss, 6) if v.p_loss is not None else None}
                for v in tree.vrms]
        groups = []
        for name, g in tree.groups.items():
            s = g.result.fields.summary
            groups.append({"name": name, "max_drop_mv": _round(s.get("max_drop", 0) * 1e3, 4),
                           "max_boost_mv": _round(s.get("max_boost", 0) * 1e3, 4),
                           "peak_current_density_a_mm2": _round(s.get("j_max", 0), 3),
                           "copper_loss_mw": _round(s.get("power_loss", 0) * 1e3, 4),
                           "max_via_current_a": _round(s.get("via_current_max", 0), 4)})
        thermal = None
        th = getattr(tree, "thermal", None)
        if th is not None and self.main.snapshot is not None:
            from kipi.dc.pi.report import layer_temps, limits_text, thermal_passed
            rows = layer_temps(tree, self.main.snapshot, th.settings)
            thermal = {
                "ambient_c": th.settings.ambient_c,
                "airflow_m_s": th.settings.airflow_m_s,
                "max_temp_c": th.settings.max_temp_c,
                "max_rise_c": th.settings.max_rise_c,
                "limits": limits_text(th.settings),
                "passed": thermal_passed(rows),
                "heat_w": _round(th.heat_w, 6),
                "heat_by_kind": {k: _round(v, 6) for k, v in th.heat_by_kind.items()},
                "iterations": len(th.history),
                "layers": [{"layer": r.layer, "peak_c": _round(r.t_max, 4),
                            "rise_c": _round(r.rise, 4), "x_mm": _round(r.x, 4),
                            "y_mm": _round(r.y, 4), "group": r.group,
                            "passed": r.passed} for r in rows],
            }
        return {"loads": loads, "vrms": vrms, "groups": groups,
                "thermal": thermal, "warnings": list(tree.warnings or [])}

    def tool_add_noise_aggressor(self, args) -> dict:
        from kipi.noise.checks import seed_phases
        from kipi.noise.model import Aggressor
        main = self.main
        if main.snapshot is None:
            raise ValueError("还没有加载板卡。")
        name = str(args.get("name") or "").strip()
        vrm_name = str(args.get("vrm") or "").strip()
        setup = _setup(main)
        vrm = next((v for v in setup.vrms if v.name == vrm_name), None)
        if vrm is None:
            raise ValueError(f"没有名为 {vrm_name} 的 VRM。请先 add_vrm 创建 smps 类型的 VRM。")
        if vrm.kind == "source":
            raise ValueError(f"{vrm_name} 是理想源；耦合噪声需要 smps 类型的 VRM（带输入和地）")
        if vrm.input is None:
            raise ValueError(f"{vrm_name} 没有输入引脚，无法建立开关回路")
        topology = str(args.get("topology") or "buck")
        if topology == "auto":
            topology = "buck" if vrm.input.net and vrm.voltage < 5.5 else "boost"
        phases = seed_phases(main.snapshot, setup, vrm, topology)
        if not phases:
            raise ValueError("无法从板卡推断功率级（电感/开关节点）")
        ph = phases[0]
        if args.get("switch_net"):
            ph.switch_net = str(args["switch_net"])
        if args.get("inductor"):
            ph.inductor = str(args["inductor"])
        if args.get("inductance_h"):
            ph.inductance_h = float(args["inductance_h"])
        if args.get("dcr_ohm") is not None:
            ph.dcr_ohm = float(args["dcr_ohm"])
        if args.get("inductor_shielded") is not None:
            ph.inductor_shielded = bool(args["inductor_shielded"])
        if not ph.inductance_h:
            raise ValueError(f"没有读到 {ph.inductor or '电感'} 的电感值；请给 inductance_h")
        agg = Aggressor(name, vrm=vrm_name, topology=topology,
                        vin_v=args.get("vin_v"), load_a=args.get("load_a"),
                        fsw_hz=float(args.get("fsw_hz") or 1e6),
                        rise_s=float(args.get("rise_ns") or 2) * 1e-9,
                        fall_s=float(args.get("fall_ns") or 2) * 1e-9, phases=phases)
        setup.aggressors = [a for a in setup.aggressors if a.name != name]
        setup.aggressors.append(agg)
        setup.noise.aggressor = name
        _refresh(main)
        return {"added": name, "vrm": vrm_name, "topology": topology,
                "switch_net": ph.switch_net, "inductor": ph.inductor,
                "inductance_h": ph.inductance_h, "input_caps": ph.input_caps,
                "output_caps": ph.output_caps,
                "high_side": _pin_dict(ph.high_side), "low_side": _pin_dict(ph.low_side)}

    def tool_add_noise_victims(self, args) -> dict:
        from kipi.noise.checks import guess_ends
        from kipi.noise.model import Victim
        main = self.main
        if main.snapshot is None:
            raise ValueError("还没有加载板卡。")
        nets = [str(n) for n in args.get("nets") or []]
        _check_nets(main, nets)
        preset = str(args.get("preset") or "cmos")
        logic = float(args.get("logic_v") or 3.3)
        setup = _setup(main)
        setup.victims = [v for v in setup.victims if v.net not in nets]
        rows = []
        for net in nets:
            drv, rcv = guess_ends(main.snapshot, net)
            setup.victims.append(Victim(net, driver=drv, receiver=rcv, preset=preset,
                                        logic_v=logic))
            rows.append({"net": net, "driver": _pin_dict(drv), "receiver": _pin_dict(rcv)})
        _refresh(main)
        return {"added": rows, "preset": preset, "logic_v": logic}

    def tool_solve_noise(self, args) -> dict:
        main = self.main
        setup = _setup(main)
        if not setup.aggressors:
            raise ValueError("设置中没有干扰源。请先 add_noise_aggressor。")
        name = str(args.get("aggressor") or setup.noise.aggressor
                   or setup.aggressors[0].name)
        if not any(a.name == name for a in setup.aggressors):
            raise ValueError(f"没有名为 {name} 的干扰源")
        if main.mode != "noise":
            main.set_mode("noise")
        used = _fast_setup(setup) if self.fast else setup
        started = time.monotonic()
        main._last_noise_error = None
        main.run_noise_solve(used, name)
        if not self.wait_idle(timeout_s=3600):
            raise RuntimeError("噪声求解超时或仍在运行")
        if getattr(main, "_last_noise_error", None):
            raise RuntimeError(main._last_noise_error)
        if main.noise_panel.result is None:
            raise RuntimeError("求解结束但没有结果")
        result = self.tool_get_noise_results({})
        result["elapsed_s"] = round(time.monotonic() - started, 2)
        if self.fast:
            result["fast"] = True
            result["note"] = FAST_NOTE
        return result

    def tool_get_noise_results(self, args) -> dict:
        result = getattr(self.main.noise_panel, "result", None)
        if result is None:
            raise ValueError("还没有噪声结果。请先 solve_noise。")
        victims = [{"net": v.net, "peak_mv": _round(v.peak_v * 1e3, 4),
                    "margin_mv": _round(v.margin_v * 1e3, 3),
                    "ratio": _round(v.ratio, 4), "passed": v.passed,
                    "dominant": v.dominant,
                    "by_mechanism_mv": {k: _round(x * 1e3, 4)
                                        for k, x in v.peak_by.items()}}
                   for v in result.victims]
        victims.sort(key=lambda v: -v["peak_mv"])
        return {"aggressor": result.aggressor,
                "operating": list(result.operating.notes),
                "victims": victims,
                "warnings": list(result.warnings or [])}

    def tool_add_ac_probe(self, args) -> dict:
        from kipi.ac.model import Probe
        main = self.main
        if main.snapshot is None:
            raise ValueError("还没有加载板卡。")
        name = str(args.get("name") or "").strip()
        rail = _pin(args, "rail", required=True)
        ground = _pin(args, "ground", required=True)
        for pin in (rail, ground):
            _check_nets(main, [pin.net])
            _check_part(main, pin.ref)
        setup = _setup(main)
        setup.probes = [p for p in setup.probes if p.name != name]
        setup.probes.append(Probe(
            name, rail, ground,
            target_ohm=(float(args["target_mohm"]) / 1e3
                        if args.get("target_mohm") else None),
            target_hz=(float(args["target_mhz"]) * 1e6
                       if args.get("target_mhz") else None),
            step_a=float(args["step_a"]) if args.get("step_a") else None,
            slew_a_per_us=(float(args["slew_a_per_us"])
                           if args.get("slew_a_per_us") else None)))
        nets = set(setup.nets or []) | {rail.net, ground.net}
        _select_nets(main, sorted(nets))
        _refresh(main)
        return {"added": name, "rail": _pin_dict(rail), "ground": _pin_dict(ground)}

    def tool_solve_ac(self, args) -> dict:
        main = self.main
        setup = _setup(main)
        vrm = str(args.get("vrm") or "").strip()
        ground = str(args.get("ground") or "").strip()
        if not any(v.name == vrm for v in setup.vrms):
            raise ValueError(f"没有名为 {vrm} 的 VRM")
        _check_nets(main, [ground])
        if main.mode != "ac":
            main.set_mode("ac")
        used = _fast_setup(setup) if self.fast else setup
        started = time.monotonic()
        main._last_ac_error = None
        main.run_ac_solve(used, vrm, ground)
        if not self.wait_idle(timeout_s=3600):
            raise RuntimeError("AC 求解超时或仍在运行")
        if getattr(main, "_last_ac_error", None):
            raise RuntimeError(main._last_ac_error)
        result = self.tool_get_ac_results({"vrm": vrm})
        result["elapsed_s"] = round(time.monotonic() - started, 2)
        if self.fast:
            result["fast"] = True
            result["note"] = FAST_NOTE
        return result

    def tool_get_ac_results(self, args) -> dict:
        panel = self.main.ac_panel
        held = panel.held_results() if hasattr(panel, "held_results") else {}
        want = str(args.get("vrm") or "")
        result = held.get(want) if want else (getattr(panel, "result", None)
                                              or next(iter(held.values()), None))
        if result is None:
            raise ValueError("还没有 AC 结果。请先 solve_ac。")
        probes = []
        for c in result.probes:
            zmax, fmax = c.worst(result.freqs)
            probes.append({
                "name": c.name, "min_z_mohm": _round(float(min(c.mag)) * 1e3, 4),
                "worst_z_mohm": _round(float(zmax) * 1e3, 4),
                "at_mhz": _round(float(fmax) / 1e6, 4),
                "target_ohm": c.target_ohm, "passed": c.passed(result.freqs),
            })
        return {"rail": result.rail, "nets": list(result.rail_nets),
                "ground": result.ground, "probes": probes,
                "plane_capacitance_nf": _round(result.plane_capacitance_f * 1e9, 4),
                "warnings": list(result.warnings or [])}

    def tool_set_mode(self, args) -> dict:
        mode = str(args.get("mode") or "")
        if mode not in ("dc", "ac", "noise"):
            raise ValueError("mode 必须是 dc/ac/noise")
        self.main.set_mode(mode)
        return {"mode": mode}

    def tool_export_report(self, args) -> dict:
        main = self.main
        kind = str(args.get("kind") or "dc")
        fmt = str(args.get("fmt") or "html")
        if fmt not in ("html", "pdf"):
            raise ValueError("fmt 必须是 html 或 pdf")
        if kind == "dc":
            if main._tree is None:
                raise ValueError("还没有 DC 结果")
            main._dc_report(fmt)
            result = main._tree
        elif kind == "ac":
            result = getattr(main.ac_panel, "result", None)
            if result is None:
                raise ValueError("还没有 AC 结果")
            main._ac_report(result, fmt)
        else:
            result = getattr(main.noise_panel, "result", None)
            if result is None:
                raise ValueError("还没有噪声结果")
            main._noise_report(result, fmt)
        if not self.wait_idle(timeout_s=1800):
            raise RuntimeError("报告生成超时")
        path = getattr(result, "report_path", "")
        if not path:
            raise RuntimeError("报告没有生成")
        return {"report": str(path)}
