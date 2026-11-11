"""The AI assistant's provider requests, response parsing and tools."""

import dataclasses
import json
import os

import pytest

pytest.importorskip("qtpy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtCore import Qt, QSettings, QUrl  # noqa: E402
from qtpy.QtWidgets import QApplication, QListWidget, QListWidgetItem  # noqa: E402

from kipi.core.model.board import (  # noqa: E402
    BoardSnapshot, Footprint, Net, Pad, Poly, Stackup, Track,
)
from kipi.core.model.layers import B_CU, F_CU  # noqa: E402
from kipi.dc.pi.model import PISetup  # noqa: E402
from kipi.gui.assistant import providers  # noqa: E402
from kipi.gui.assistant.providers import (  # noqa: E402
    Config, ModelInfo, build_request, parse_response,
)
from kipi.gui.assistant.tools import TOOLS, ToolRunner  # noqa: E402

app = QApplication.instance() or QApplication([])


def _square(x, y, s=1.0):
    h = s / 2
    return [(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]


def _board():
    nets = [Net(i, n) for i, n in enumerate(["", "3V3", "GND", "SIG"])]
    pads = [
        Pad("L1.2", "3V3", "L1", "2", (10, 10), "smd", shapes={F_CU: [Poly(_square(10, 10))]}),
        Pad("U1.1", "3V3", "U1", "1", (20, 10), "smd", shapes={F_CU: [Poly(_square(20, 10))]}),
        Pad("U1.2", "GND", "U1", "2", (20, 12), "smd", shapes={F_CU: [Poly(_square(20, 12))]}),
        Pad("L1.1", "SW", "L1", "1", (12, 10), "smd", shapes={F_CU: [Poly(_square(12, 10))]}),
        Pad("U2.1", "3V3", "U2", "1", (30, 10), "smd", shapes={F_CU: [Poly(_square(30, 10))]}),
        Pad("U2.2", "GND", "U2", "2", (30, 12), "smd", shapes={F_CU: [Poly(_square(30, 12))]}),
    ]
    fps = [
        Footprint("fL1", "L1", "1.5uH", (10, 10), "top", ["L1.1", "L1.2"]),
        Footprint("fU1", "U1", "PMIC", (20, 10), "top", ["U1.1", "U1.2"]),
        Footprint("fU2", "U2", "LOAD", (30, 10), "top", ["U2.1", "U2.2"]),
    ]
    tracks = [Track("3V3", F_CU, 0.4, (10, 10), (30, 10))]
    copper = [type("C", (), {"id": F_CU, "name": "F.Cu", "index": 0, "thickness_mm": 0.035,
                             "z_bottom_mm": 1.5}),
              type("C", (), {"id": B_CU, "name": "B.Cu", "index": 1, "thickness_mm": 0.035,
                             "z_bottom_mm": 0.0})]
    stack = Stackup(copper=copper, dielectrics=[], board_thickness_mm=1.6)
    snap = BoardSnapshot("test", ".", stack, nets, tracks, [], pads, fps, [], [], "test")
    snap.invalidate_index()
    return snap


class _Signal:
    def emit(self):
        pass


class _Panel:
    def __init__(self, setup):
        self.setup = setup
        self.setup_changed = _Signal()

    def reload(self):
        pass


class _Main:
    def __init__(self):
        self.snapshot = _board()
        self.mode = "dc"
        self.solve_panel = _Panel(PISetup())
        self.ac_panel = _Panel(self.solve_panel.setup)
        self.noise_panel = _Panel(self.solve_panel.setup)
        self.net_list = QListWidget()
        for name in ("3V3", "GND", "SIG"):
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.net_list.addItem(item)
        self._tree = None
        self._last_solve_error = None
        self._pending_solve = self._pending_ac = self._pending_noise = None

    def _panels(self):
        return {"dc": self.solve_panel, "ac": self.ac_panel, "noise": self.noise_panel}

    def sync_nets(self):
        checked = {self.net_list.item(i).data(Qt.ItemDataRole.UserRole)
                   for i in range(self.net_list.count())
                   if self.net_list.item(i).checkState() == Qt.CheckState.Checked}
        self.solve_panel.setup.nets = sorted(checked)

    def _busy(self):
        return False

    def set_mode(self, mode):
        self.mode = mode


def test_reasoning_is_parsed_for_openai_and_anthropic():
    cfg = Config(provider="DeepSeek", api_key="k")
    turn = parse_response(cfg, {"choices": [{"message": {
        "content": "答案", "reasoning_content": "先想一下"}}]})
    assert turn.text == "答案" and turn.thinking == "先想一下"

    turn = parse_response(cfg, {"choices": [{"message": {
        "content": "答案", "reasoning_details": [
            {"type": "reasoning.text", "text": "细节推理"}]}}]})
    assert turn.thinking == "细节推理"

    anthropic = Config(provider="Anthropic", base_url="https://api.anthropic.com/v1",
                       model="claude", api_key="k")
    turn = parse_response(anthropic, {"content": [
        {"type": "thinking", "thinking": "推理过程", "signature": "s"},
        {"type": "text", "text": "答案"},
        {"type": "tool_use", "id": "t1", "name": "get_context", "input": {}}]})
    assert turn.thinking == "推理过程" and turn.text == "答案"
    assert turn.tool_calls[0].name == "get_context"


def test_assistant_markdown_is_rendered():
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock._append("助手", "**粗体**\n\n- 第一项\n- 第二项\n\n`code`", markdown=True)
    rendered = dock.view.toHtml()
    assert "font-weight:700" in rendered
    assert "<ul" in rendered.lower()
    assert "第一项" in dock.view.toPlainText()
    assert "**粗体**" not in dock.view.toPlainText()

    dock._append("", '{"a": "*b*", "c": "`x`"}', "#555")
    assert "*b*" in dock.view.toPlainText()


def test_the_chat_folds_reasoning_until_clicked(monkeypatch):
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock.config = Config(provider="DeepSeek", api_key="k")

    def send(config, system, history, tools):
        dock.client.done.emit({"choices": [{"message": {
            "content": "结论", "reasoning_content": "先核对网络"}}]}, "")

    monkeypatch.setattr(dock.client, "send", send)
    dock.input.setPlainText("检查板卡")
    dock._send()

    index = next(i for i, item in enumerate(dock._items) if item["kind"] == "thinking")
    assert "先核对网络" not in dock.view.toPlainText()
    assert "思考过程" in dock.view.toPlainText()

    dock._anchor_clicked(QUrl(f"kipi-thinking:{index}"))
    assert "先核对网络" in dock.view.toPlainText()

    dock._anchor_clicked(QUrl(f"kipi-thinking:{index}"))
    assert "先核对网络" not in dock.view.toPlainText()


def test_openai_request_and_parse():
    cfg = Config(provider="DeepSeek", api_key="k")
    url, headers, body = build_request(cfg, "sys", [{"role": "user", "content": "hi"}], TOOLS)
    assert url == "https://api.deepseek.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer k"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["tools"] and body["tool_choice"] == "auto"
    turn = parse_response(cfg, {"choices": [{"message": {
        "content": "好的", "tool_calls": [{"id": "c1", "type": "function",
                                          "function": {"name": "get_context",
                                                       "arguments": "{}"}}]}}]})
    assert turn.text == "好的"
    assert [(c.id, c.name, c.arguments) for c in turn.tool_calls] == [("c1", "get_context", {})]


def test_anthropic_request_folds_tool_results():
    cfg = Config(provider="Anthropic", base_url="https://api.anthropic.com/v1",
                 model="claude-sonnet-5-5", api_key="k")
    url, headers, body = build_request(cfg, "sys", [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "t1", "name": "get_context", "arguments": {}}]},
        {"role": "tool", "tool_call_id": "t1", "content": "{}"},
    ], TOOLS)
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "k" and headers["anthropic-version"]
    assert body["system"] == "sys" and body["max_tokens"] == cfg.max_tokens
    assert body["tools"][0]["input_schema"]
    messages = body["messages"]
    assert messages[1]["content"][0]["type"] == "tool_use"
    assert messages[2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]}
    turn = parse_response(cfg, {"content": [
        {"type": "text", "text": "结果"},
        {"type": "tool_use", "id": "t2", "name": "list_nets", "input": {"power_only": True}},
    ]})
    assert turn.text == "结果" and turn.tool_calls[0].arguments == {"power_only": True}


