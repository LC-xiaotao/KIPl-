"""Toolbar entry, board import, worker delivery and trace-to-board interaction."""

import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("qtpy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qtpy.QtWidgets import QApplication

from kipi.gui.main_window import MainWindow
from kipi.si.dialog import SignalDialog
from kipi.sources.registry import open_board


def test_si_toolbar_and_step_board(monkeypatch, no_3d):
    app = QApplication.instance() or QApplication([])
    demo = Path(__file__).parents[2] / "examples/validation/single_ended_si/stepped_line.kipi.json"
    snap = open_board(demo).load()
    w = MainWindow()
    assert not w.act_si.isEnabled()
    monkeypatch.setattr(w, "sync_nets", lambda: None)
    w._set_snapshot(snap)
    opened = []

    def exercise(dialog):
        opened.append(dialog)
        assert dialog.net.currentText() == "CLK" and dialog.ref.currentText() == "GND"
        assert dialog.tx.currentData() == "TX.1" and dialog.rx.currentData() == "RX.1"
        dialog.run.click()
        deadline = time.monotonic() + 30
        while dialog.task is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        assert dialog.result is not None, dialog.status.text()
        assert dialog.result.eye and len(dialog.result.receiver_v) == 3
        dialog.show_tx.setChecked(True)
        assert len(dialog.wave.lines) == 7   # threshold, three RX and three TX
        dialog._click(SimpleNamespace(inaxes=dialog.tdr, xdata=.3, button=1))
        assert dialog.marker and "F.Cu" in dialog.location.text()
        dialog._click(SimpleNamespace(inaxes=dialog.tdr, xdata=1000, button=1))
        assert dialog.marker is None
        dialog.rx.setCurrentIndex(dialog.tx.currentIndex())
        assert dialog.result is None and not dialog.run.isEnabled()
        return 0

    monkeypatch.setattr(SignalDialog, "exec", exercise)
    assert w.act_si.isEnabled()
    # Invoke the same slot without letting Qt swallow exceptions raised by assertions.
    w.show_si()
    assert len(opened) == 1
    w.close()
