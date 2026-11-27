"""Single-ended SI setup, receiver waveforms and linked TDR/board views."""

from __future__ import annotations

from collections import Counter

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from qtpy.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from kipi.core.model.nets import is_ground_name
from kipi.gui.worker import QtProgress, Task
from kipi.noise.extract.capacitive import split_tracks
from kipi.si.channel import extract_channel
from kipi.si.solver import Settings, simulate


class SignalDialog(QDialog):
    def __init__(self, snap, default_er, parent=None):
        super().__init__(parent)
        self.snap, self.default_er = snap, default_er
        self.task = self.result = self.cached = self.marker = None
        self.close_pending = False
        self.setWindowTitle(f"单端信号完整性 · {snap.board_name}")
        self.resize(1230, 780)
        row = QHBoxLayout(self)
        pane = QWidget()
        left = QVBoxLayout(pane)
        form = QFormLayout()
        left.addLayout(form)
        self.inputs = pane
        pad_counts = Counter(p.net for p in snap.pads if p.net and p.shapes)
        nets = {t.net for t in snap.tracks if pad_counts[t.net] >= 2}
        self.net = self._combo(form, "信号网络", "选择有走线和收发焊盘的网络。")
        self.net.addItems(sorted(nets, key=lambda n: (is_ground_name(n), n)))
        self.ref = self._combo(form, "参考网络", "截面求解使用该网络的实际铜形状作为回流参考。")
        refs = sorted(snap.net_names(), key=lambda n: (not is_ground_name(n), n))
        self.ref.addItems(refs)
        self.tx = self._combo(form, "发送焊盘", "可在右侧板图上点选。")
        self.rx = self._combo(form, "接收焊盘", "可在右侧板图上点选。")
        self.pick = self._combo(form, "板图点选目标", "点击焊盘设置端口。")
        self.pick.addItems(["发送端", "接收端"])
        stack_source = "读取/编辑的叠层" if snap.stackup.from_board or snap.stackup.edited else "使用默认叠层"
        stack = QLabel(f"{len(snap.stackup.copper)} 个铜层，板厚 {snap.stackup.board_thickness_mm:g} mm"
                       f"\n{stack_source}，缺省 εr = {default_er:g}")
        stack.setWordWrap(True)
        form.addRow("板叠层", stack)
        self.volts = self._spin(form, "驱动高电平", 1.8, .001, 100., " V", "低电平为 0 V。")
        self.rise = self._spin(form, "10–90% 边沿", 200, 1., 100000., " ps", "线性上升沿的 10–90% 时间。")
        self.driver = self._spin(form, "驱动内阻", 18, 0, 10000, " Ω", "驱动器本身的串联电阻。")
        self.series = QLineEdit("0, 22, 33")
        self.series.setToolTip("用逗号分隔多个附加串阻，单位 Ω。每个值生成一条曲线。")
        form.addRow("对比串阻（Ω）", self.series)
        self.cap = self._spin(form, "输入电容", 3, 0, 1000, " pF", "接收焊盘对参考网络的并联电容。")
        self.load = self._spin(form, "接收端电阻", 0, 0, 1e7, " Ω",
                               "0 表示开路；输入电容仍然有效。")
        self.load.setSpecialValueText("高阻")
        self.threshold = self._spin(form, "穿越计数门限", .9, .001, 99., " V",
                                    "统计接收信号穿越该电压的次数。")
        self.zref = self._spin(form, "TDR 参考阻抗", 50, 1., 1000., " Ω",
                               "TDR 两端使用该电阻，替代信号收发器。")
        self.eye_check = QCheckBox("生成 PRBS7 眼图")
        self.eye_check.setChecked(True)
        self.eye_check.setToolTip("对最后一个串阻值按周期叠加阶跃，只含通道引起的码间干扰。")
        form.addRow(self.eye_check)
        self.rate = self._spin(form, "眼图数据率", 1, .001, 100., " Gb/s", "每个单位间隔等于数据率的倒数。")
        self.eye_check.toggled.connect(self.rate.setEnabled)
        self.run = QPushButton("运行单端仿真")
        self.run.setToolTip("提取截面并计算接收波形、TDR 和所选眼图。")
        self.run.clicked.connect(self._run)
        left.addWidget(self.run)
        self.show_tx = QCheckBox("叠加发送端波形")
        self.show_tx.setToolTip("虚线显示附加串阻后、走线入口处的电压。")
        self.show_tx.toggled.connect(self._draw_wave)
        left.addWidget(self.show_tx)
        notes = QLabel("无损准 TEM 走线；过孔与焊盘按理想连接处理，其他支路末端开路。"
                       "点击 TDR 曲线可查看所选路径上按首达时间估算的位置。")
        notes.setWordWrap(True)
        left.addWidget(notes)
        left.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(pane)
        scroll.setMinimumWidth(295)
        row.addWidget(scroll)
        right = QVBoxLayout()
        row.addLayout(right, 1)
        self.figure = Figure(figsize=(8, 6), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        right.addWidget(self.toolbar)
        right.addWidget(self.canvas, 1)
        (self.board, self.tdr), (self.wave, self.eye) = self.figure.subplots(2, 2)
        self.status = QLabel()
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        self.location = QLabel()
        right.addWidget(self.location)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.cancel = buttons.addButton("取消计算", QDialogButtonBox.ActionRole)
        self.cancel.setToolTip("中止当前计算，保留收发端和输入参数。")
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self._cancel)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)
        self.canvas.mpl_connect("button_press_event", self._click)
        self.net.currentIndexChanged.connect(self._net_changed)
        for control in (self.ref, self.tx, self.rx):
            control.currentIndexChanged.connect(self._invalidate)
        for control in (self.volts, self.rise, self.driver, self.cap, self.load, self.threshold,
                        self.zref, self.rate):
            control.valueChanged.connect(self._invalidate)
        self.series.textChanged.connect(self._invalidate)
        self.eye_check.toggled.connect(self._invalidate)
        self._net_changed()

    @staticmethod
    def _combo(form, name, tip):
        control = QComboBox()
        control.setToolTip(tip)
        form.addRow(name, control)
        return control

    @staticmethod
    def _spin(form, name, value, minimum, maximum, suffix, tip):
        control = QDoubleSpinBox()
        control.setDecimals(3)
        control.setRange(minimum, maximum)
        control.setValue(value)
        control.setSuffix(suffix)
        control.setToolTip(tip)
        form.addRow(name, control)
        return control

    def _net_changed(self):
        net = self.net.currentText()
        self.pads = sorted((p for p in self.snap.items_on_net(net)[2] if p.shapes),
                           key=lambda p: (p.label, p.id))
        self.lines = [[s.a, s.b] for s in split_tracks(self.snap, net, 2.)]
        for combo in (self.tx, self.rx):
            combo.blockSignals(True)
            combo.clear()
            for pad in self.pads:
                combo.addItem(f"{pad.label}  ({pad.position[0]:g}, {pad.position[1]:g})", pad.id)
            combo.setCurrentIndex(min(1, len(self.pads) - 1) if combo is self.rx else 0)
            combo.blockSignals(False)
        self._invalidate()

    def _invalidate(self):
        self.result = self.marker = None
        self.location.clear()
        problem = ""
        if len(self.pads) < 2:
            problem = "当前板上没有同时具备走线和两个铜焊盘的网络。"
        elif self.tx.currentData() == self.rx.currentData():
            problem = "请选择两个不同的收发焊盘。"
        elif not self.ref.currentText() or self.net.currentText() == self.ref.currentText():
            problem = "请选择与信号网络不同的参考网络。"
        self.status.setText(problem or "选择收发焊盘和参考网络，然后运行。")
        self.run.setEnabled(not problem)
        for ax, title, ylabel in [(self.tdr, "TDR", "Impedance (ohm)"),
                                  (self.wave, "Receiver step", "Voltage (V)"),
                                  (self.eye, "Receiver eye", "Voltage (V)")]:
            ax.clear()
            ax.set(title=title, ylabel=ylabel, xlabel="Time (UI)" if ax is self.eye else "Time (ns)")
            ax.grid(True, alpha=.2)
        self.board.clear()
        self.board.set(title=self.net.currentText(), xlabel="X (mm)", ylabel="Y (mm)")
        self.board.set_aspect("equal", adjustable="datalim")
        for poly in self.snap.outline:
            if poly.outline:
                self.board.fill(*zip(*poly.outline), facecolor="#edf4ef", edgecolor="#acbdb2", lw=.8)
        self.board.add_collection(LineCollection(self.lines, colors="#38699b", linewidths=1.2))
        if self.pads:
            self.board.scatter(*zip(*(p.position for p in self.pads)), c=".45", s=15)
        for combo, color, name in [(self.tx, "#00766e", "TX"), (self.rx, "#a74e20", "RX")]:
            if combo.currentIndex() >= 0:
                x, y = self.pads[combo.currentIndex()].position
                self.board.plot(x, y, "o", color=color)
                self.board.annotate(name, (x, y), xytext=(3, 4), textcoords="offset points")
        self.board.autoscale()
        self.board.invert_yaxis()
        self.canvas.draw_idle()

    def _click(self, event):
        if event.button != 1 or self.toolbar.mode or self.task is not None:
            return
        if event.inaxes is self.board and self.pads:
            xy = self.board.transData.transform([p.position for p in self.pads])
            d = np.hypot(xy[:, 0] - event.x, xy[:, 1] - event.y)
            if d.min() <= 12:
                which = self.pick.currentIndex()
                (self.tx, self.rx)[which].setCurrentIndex(int(np.argmin(d)))
                self.pick.setCurrentIndex(1 - which)
        elif event.inaxes is self.tdr and self.result:
            hit = self.result.channel.locate(event.xdata)
            if self.marker:
                self.marker.remove()
                self.marker = None
            if hit:
                line, (x, y), length = hit
                self.marker, = self.board.plot(x, y, "*", ms=15, color="#c2185b")
                layer = self.snap.stackup.layer(line.layer)
                self.location.setText(f"路径候选点 · {length:.2f} mm · {layer.name}"
                                      f" · X {x:.3f}, Y {y:.3f} mm")
            else:
                self.location.setText("该时刻超出所选收发路径的首次往返时间。")
            self.canvas.draw_idle()

    def _run(self):
        try:
            parts = self.series.text().replace("，", ",").split(",")
            values = tuple(dict.fromkeys(float(x.strip()) for x in parts))
            if len(values) > 12:
                raise ValueError("每次最多对比 12 个串阻。")
            cfg = Settings(self.volts.value(), self.rise.value(), self.driver.value(), values,
                           self.load.value() or np.inf, self.cap.value(), self.zref.value(),
                           self.threshold.value(), self.rate.value() if self.eye_check.isChecked() else 0.)
            cfg.validate()
        except ValueError as e:
            self.status.setText(f"输入有误：{e}")
            return
        key = (self.net.currentText(), self.ref.currentText(), self.tx.currentData(), self.rx.currentData())
        cached = self.cached

        def work(progress):
            channel = (cached[1] if cached and cached[0] == key else
                       extract_channel(self.snap, *key, self.default_er, progress))
            return simulate(channel, cfg, progress)

        self._invalidate()
        self.inputs.setEnabled(False)
        self.cancel.setEnabled(True)
        self.status.setText("正在提取通道…")
        self.progress = QtProgress()
        self.progress.sig_stage.connect(self.status.setText)
        self.task = Task(work, self.progress, self)
        self.task.done.connect(self._show_result)
        self.task.failed.connect(self._failed)
        self.task.canceled.connect(lambda: self.status.setText("已取消。"))
        self.task.finished.connect(self._finished)
        self.task.start()

    def _failed(self, message):
        self.status.setText(message.strip().splitlines()[-1])

    def _finished(self):
        self.inputs.setEnabled(True)
        self.cancel.setEnabled(False)
        self.task.deleteLater()
        self.task = None
        if self.close_pending:
            super().reject()

    def _cancel(self):
        if self.task:
            self.progress.cancel()

    def reject(self):
        if self.task:
            self.close_pending = True
            self._cancel()
            self.status.setText("正在取消计算…")
            return
        super().reject()

    def _show_result(self, r):
        self.result = r
        key = (self.net.currentText(), self.ref.currentText(), self.tx.currentData(), self.rx.currentData())
        self.cached = (key, r.channel)
        self.board.add_collection(LineCollection([(s.a, s.b) for s in r.channel.route()],
                                                 colors="#00857b", linewidths=2.3))
        self.tdr.plot(r.time_ns, r.tdr_ohm, color="#245a91")
        flight = sum(s.flight_ns for s in r.channel.route())
        self.tdr.set_xlim(0, min(r.time_ns[-1], 3 * flight + 2 * r.settings.rise_ps / 1000))
        self._draw_wave()
        info = []
        for ohm, v in zip(r.settings.series_ohm, r.receiver_v):
            over = v >= r.settings.threshold_v
            count = np.count_nonzero(over[1:] != over[:-1])
            info.append(f"+{ohm:g} Ω：峰值 {v.max():.3f} V，门限穿越 {count} 次")
        if r.eye:
            phase, traces, opening = r.eye
            self.eye.plot(phase, traces.T, color="#00857b", alpha=.15, lw=.7)
            self.eye.set_title(f"PRBS7  ·  +{r.settings.series_ohm[-1]:g} Ω")
            info.append(f"0.5 UI 眼高 {opening:.3f} V")
        self.status.setText(f"单程 {flight:.3f} ns。 " + "；".join(info) + "  " + r.eye_note)
        self.canvas.draw_idle()

    def _draw_wave(self):
        r = self.result
        if r is None:
            return
        self.wave.clear()
        self.wave.set(title="TX / RX step" if self.show_tx.isChecked() else "Receiver step",
                      xlabel="Time (ns)", ylabel="Voltage (V)")
        self.wave.grid(True, alpha=.2)
        self.wave.axhline(r.settings.threshold_v, ls=":", lw=1, color=".45")
        for ohm, rx, tx in zip(r.settings.series_ohm, r.receiver_v, r.source_v):
            line, = self.wave.plot(r.time_ns, rx, label=f"RX +{ohm:g} Ω")
            if self.show_tx.isChecked():
                self.wave.plot(r.time_ns, tx, color=line.get_color(), ls="--", label=f"TX +{ohm:g} Ω")
        self.wave.legend(fontsize=8)
        self.canvas.draw_idle()