def test_tools_read_and_edit_the_setup():
    main = _Main()
    runner = ToolRunner(main)
    context = json.loads(runner.run("get_context", {}))
    assert context["board"]["name"] == "test"
    nets = json.loads(runner.run("list_nets", {"power_only": True}))
    assert {n["name"] for n in nets["nets"]} == {"3V3", "GND"}
    parts = json.loads(runner.run("list_parts", {"net": "3V3"}))
    assert {p["ref"] for p in parts["parts"]} == {"L1", "U1", "U2"}

    out = json.loads(runner.run("add_vrm", {
        "name": "3V3 buck", "voltage": 3.3, "kind": "source",
        "output_net": "3V3", "output_part": "L1", "output_pins": "2",
        "ground_net": "GND", "ground_part": "U1", "ground_pins": "2"}))
    assert out["added"] == "3V3 buck"
    setup = main.solve_panel.setup
    assert setup.vrms[0].output.ref == "L1" and setup.vrms[0].output.pins == ["2"]
    assert "3V3" in setup.nets and "GND" in setup.nets
    checked = {main.net_list.item(i).data(Qt.ItemDataRole.UserRole)
               for i in range(main.net_list.count())
               if main.net_list.item(i).checkState() == Qt.CheckState.Checked}
    assert {"3V3", "GND"} <= checked

    json.loads(runner.run("add_load", {
        "name": "core", "current_a": 0.5, "supply_net": "3V3", "supply_part": "U2",
        "supply_pins": "1", "ground_net": "GND", "ground_part": "U2", "ground_pins": "2"}))
    assert setup.loads[0].name == "core" and setup.loads[0].total_current() == 0.5
    assert json.loads(runner.run("get_setup", {}))["loads"][0]["current_a"] == 0.5

    json.loads(runner.run("remove_item", {"kind": "load", "name": "core"}))
    assert not main.solve_panel.setup.loads


