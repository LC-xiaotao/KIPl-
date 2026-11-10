"""Chinese reports: the DC, AC, Coupled Noise and Tolerance reports, HTML and PDF.

The report modules build their pages from English literals and f-strings. Rather than
thread a translation call through every one of them, the finished page is translated
where every report goes out (:func:`kipi.dc.report.html.finish`), and every figure where
it is rendered (:func:`kipi.dc.report.html._png`):

* text between tags, and the ``title``/``placeholder`` attributes, by the catalog
  ``translations/report_zh_CN.json``: exact phrases first, then templates in which
  ``{}`` stands for a number, a name or a unit;
* inside scripts only Plotly's ``"text"``, ``"name"`` and ``"title"`` strings, and the
  report's own JavaScript messages, so no code or data key is touched;
* matplotlib figures' titles, labels and legends, drawn with a CJK font.

Anything the catalog does not know stays English, so a report is never blank or wrong.
``KIPI_LANG=en`` keeps the reports English (see :mod:`kipi.core.lang`).
"""

from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from kipi.core import lang

_CATALOG: Optional[Dict[str, str]] = None
_TEMPLATES: Optional[List[Tuple[re.Pattern, str]]] = None
_JS: Optional[Dict[str, str]] = None

#: Fonts with Chinese glyphs, best first, for figures and pages.
CJK_FONTS = ("Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC",
             "Source Han Sans SC", "WenQuanYi Micro Hei", "Arial Unicode MS")


def enabled() -> bool:
    return lang.chinese()


_PHRASES: Optional[List[Tuple[re.Pattern, str]]] = None

# In an English template, {} is any text and {#} a number. In its Chinese, {} takes the
# values in order, {0}, {1}... by position (where Chinese puts them in another order), and
# {p} the next value with the catalog's phrases put in it (lists such as the stackup).
_EN_SLOT = re.compile(r"\{#?\}")
_ZH_SLOT = re.compile(r"\{(\d+|p|)\}")
_NUMBER = r"([-+]?\d[\d.,]*(?:[eE][-+]?\d+)?)"


def _compile(en: str) -> re.Pattern:
    """The pattern of the English template ``en``: its text between the slots matched as
    written (one space for any run of white space, so spaces around a slot are kept)."""
    norm = re.sub(r"\s+", " ", en.strip())
    out, pos = ["^"], 0
    for m in _EN_SLOT.finditer(norm):
        out.append(re.escape(norm[pos:m.start()]))
        out.append(_NUMBER if m.group() == "{#}" else "(.+?)")
        pos = m.end()
    out.append(re.escape(norm[pos:]) + "$")
    return re.compile("".join(out), re.S)


def _load() -> None:
    global _CATALOG, _TEMPLATES, _JS, _PHRASES
    if _CATALOG is not None:
        return
    path = Path(__file__).with_name("translations") / "report_zh_CN.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    _JS = dict(data.pop("__js__", {}))
    phrases = dict(data.pop("__phrases__", {}))
    exact: Dict[str, str] = {}
    templates: List[Tuple[str, str]] = []
    for en, zh in data.items():
        if en.startswith("__"):
            continue
        if _EN_SLOT.search(en):
            templates.append((en, zh))
        else:
            exact[" ".join(en.split())] = zh
    # Longest first: a template that says more wins over a shorter one it contains.
    _TEMPLATES = [(_compile(en), zh) for en, zh in sorted(templates, key=lambda t: -len(t[0]))]
    _PHRASES = [(re.compile(r"(?<![A-Za-z0-9_])" + re.escape(en) + r"(?![A-Za-z0-9_])"), zh)
                for en, zh in sorted(phrases.items(), key=lambda t: -len(t[0]))]
    _CATALOG = exact


def reset() -> None:
    """Read the catalog again (tests)."""
    global _CATALOG, _TEMPLATES, _JS, _PHRASES
    _CATALOG = _TEMPLATES = _JS = _PHRASES = None


def _phrases(text: str) -> str:
    """``text`` with the catalog's phrases (whole words) put in Chinese: for lists that
    are built from many small parts, such as the stackup or the via plating rules."""
    for pattern, zh in _PHRASES or ():
        text = pattern.sub(zh, text)
    return text


def _fill(zh: str, values) -> str:
    values = list(values)
    order = iter(range(len(values)))

    def slot(m):
        key = m.group(1)
        i = int(key) if key.isdigit() else next(order, None)
        if i is None or i >= len(values):
            return m.group(0)
        return _phrases(values[i]) if key == "p" else tr(values[i])
    return _ZH_SLOT.sub(slot, zh)


