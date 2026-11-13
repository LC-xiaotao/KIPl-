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


def test_waveform_plot_strings():
    """The labels the waveform plots build at run time (matplotlib has no Qt setter)."""
    assert i18n.tr("Amplitude (V peak)") == "幅值（V 峰值）"
    assert i18n.tr("Time (µs)") == "时间 (µs)"
    assert i18n.tr("Load step (A)") == "负载阶跃 (A)"
    assert i18n.tr("Rail deviation (mV)") == "电源轨偏移 (mV)"
    assert i18n.tr("Show C12") == "显示 C12"
    assert i18n.tr("noise margin ±300 mV") == "噪声容限 ±300 mV"
    assert (i18n.tr("the ±300 mV noise margin is off the scale")
            == "±300 mV 噪声容限超出显示范围")
    assert (i18n.tr("U3: 132 mV peak against its ±300 mV margin, from U1")
            == "U3：峰值 132 mV，相对 ±300 mV 裕量，来自 U1")
    assert (i18n.tr("VIN (buck, 12 V → 0.9 V, 3 A, 500 kHz, D = 0.420)")
            == "VIN（降压，12 V → 0.9 V，3 A，500 kHz，D = 0.420）")
    assert (i18n.tr("U3 held high (driver 33 Ω): 45 mV toward VIH, 300 mV away")
            == "U3 保持高电平（驱动 33 Ω）：45 mV 朝向 VIH，距其 300 mV")
    assert (i18n.tr("ESL spike L·di/dt = 1.2 nH × 2 A/µs = 45 mV over its 10 ns edge; "
                    "−60 mV there with the droop")
            == "ESL 尖峰 L·di/dt = 1.2 nH × 2 A/µs = 45 mV（10 ns 边沿内）；"
               "连同下垂为 −60 mV")
    assert (i18n.tr("its 150 ns edge is slow enough that the PDN is still capacitive "
                    "at its 2.12 MHz: no ESL spike stands out from the droop "
                    "(−45 mV over the edge)")
            == "其 150 ns 边沿足够慢，PDN 在 2.12 MHz 时仍呈容性："
               "没有超出下垂的 ESL 尖峰（边沿内 −45 mV）")
    # Numbers and net names are left as they are.
    assert i18n.tr("U3") == "U3"


def test_unknown_and_data_are_left_alone():
    assert i18n.tr("+3V3") == "+3V3"
    assert i18n.tr("U1") == "U1"
    assert i18n.tr("") == ""


def test_english_can_be_forced(monkeypatch):
    monkeypatch.setenv("KIPI_LANG", "en")
    i18n._ENABLED = None
    assert i18n.tr("Cancel") == "Cancel"