def test_the_chat_runs_a_tool_and_answers(monkeypatch):
    from kipi.gui.assistant.panel import AssistantDock

    main = _Main()
    dock = AssistantDock(main)
    dock.config = Config(provider="DeepSeek", api_key="k")
    calls = []

    def send(config, system, history, tools):
        calls.append(list(history))
        if len(calls) == 1:
            dock.client.done.emit({"choices": [{"message": {
                "content": "我先看一下。",
                "tool_calls": [{"id": "c1", "type": "function",
                                "function": {"name": "get_context", "arguments": "{}"}}]}}]}, "")
        else:
            dock.client.done.emit({"choices": [{"message": {"content": "板卡名是 test。"}}]}, "")

    monkeypatch.setattr(dock.client, "send", send)
    dock.input.setPlainText("看看当前板卡")
    dock._send()
    assert [m["role"] for m in dock.history] == ["user", "assistant", "tool", "assistant"]
    assert dock.history[2]["name"] == "get_context"
    assert "test" in dock.history[3]["content"]
    assert len(calls) == 2
    assert not dock._sending


def test_tools_report_unknown_names():
    main = _Main()
    runner = ToolRunner(main)
    assert "板卡上没有这些网络" in json.loads(runner.run("set_nets", {"nets": ["nope"]}))["error"]
    assert "板卡上没有位号" in json.loads(runner.run("add_load", {
        "name": "x", "current_a": 1, "supply_net": "3V3", "supply_part": "X9"}))["error"]
    assert "未知工具" in json.loads(runner.run("nope", {}))["error"]