def tr(text: str) -> str:
    """``text`` in Chinese when the catalog knows it (whole, or as a template); else as
    it is. Leading and trailing white space is kept."""
    if not text or not enabled():
        return text
    _load()
    core = " ".join(text.split())
    if not core or not re.search(r"[A-Za-z]", core):
        return text
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    hit = _CATALOG.get(core)
    if hit is None:
        for pattern, zh in _TEMPLATES:
            m = pattern.match(core)
            if m:
                hit = _fill(zh, m.groups())
                break
    if hit is None:
        # A header split around unit spans: "Highest pin (" ... ")"; a label: "Layers:".
        for suffix in (" (", ":", " :", ".", ",", ";"):
            if core.endswith(suffix) and len(core) > len(suffix):
                base = core[:-len(suffix)].strip()
                inner = _CATALOG.get(base)
                if inner is not None:
                    # " (" opens a unit the next text node closes with an ASCII ")".
                    hit = inner + {" (": " (", ":": "：", " :": "：", ".": "。",
                                   ",": "，", ";": "；"}[suffix]
                    break
    if hit is None:
        return text
    return lead + hit + trail


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

_SCRIPT = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)
_STYLE = re.compile(r"(<style\b[^>]*>.*?</style>)", re.S | re.I)
_TAG = re.compile(r"(<[^>]+>)")
_ATTR = re.compile(r"""(\b(?:title|data-placeholder|placeholder|aria-label)=)(['"])(.*?)\2""",
                   re.S)
# Plotly's human strings in its figure JSON: "text", "name" and "title" values.
_PLOTLY_STR = re.compile(r'("(?:text|name|title)"\s*:\s*)"((?:[^"\\]|\\.)*)"')


def _text_node(segment: str) -> str:
    if not segment.strip():
        return segment
    raw = _html.unescape(segment)
    zh = tr(raw)
    return segment if zh == raw else _html.escape(zh, quote=False)


def _attrs(tag: str) -> str:
    def sub(m):
        raw = _html.unescape(m.group(3))
        zh = tr(raw)
        if zh == raw:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{_html.escape(zh, quote=True)}{m.group(2)}"
    return _ATTR.sub(sub, tag)


def _markup(chunk: str) -> str:
    """Translate the text and attributes of HTML with no scripts or styles in it."""
    out = []
    for piece in _TAG.split(chunk):
        if piece.startswith("<") and piece.endswith(">"):
            out.append(_attrs(piece))
        else:
            out.append(_text_node(piece))
    return "".join(out)


_DATA_LAYER = re.compile(r"""data-layer=(['"])(.*?)\1""")
_KEEP: set = set()      # names the page's layer tickboxes look traces up by


def _script(body: str) -> str:
    def plotly(m):
        try:
            raw = json.loads(f'"{m.group(2)}"')
        except ValueError:
            return m.group(0)
        if m.group(1).lstrip('"').startswith("name") and raw in _KEEP:
            return m.group(0)       # a layer's trace: its tickbox finds it by this name
        zh = tr(raw)
        if zh == raw:
            return m.group(0)
        return m.group(1) + json.dumps(zh, ensure_ascii=False)
    body = _PLOTLY_STR.sub(plotly, body)
    for en, zh in (_JS or {}).items():
        body = body.replace(f'"{en}"', json.dumps(zh, ensure_ascii=False))
    return body


def translate_js(script: str) -> str:
    """The report's own JavaScript with its user-facing messages in Chinese."""
    if not enabled() or not script:
        return script
    _load()
    return _script(script)


def translate_html(page: str) -> str:
    """The report page ``page`` in Chinese (unchanged when the reports are English)."""
    if not enabled():
        return page
    _load()
    global _KEEP
    _KEEP = {_html.unescape(m.group(2)) for m in _DATA_LAYER.finditer(page)}
    out = []
    pos = 0
    for m in _SCRIPT.finditer(page):
        out.append(_outside_scripts(page[pos:m.start()]))
        out.append(m.group(1) + _script(m.group(2)) + m.group(3))
        pos = m.end()
    out.append(_outside_scripts(page[pos:]))
    return "".join(out)


def _outside_scripts(chunk: str) -> str:
    parts = _STYLE.split(chunk)
    return "".join(p if p.lower().startswith("<style") else _markup(p) for p in parts)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _cjk_font() -> Optional[str]:
    try:
        from matplotlib import font_manager
    except ImportError:
        return None
    names = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in CJK_FONTS if n in names), None)


def figure_context(fig):
    """A context for saving ``fig``: its titles, labels and legend entries in Chinese,
    drawn with a font that has the glyphs. A no-op when the reports are English."""
    import contextlib
    if not enabled():
        return contextlib.nullcontext()
    from matplotlib import rcParams, rc_context
    from matplotlib.text import Text
    for t in fig.findobj(Text):
        s = t.get_text()
        if s and re.search(r"[A-Za-z]{2}", s):
            zh = tr(s)
            if zh != s:
                t.set_text(zh)
    font = _cjk_font()
    if font is None:
        return contextlib.nullcontext()
    return rc_context({"font.sans-serif": [font, *rcParams["font.sans-serif"]],
                       "font.family": "sans-serif", "axes.unicode_minus": False})
