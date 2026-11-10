"""Chinese reports: the catalog, the page translation and the figure text."""

import pytest

from kipi.core import lang, report_i18n as i18n


@pytest.fixture
def chinese(monkeypatch):
    monkeypatch.setenv("KIPI_LANG", "zh_CN")
    lang.reset()
    i18n.reset()
    yield
    lang.reset()
    i18n.reset()


def test_phrases_and_templates(chinese):
    assert i18n.tr("Loads") == "负载"
    assert i18n.tr("PASS") == "通过"
    assert i18n.tr("Via current limit 1000 mA.") == "过孔电流上限 1000 mA。"
    assert i18n.tr("KiPI report — board") == "KiPI 报告 — board"
    # Values keep their place where Chinese reorders them.
    assert i18n.tr("crosses from GND (In1) to no plane at (1.0, 2.0) mm on top: the return "
                   "detours 0.5 mm, 0.12 nH in series") == (
        "在 top 的 (1.0, 2.0) mm 处从 GND (In1) 跨到 无平面，回流绕行 0.5 mm，串联 0.12 nH")
    # Lists made of small parts get their phrases translated, names left alone.
    assert i18n.tr("Stackup, top to bottom: top solder mask 10 µm, F.Cu 35 µm; 1.6 mm in all.") \
        == "叠层（从上到下）：顶部阻焊 10 µm, F.Cu 35 µm; 1.6 mm 合计。"


def test_data_is_left_alone(chinese):
    for text in ("+3V3", "U1[35] → FPC1[22]", "top_layer", "FSMC-NWE", "mV", "x (mm)"):
        assert i18n.tr(text) == text


def test_pages_keep_their_code_and_data(chinese):
    page = ("<h2 id='loads'>Loads</h2><th title='Click to sort'>Load</th>"
            "<style>.x{content:'Loads'}</style>"
            "<script>var a = 'Loads'; b.textContent = \"⤢ Full screen\";</script>"
            "<script type='application/json'>{\"name\": \"vias\", \"title\": {\"text\": "
            "\"Frequency\"}, \"key\": \"Loads\"}</script>")
    out = i18n.translate_html(page)
    assert "<h2 id='loads'>负载</h2>" in out and "title='点击排序'" in out and ">负载</th>" in out
    assert ".x{content:'Loads'}" in out                  # styles untouched
    assert "var a = 'Loads'" in out and "⤢ 全屏" in out   # code untouched, messages translated
    assert '"name": "vias"' in out                       # layer toggles find traces by name
    assert '"text": "频率"' in out and '"key": "Loads"' in out


def test_a_layer_named_like_a_phrase_keeps_its_tickbox(chinese):
    """A board layer called "Ground": its tickbox's label is translated, but the trace it
    hides keeps the name the tickbox looks it up by."""
    page = ("<label><input type='checkbox' data-layer='Ground'> Ground</label>"
            "<script type='application/json'>{\"name\": \"Ground\"}</script>")
    out = i18n.translate_html(page)
    assert "data-layer='Ground'> 地</label>" in out and '"name": "Ground"' in out


def test_english_reports_are_unchanged(monkeypatch):
    monkeypatch.setenv("KIPI_LANG", "en")
    lang.reset()
    i18n.reset()
    try:
        page = "<h2>Loads</h2><p>PASS</p>"
        assert i18n.translate_html(page) == page and i18n.tr("Loads") == "Loads"
    finally:
        lang.reset()
        i18n.reset()


def test_figures_are_translated(chinese):
    pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1], label="noise margin")
    ax.set_xlabel("Time (µs)")
    ax.set_title("Input capacitor currents")
    ax.legend()
    with i18n.figure_context(fig):
        pass
    assert ax.get_xlabel() == "时间 (µs)" and ax.get_title() == "输入电容电流"
    assert ax.get_legend().get_texts()[0].get_text() == "噪声容限"