def test_model_list_request_and_parse():
    cfg = Config(provider="DeepSeek", api_key="k")
    url, headers = providers.build_models_request(cfg)
    assert url == "https://api.deepseek.com/v1/models"
    assert headers["Authorization"] == "Bearer k"
    assert providers.parse_models({"data": [{"id": "deepseek-chat"},
                                            {"id": "deepseek-reasoner"},
                                            {"id": "deepseek-chat"}]}) == [
        "deepseek-chat", "deepseek-reasoner"]

    anthropic = Config(provider="Anthropic", base_url="https://api.anthropic.com/v1",
                       api_key="k")
    url, headers = providers.build_models_request(anthropic)
    assert url == "https://api.anthropic.com/v1/models"
    assert headers["x-api-key"] == "k" and headers["anthropic-version"]
    assert providers.parse_models({"data": [{"id": "claude-sonnet-5-5",
                                             "display_name": "Claude Sonnet"}]}) == [
        "claude-sonnet-5-5"]

    local = Config(provider="Ollama", base_url="http://localhost:11434/v1", api_key="")
    url, headers = providers.build_models_request(local)
    assert url == "http://localhost:11434/v1/models"
    assert "Authorization" not in headers
    assert providers.parse_models({"models": [{"name": "qwen2.5:7b"}]}) == ["qwen2.5:7b"]

    custom = Config(provider="自定义", api_style="anthropic",
                    base_url="https://gateway.example/v1", api_key="k")
    url, headers = providers.build_models_request(custom)
    assert url == "https://gateway.example/v1/models"
    assert headers["x-api-key"] == "k" and "Authorization" not in headers


def test_full_endpoint_urls_are_normalized():
    custom = Config(provider="自定义", api_style="anthropic",
                    base_url="https://gateway.example/v1/messages/", api_key="k")
    assert build_request(custom, "", [], [])[0] == "https://gateway.example/v1/messages"
    assert providers.models_endpoint(custom) == "https://gateway.example/v1/models"

    openai = Config(provider="OpenAI",
                    base_url="https://api.openai.com/v1/chat/completions")
    assert build_request(openai, "", [], [])[0] == \
        "https://api.openai.com/v1/chat/completions"
    assert providers.models_endpoint(openai) == "https://api.openai.com/v1/models"


def test_model_list_retry_adds_v1_only_once():
    assert providers._alternate_models_url("https://api.deepseek.com/models") == \
        "https://api.deepseek.com/v1/models"
    assert providers._alternate_models_url("https://api.deepseek.com/v1/models") == ""
    assert providers._alternate_models_url(
        "https://open.bigmodel.cn/api/paas/v4/models") == ""
    message = providers._model_list_error(None, 404, b"", "Not Found",
                                          "https://example.com/models")
    assert "HTTP 404" in message and "https://example.com/models" in message


def test_model_list_reports_output_limits():
    infos = providers.parse_model_infos({"data": [
        {"id": "vendor/model", "top_provider": {"max_completion_tokens": 5000}},
        {"id": "other", "max_output_tokens": "4096"},
        {"id": "deepseek-chat"},
        {"id": "unknown-model"},
    ]}, Config(provider="DeepSeek"))
    limits = {info.id: info.max_output_tokens for info in infos}
    assert limits["vendor/model"] == 5000
    assert limits["other"] == 4096
    assert limits["deepseek-chat"] == 8192
    assert limits["unknown-model"] == 8192
    assert providers.parse_models({"data": [{"id": "a"}, {"id": "a"}]}) == ["a"]


def test_custom_config_name_and_anthropic_style(tmp_path):
    cfg = Config(provider="自定义", name="公司网关", api_style="anthropic",
                 base_url="https://gateway.example/v1", model="my-claude", api_key="k",
                 max_turns=45)
    url, headers, _body = build_request(cfg, "sys", [{"role": "user", "content": "hi"}], [])
    assert url == "https://gateway.example/v1/messages"
    assert headers["x-api-key"] == "k"

    settings = QSettings(str(tmp_path / "assistant.ini"), QSettings.Format.IniFormat)
    cfg.save(settings)
    loaded = Config.load(settings)
    assert loaded.provider == "自定义"
    assert loaded.name == "公司网关" and loaded.style == "anthropic"
    assert loaded.base_url == "https://gateway.example/v1"
    assert loaded.max_turns == 45

    settings.setValue("assistant/provider", "自定义 (OpenAI 兼容)")
    assert Config.load(settings).provider == "自定义"          # old name migrated


