"""Switching the interface and report language at runtime."""

import os

import pytest

pytest.importorskip("qtpy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import QApplication, QComboBox, QLabel, QTabWidget, QWidget  # noqa: E402

from kipi.core import lang  # noqa: E402
from kipi.gui import i18n  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def chinese(monkeypatch, app):
    monkeypatch.delenv("KIPI_LANG", raising=False)
    i18n.install()
    i18n.set_preference("zh_CN")
    yield
    monkeypatch.delenv("KIPI_LANG", raising=False)
    i18n._ENABLED = None
    lang.reset()


def test_widgets_switch_between_chinese_and_english():
    label = QLabel("Cancel")
    combo = QComboBox()
    combo.addItems(["None", "All power"])
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "3D view")
    for widget in (label, combo, tabs):
        i18n.translate_tree(widget)
    assert label.text() == "取消"
    assert combo.itemText(0) == "无" and combo.itemText(1) == "全部电源"
    assert tabs.tabText(0) == "3D 视图"

    assert i18n.set_preference("en")
    for widget in (label, combo, tabs):
        i18n.translate_tree(widget)
    assert label.text() == "Cancel"
    assert combo.itemText(0) == "None" and combo.itemText(1) == "All power"
    assert tabs.tabText(0) == "3D view"
    assert not lang.chinese()

    assert i18n.set_preference("zh_CN")
    for widget in (label, combo, tabs):
        i18n.translate_tree(widget)
    assert label.text() == "取消"
    assert lang.chinese()


def test_follow_system(monkeypatch):
    i18n.set_preference("system")
    monkeypatch.setattr(i18n, "system_language", lambda: "en")
    i18n._ENABLED = None
    assert not i18n.language()
    monkeypatch.setattr(i18n, "system_language", lambda: "zh_CN")
    i18n._ENABLED = None
    assert i18n.language()


def test_the_toolbar_language_menu_switches_the_window(no_3d):
    from kipi.gui.main_window import MainWindow

    window = MainWindow()
    try:
        assert {a.data() for a in window._language_actions.values()} == {
            "system", "zh_CN", "en"}
        window.set_language("en")
        assert window.act_about.text() == "About"
        assert window.act_language.text() == "Language"
        assert window._language_actions["en"].isChecked()

        window.set_language("zh_CN")
        assert window.act_about.text() == "关于"
        assert window.act_language.text() == "语言"
        assert window._language_actions["zh_CN"].isChecked()
    finally:
        window.close()
