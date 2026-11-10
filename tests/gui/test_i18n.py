"""The Chinese catalog and the text lookup, without Qt."""

import pytest

from kipi.gui import i18n


@pytest.fixture(autouse=True)
def chinese(monkeypatch):
    monkeypatch.setenv("KIPI_LANG", "zh_CN")
    i18n._CATALOG = None
    i18n._ENABLED = None
    yield
    i18n._CATALOG = None
    i18n._ENABLED = None


def test_plain_labels():
    assert i18n.tr("Cancel") == "取消"
    assert i18n.tr("Copper layers") == "铜层"
    assert i18n.tr("Mode: ") == "模式： "


def test_tooltip_shortcuts_are_kept():
    assert i18n.tr("Open… (Ctrl+O)") == "打开… (Ctrl+O)"
    assert i18n.tr("Re-read the board (F5)") == "重新读取板卡 (F5)"


def test_mnemonics_and_dynamic_titles():
    assert i18n.tr("&File") == "文件"
    assert i18n.tr("KiPI 1.0.0 — Power Integrity (standalone)") == "KiPI 1.0.0 — 电源完整性（独立版）"
    assert i18n.tr("Phase 3") == "相位 3"


def test_unknown_and_data_are_left_alone():
    assert i18n.tr("+3V3") == "+3V3"
    assert i18n.tr("U1") == "U1"
    assert i18n.tr("") == ""


def test_english_can_be_forced(monkeypatch):
    monkeypatch.setenv("KIPI_LANG", "en")
    i18n._ENABLED = None
    assert i18n.tr("Cancel") == "Cancel"