def test_settings_dialog_edits_name_and_style():
    from kipi.gui.assistant import panel as panel_mod

    dialog = panel_mod.SettingsDialog(Config(
        provider="自定义", name="公司网关", api_style="anthropic",
        base_url="https://gateway.example/v1", model="my-claude", api_key="k",
        max_turns=12))
    assert dialog.ed_name.text() == "公司网关"
    assert dialog.cmb_style.currentData() == "anthropic"
    assert dialog.sp_turns.value() == 12
    value = dialog.value()
    assert value.name == "公司网关" and value.style == "anthropic"
    assert value.max_turns == 12
    dialog.reject()


def test_settings_dialog_applies_the_model_output_limit():
    from kipi.gui.assistant import panel as panel_mod

    dialog = panel_mod.SettingsDialog(Config(provider="DeepSeek", api_key=""))
    dialog.sp_tokens.setValue(1234)
    dialog._models_fetched([ModelInfo("deepseek-chat", max_output_tokens=8192),
                            ModelInfo("unknown", max_output_tokens=0)], "")
    assert dialog.sp_tokens.value() == 8192
    assert "8192" in dialog.lbl_models.text()
    dialog.cmb_model.setCurrentText("unknown")
    assert dialog.sp_tokens.value() == 8192
    assert "未知" in dialog.lbl_models.text()
    dialog.reject()


def test_settings_dialog_keeps_the_endpoint_that_worked():
    from kipi.gui.assistant import panel as panel_mod

    class FakeClient:
        resolved_url = "http://localhost:8000/v1/models"

        def deleteLater(self):  # noqa: N802 - Qt spelling
            pass

    dialog = panel_mod.SettingsDialog(Config(provider="自定义",
                                             base_url="http://localhost:8000",
                                             model="", api_key=""))
    dialog._model_client = FakeClient()
    dialog._models_fetched([ModelInfo("m1")], "")
    assert dialog.ed_base.text() == "http://localhost:8000/v1"
    dialog.reject()


def test_the_chat_pauses_at_the_turn_limit_and_can_continue(monkeypatch):
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock.config = Config(provider="DeepSeek", api_key="k", max_turns=2)
    calls = []

    def send(config, system, history, tools):
        calls.append(list(history))
        if len(calls) < 3:
            dock.client.done.emit({"choices": [{"message": {
                "content": "",
                "tool_calls": [{"id": f"c{len(calls)}", "type": "function",
                                "function": {"name": "get_context",
                                             "arguments": "{}"}}]}}]}, "")
        else:
            dock.client.done.emit({"choices": [{"message": {"content": "完成"}}]}, "")

    monkeypatch.setattr(dock.client, "send", send)
    dock.input.setPlainText("看看当前板卡")
    dock._send()
    assert len(calls) == 2
    assert not dock._sending and not dock.btn_continue.isHidden()
    assert "轮工具调用" in dock.view.toPlainText()

    dock._continue()
    assert len(calls) == 3
    assert not dock._sending and dock.btn_continue.isHidden()
    assert "完成" in dock.view.toPlainText()


def test_attachments_go_into_the_user_message(tmp_path):
    from kipi.gui.assistant.attachments import Attachment
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock.config = Config(provider="DeepSeek", api_key="k")
    dock._pending_attachments = [
        Attachment("spec.pdf", "PDF TEXT", "PDF，1 页，8 字"),
    ]
    dock.input.setPlainText("按附件检查 3V3")
    sent = []
    dock.client.send = lambda config, system, history, tools: sent.append(list(history))
    dock._send()
    assert "spec.pdf" in dock.history[0]["content"]
    assert "PDF TEXT" in dock.history[0]["content"]
    assert "按附件检查 3V3" in dock.history[0]["content"]
    assert "spec.pdf" in dock.view.toPlainText()
    assert not dock._pending_attachments
    assert sent


