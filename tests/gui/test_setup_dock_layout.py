"""The setup dock gives up width on a small window instead of squeezing the 3D view."""

import os

import pytest

pytest.importorskip("qtpy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import (  # noqa: E402
    QApplication, QFormLayout, QSizePolicy, QTableWidget,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_setup_dock_can_shrink(app, no_3d):
    from kipi.gui.main_window import MainWindow
    w = MainWindow()
    try:
        assert w.solve_dock.minimumWidth() <= 320
        assert w.setup_scroll.widgetResizable()
        assert w.setup_stack.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
        for panel in w._panels().values():
            assert panel.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
            for form in panel.findChildren(QFormLayout):
                assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapLongRows
            for table in panel.findChildren(QTableWidget):
                assert table.horizontalScrollBarPolicy() is not None
    finally:
        w.close()


def test_switching_mode_returns_the_panel_to_its_top(app, no_3d):
    from kipi.gui.main_window import MainWindow
    w = MainWindow()
    try:
        w.setup_scroll.verticalScrollBar().setValue(50)
        w.set_mode("ac")
        assert w.setup_scroll.verticalScrollBar().value() == 0
        w.set_mode("dc")
    finally:
        w.close()