def test_conversations_follow_the_project(tmp_path):
    from kipi.gui.assistant.panel import AssistantDock
    from kipi.gui.assistant.store import ConversationStore

    main = _Main()
    first = main.snapshot
    second = dataclasses.replace(first, board_name="other")
    dock = AssistantDock(main, store=ConversationStore(tmp_path))
    dock._project_changed(first)
    dock._append("你", "第一块板的问题", "#1f5fa8")
    dock.history.append({"role": "user", "content": "第一块板的问题"})
    dock.save_conversation()

    dock._project_changed(second)
    assert dock._items == [] and dock.history == []
    dock._append("助手", "第二块板的回答", markdown=True)
    dock.history.append({"role": "assistant", "content": "第二块板的回答"})
    dock.save_conversation()

    dock._project_changed(first)
    assert "第一块板的问题" in dock.view.toPlainText()
    assert "第二块板的回答" not in dock.view.toPlainText()
    assert dock.history == [{"role": "user", "content": "第一块板的问题"}]

    reopened = AssistantDock(main, store=ConversationStore(tmp_path))
    assert "第一块板的问题" in reopened.view.toPlainText()


def test_switching_projects_aborts_an_in_flight_reply(tmp_path):
    from kipi.gui.assistant.panel import AssistantDock
    from kipi.gui.assistant.store import ConversationStore

    dock = AssistantDock(_Main(), store=ConversationStore(tmp_path))
    aborted = []
    dock.client.abort = lambda: aborted.append(True)
    dock._sending = True
    dock._project_changed(dataclasses.replace(dock.main.snapshot, board_name="other"))
    assert aborted and not dock._sending


def test_dock_shows_the_custom_config_name():
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock.config = Config(provider="自定义", name="公司网关", model="my-model", api_key="k")
    dock._update_provider()
    assert "公司网关" in dock.lbl_provider.text()


def test_attachment_tools_search_pages_and_read():
    from kipi.gui.assistant.attachments import Attachment

    main = _Main()
    runner = ToolRunner(main)
    pages = [(n, ("3V3 thermal " if n == 7 else "other ") * 20) for n in range(1, 10)]
    full_text = "\n".join(f"[第 {n} 页]\n{text}" for n, text in pages)
    runner.attachments = {
        "spec.pdf": Attachment("spec.pdf", "digest", "PDF，9 页", full_text, pages),
    }
    listed = json.loads(runner.run("list_attachments", {}))
    assert listed["attachments"][0]["pages"] == 9
    assert not listed["attachments"][0]["complete"]

    hits = json.loads(runner.run("search_attachment", {"query": "thermal"}))
    assert hits["count"] and hits["hits"][0]["page"] == 7

    read = json.loads(runner.run("read_attachment", {
        "name": "spec.pdf", "start_page": 7, "end_page": 7}))
    assert "3V3 thermal" in read["text"] and read["start_page"] == 7


def test_thermal_settings_can_be_set_from_the_assistant():
    main = _Main()
    runner = ToolRunner(main)
    assert "set_thermal" in {tool["function"]["name"] for tool in TOOLS}

    out = json.loads(runner.run("set_thermal", {
        "enabled": True, "ambient_c": 40, "iterations": 5, "airflow_m_s": 1.5,
        "load_power": True, "max_temp_c": 85, "max_rise_c": 45}))
    thermal = out["thermal"]
    assert thermal["enabled"] and thermal["ambient_c"] == 40
    assert thermal["iterations"] == 5 and thermal["airflow_m_s"] == 1.5
    assert thermal["max_temp_c"] == 85 and thermal["max_rise_c"] == 45
    setup = main.solve_panel.setup
    assert setup.thermal.enabled and setup.thermal.load_power

    assert json.loads(runner.run("get_context", {}))["setup"]["thermal"] is True
    assert json.loads(runner.run("get_setup", {}))["thermal"]["ambient_c"] == 40

    runner.run("set_thermal", {"clear_limits": True})
    assert setup.thermal.max_temp_c is None and setup.thermal.max_rise_c is None


def test_fast_setup_is_coarser_without_touching_the_setup():
    from kipi.gui.assistant.tools import _fast_setup

    setup = PISetup()
    fast = _fast_setup(setup)
    assert fast.settings.max_edge_mm > setup.settings.max_edge_mm
    assert fast.settings.tol >= setup.settings.tol
    assert fast.ac.points_per_decade < setup.ac.points_per_decade
    assert fast.noise.max_harmonics < setup.noise.max_harmonics
    assert not fast.noise.board_model and setup.noise.board_model


def test_request_history_drops_old_turns_and_truncates_results(monkeypatch):
    from kipi.gui.assistant import panel as panel_mod
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    monkeypatch.setattr(panel_mod, "HISTORY_CHAR_BUDGET", 700)
    monkeypatch.setattr(panel_mod, "TOOL_RESULT_CHAR_BUDGET", 50)
    dock.history = [
        {"role": "user", "content": "old " * 100},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "",
         "tool_calls": [{"id": "c1", "name": "get_context", "arguments": {}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "get_context",
         "content": "x" * 500},
    ]
    kept = dock._request_history()
    assert [m["role"] for m in kept] == ["user", "assistant", "tool"]
    assert kept[0]["content"] == "new question"
    assert kept[2]["content"].startswith("x" * 50)
    assert "已截断" in kept[2]["content"]


def test_the_fast_checkbox_drives_the_tool_runner():
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock.chk_fast.setChecked(True)
    assert dock.runner.fast
    dock.chk_fast.setChecked(False)
    assert not dock.runner.fast


def test_settings_dialog_fetches_and_offers_models(monkeypatch):
    from kipi.gui.assistant import panel as panel_mod

    seen = {}

    class _Done:
        def connect(self, slot):
            self.slot = slot

    class FakeClient:
        def __init__(self, parent=None):
            self.parent = parent
            self.done = _Done()

        def fetch(self, config):
            seen["config"] = config

        def abort(self):
            seen["aborted"] = True

        def deleteLater(self):  # noqa: N802 - Qt spelling
            seen["deleted"] = True

    monkeypatch.setattr(panel_mod, "ModelListClient", FakeClient)
    dialog = panel_mod.SettingsDialog(Config(provider="DeepSeek", api_key=""))
    dialog.ed_base.setText("https://api.deepseek.com/v1")
    dialog.ed_key.setText("secret")
    dialog._fetch_models()
    assert seen["config"].api_key == "secret"
    assert seen["config"].base_url == "https://api.deepseek.com/v1"
    assert "正在拉取" in dialog.lbl_models.text()
    assert not dialog.btn_models.isEnabled()

    dialog._models_fetched(["deepseek-chat", "deepseek-reasoner"], "")
    assert [dialog.cmb_model.itemText(i) for i in range(dialog.cmb_model.count())] == [
        "deepseek-chat", "deepseek-reasoner"]
    assert dialog.value().model == "deepseek-chat"
    assert dialog.btn_models.isEnabled()
    assert seen.get("deleted")

    dialog.cmb_model.setEditText("my-finetune")
    dialog._models_fetched(["deepseek-chat"], "")
    assert dialog.value().model == "my-finetune"

    dialog._models_fetched([], "HTTP 401: bad key")
    assert "401" in dialog.lbl_models.text()
    dialog._fetch_models()
    dialog.reject()
    assert seen.get("aborted")


def test_settings_dialog_fetches_models_automatically_once(monkeypatch):
    from kipi.gui.assistant import panel as panel_mod

    calls = []

    class _Done:
        def connect(self, slot):
            self.slot = slot

    class FakeClient:
        def __init__(self, parent=None):
            self.done = _Done()

        def fetch(self, config):
            calls.append(config.base_url)

        def abort(self):
            pass

        def deleteLater(self):  # noqa: N802 - Qt spelling
            pass

    monkeypatch.setattr(panel_mod, "ModelListClient", FakeClient)
    dialog = panel_mod.SettingsDialog(Config(provider="DeepSeek", api_key=""))
    dialog.ed_base.setText("https://api.deepseek.com/v1")
    dialog.ed_key.setText("secret")
    dialog._maybe_fetch_models()
    assert calls == ["https://api.deepseek.com/v1"]
    dialog._maybe_fetch_models()
    assert calls == ["https://api.deepseek.com/v1"]

    dialog._models_fetched(["deepseek-chat"], "")
    dialog._maybe_fetch_models()
    assert calls == ["https://api.deepseek.com/v1"]
    dialog.reject()


def test_tool_calls_fold_into_one_block(monkeypatch):
    from kipi.gui.assistant.panel import AssistantDock

    dock = AssistantDock(_Main())
    dock.config = Config(provider="DeepSeek", api_key="k")
    calls = []

    def send(config, system, history, tools):
        calls.append(list(history))
        if len(calls) == 1:
            dock.client.done.emit({"choices": [{"message": {
                "content": "",
                "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "get_context", "arguments": "{}"}},
                    {"id": "c2", "type": "function",
                     "function": {"name": "list_nets", "arguments": "{}"}},
                ]}}]}, "")
        else:
            dock.client.done.emit({"choices": [{"message": {"content": "完成"}}]}, "")

    monkeypatch.setattr(dock.client, "send", send)
    dock.input.setPlainText("看看板卡")
    dock._send()

    indexes = [i for i, item in enumerate(dock._items) if item["kind"] == "tools"]
    assert len(indexes) == 1
    index = indexes[0]
    assert len(dock._items[index]["calls"]) == 2
    assert not dock._items[index]["expanded"]
    text = dock.view.toPlainText()
    assert "工具调用 2 次" in text and "get_context" in text and "list_nets" in text
    assert '"board"' not in text            # the raw result stays folded

    dock._anchor_clicked(QUrl(f"kipi-tools:{index}"))
    text = dock.view.toPlainText()
    assert dock._items[index]["expanded"]
    assert '"board"' in text and "执行中" not in text

    dock._anchor_clicked(QUrl(f"kipi-tools:{index}"))
    assert not dock._items[index]["expanded"]
    assert '"board"' not in dock.view.toPlainText()


def test_old_tool_messages_are_folded_when_loaded(tmp_path):
    from kipi.gui.assistant.panel import AssistantDock
    from kipi.gui.assistant.store import ConversationStore

    store = ConversationStore(tmp_path)
    store.use("old")
    store.save({
        "version": 1,
        "history": [],
        "items": [
            {"kind": "message", "speaker": "你", "text": "看看板卡",
             "color": "#1f5fa8", "markdown": False},
            {"kind": "message", "speaker": "", "text": "🔧 get_context {}",
             "color": "#777", "markdown": False},
            {"kind": "message", "speaker": "", "text": '{"board": {"name": "test"}}',
             "color": "#555", "markdown": False},
            {"kind": "message", "speaker": "", "text": "🔧 list_nets {}",
             "color": "#777", "markdown": False},
            {"kind": "message", "speaker": "", "text": '{"nets": []}',
             "color": "#555", "markdown": False},
            {"kind": "message", "speaker": "", "text": "📎 spec.pdf（PDF，1 页）",
             "color": "#777", "markdown": False},
        ],
    })
    dock = AssistantDock(_Main())
    dock.store = store
    dock._load_conversation()

    assert [item["kind"] for item in dock._items].count("tools") == 1
    tools = next(item for item in dock._items if item["kind"] == "tools")
    assert [call["name"] for call in tools["calls"]] == ["get_context", "list_nets"]
    text = dock.view.toPlainText()
    assert "工具调用 2 次" in text
    assert '"board"' not in text
    assert "📎" not in text and "附件：spec.pdf" in text


def test_markdown_headings_use_the_transcript_style():
    from kipi.gui.assistant.panel import _markdown_html

    body = _markdown_html("## 结论\n\n正文 **粗体**")
    assert "x-large" not in body
    assert "font-weight:700" in body
