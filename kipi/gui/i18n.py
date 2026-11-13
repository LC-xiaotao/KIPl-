"""Chinese localization for KiPI's Qt interface.

KiPI's GUI is written with English literals passed straight to Qt widgets, not through
``tr()``. Rather than rewrite every call site, this module translates at the Qt boundary:

* the setters that put text on screen (``setText``, ``setWindowTitle``, ``setToolTip``,
  ``addTab``, ...) are wrapped with :func:`tr`;
* an event filter translates the widgets of each window, dialog, menu and newly shown
  panel as they appear, which covers text given to constructors;
* Qt's own translations are installed for standard dialogs and buttons.

The catalog is ``translations/zh_CN.json``, keyed by the English text exactly as the code
writes it. Text with no entry stays English, so an untranslated control is never blank or
wrong. ``KIPI_LANG=en`` turns the whole layer off; ``KIPI_I18N_LOG=<file>`` appends every
untranslated on-screen string, which is how the catalog is grown.
"""

from __future__ import annotations

import json
import os
import re
import sys
import weakref
from pathlib import Path
from typing import Any, Iterable, Optional

_CATALOG: Optional[dict] = None
_ENABLED: Optional[bool] = None
_INSTALLED = False
_SEEN: "weakref.WeakSet" = weakref.WeakSet()
_MISSING_SEEN: set = set()
_FILTER = None
_TRANSLATING = False
_QT_TRANSLATOR = None
_PATCHED = False

#: A shortcut tacked onto a tooltip by ``with_keys``: "Open… (Ctrl+O)".
_SHORTCUT = re.compile(r"^(.*?)\s*\(([A-Za-z0-9+][A-Za-z0-9+ ]*)\)$")
#: A tab-separated accelerator Qt puts in an action's text: "Open…\tCtrl+O".
_TAB_SHORTCUT = re.compile(r"^(.*?)\t(.+)$")

PREFERENCE_KEY = "ui/language"


def system_language() -> str:
    """The language the computer is set to: ``zh_CN`` or ``en``."""
    try:
        from qtpy.QtCore import QLocale
        return "zh_CN" if QLocale.system().name().lower().startswith("zh") else "en"
    except Exception:  # noqa: BLE001 - no Qt yet: Chinese is this build's default
        return "zh_CN"


def preference() -> str:
    """The chosen language: ``system``, ``zh_CN`` or ``en``.

    ``KIPI_LANG`` still wins, so CI and scripts can force a language; otherwise the
    choice saved by the language menu, then the computer's own language.
    """
    choice = os.environ.get("KIPI_LANG", "").strip().lower()
    if choice:
        if choice.startswith("zh"):
            return "zh_CN"
        if choice in ("en", "english", "en_us", "en-us", "en_gb", "en-gb"):
            return "en"
    try:
        from qtpy.QtCore import QSettings
        saved = str(QSettings("KiPI", "KiPI").value(PREFERENCE_KEY, "system") or "system")
    except Exception:  # noqa: BLE001
        saved = "system"
    saved = saved.strip().lower()
    if saved.startswith("zh"):
        return "zh_CN"
    if saved in ("en", "english", "en_us", "en-us", "en_gb", "en-gb"):
        return "en"
    return "system"


def language() -> bool:
    """Whether the Chinese interface is on."""
    global _ENABLED
    if _ENABLED is None:
        choice = preference()
        _ENABLED = (system_language().startswith("zh") if choice == "system"
                    else choice.startswith("zh"))
    return _ENABLED


def set_preference(choice: str) -> bool:
    """Save and apply ``system``/``zh_CN``/``en`` now. Returns whether it changed."""
    install()
    choice = choice if choice in ("system", "zh_CN", "en") else "system"
    before = language()
    try:
        from qtpy.QtCore import QSettings
        QSettings("KiPI", "KiPI").setValue(PREFERENCE_KEY, choice)
    except Exception:  # noqa: BLE001
        pass
    # Reports read KIPI_LANG; keep the session's choice there too. A later start reads
    # the saved preference when the environment does not carry one.
    if choice == "system":
        os.environ.pop("KIPI_LANG", None)
    else:
        os.environ["KIPI_LANG"] = choice
    global _ENABLED
    _ENABLED = None
    after = language()
    _install_qt_translations(after)
    retranslate_all()
    return before != after


def _catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        folder = Path(__file__).with_name("translations")
        merged: dict = {}
        for path in sorted(folder.glob("zh_CN*.json")):
            try:
                merged.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        _CATALOG = merged
    return _CATALOG


def _lookup(text: str) -> Optional[str]:
    hit = _catalog().get(text)
    if hit is not None:
        return hit
    if "&" in text:                     # Qt mnemonic: "&File" -> "File"
        plain = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
        hit = _catalog().get(plain)
        if hit is not None:
            return hit
    return None


# ---------------------------------------------------------------------------
# The English source of each on-screen string
# ---------------------------------------------------------------------------

def _property(key: str) -> str:
    return f"kipi_i18n_{key}"


def _source_text(obj, key: str, current: Any) -> Any:
    """The English text behind ``current``: remembered on the object, or ``current``."""
    if not isinstance(current, str):
        return current
    try:
        stored = obj.property(_property(key))
    except Exception:                   # noqa: BLE001 - not a QObject with properties
        return current
    if stored is None:
        try:
            obj.setProperty(_property(key), current)
        except Exception:               # noqa: BLE001
            return current
        return current
    return str(stored)


def _source_list(obj, key: str, current: list) -> list:
    """The English texts behind a list (a combo's items, a tab bar's tabs)."""
    try:
        stored = obj.property(_property(key))
    except Exception:                   # noqa: BLE001
        stored = None
    try:
        stored = list(stored) if stored is not None else []
    except TypeError:
        stored = []
    if len(stored) != len(current):
        stored = [str(v) for v in current]
        try:
            obj.setProperty(_property(key), list(stored))
        except Exception:               # noqa: BLE001
            return stored
    return [str(v) for v in stored]


def _store_list(obj, key: str, values: list) -> None:
    try:
        obj.setProperty(_property(key), [str(v) for v in values])
    except Exception:                   # noqa: BLE001
        pass


def _apply_text(obj, key: str, getter, setter, enabled: bool) -> None:
    original = _source_text(obj, key, getter())
    if not isinstance(original, str):
        return
    target = tr(original) if enabled else original
    if target != getter():
        setter(target)


def _apply_list(obj, key: str, current_getter, item_getter, item_setter,
                enabled: bool) -> None:
    current = list(current_getter())
    originals = _source_list(obj, key, current)
    for i, original in enumerate(originals):
        target = tr(original) if enabled else original
        if item_getter(i) != target:
            item_setter(i, target)


def tr(text: Any) -> Any:
    """``text`` in Chinese when the catalog has it; otherwise unchanged."""
    if not isinstance(text, str) or not text or not language():
        return text
    hit = _lookup(text)
    if hit is not None:
        return hit

    # Tooltips built as f"{tip} ({keys})" and action text with Qt's tab shortcut.
    m = _TAB_SHORTCUT.match(text)
    if m:
        base = _lookup(m.group(1))
        if base is not None:
            return base + "\t" + m.group(2)
    m = _SHORTCUT.match(text)
    if m:
        base = _lookup(m.group(1))
        if base is not None:
            return base + " (" + m.group(2) + ")"

    # Titles built at run time: "KiPI 1.0.0 — Power Integrity (standalone)".
    m = re.match(r"^KiPI ([\d.]+) — (.*)$", text)
    if m:
        return f"KiPI {m.group(1)} — {tr(m.group(2))}"
    m = re.match(r"^KiPI — (.*)$", text)
    if m:
        return f"KiPI — {tr(m.group(1))}"
    m = re.match(r"^Phase (\d+)$", text)
    if m:
        return f"相位 {m.group(1)}"
    m = re.match(r"^Point (\d+)$", text)
    if m:
        return f"点 {m.group(1)}"
    m = re.match(r"^DC Accuracy Calculator: (.+)$", text)
    if m:
        return f"DC 精度计算器：{m.group(1)}"
    m = re.match(r"^(.*) \(standalone\)$", text)
    if m:
        return f"{tr(m.group(1))}（独立版）"
    m = re.match(r"^New setup \(will be saved as (.+)\)$", text)
    if m:
        return f"新设置（将保存为 {m.group(1)}）"
    m = re.match(r"^not set \((.+)\)$", text)
    if m:
        return f"未设置（{m.group(1)}）"
    m = re.match(r"^Load from (.+)$", text)
    if m:
        return f"从 {m.group(1)} 加载"
    m = re.match(r"^Board ([\d.]+ mm)$", text)
    if m:
        return f"板卡 {m.group(1)}"
    m = re.match(r"^KiPI — Tolerance stack-up — (.+)$", text)
    if m:
        return f"KiPI — 容差堆叠 — {m.group(1)}"
    m = re.match(r"^(\d+) load\(s\)\. Ripple and transient through a 20 MHz limit\.$", text)
    if m:
        return f"{m.group(1)} 个负载。纹波和瞬态通过 20 MHz 带宽限制。"
    m = re.match(r"^(\d+) load\(s\)\. Ripple and transient at full bandwidth\.$", text)
    if m:
        return f"{m.group(1)} 个负载。纹波和瞬态为全带宽。"

    # Titles and labels the waveform plots build at run time (matplotlib axes have no Qt
    # setter to patch, so the call sites pass their strings through tr() themselves).
    m = re.match(r"^Amplitude \((.+?) peak\)$", text)
    if m:
        return f"幅值（{m.group(1)} 峰值）"
    m = re.match(r"^Time \((.+)\)$", text)
    if m:
        return f"时间 ({m.group(1)})"
    m = re.match(r"^Show (.+)$", text)
    if m:
        return f"显示 {m.group(1)}"
    m = re.match(r"^noise margin ±(.+)$", text)
    if m:
        return f"噪声容限 ±{m.group(1)}"
    m = re.match(r"^the ±(.+) mV noise margin is off the scale$", text)
    if m:
        return f"±{m.group(1)} mV 噪声容限超出显示范围"
    m = re.match(r"^(.+): (.+) mV peak against its ±(.+) mV margin, from (.+)$", text)
    if m:
        return (f"{m.group(1)}：峰值 {m.group(2)} mV，相对 ±{m.group(3)} mV 裕量，"
                f"来自 {m.group(4)}")
    m = re.match(r"^(.+?) \((buck|boost), (.+) V → (.+) V, (.+) A, (.+) kHz, D = (.+)\)$",
                 text)
    if m:
        top = "降压" if m.group(2) == "buck" else "升压"
        return (f"{m.group(1)}（{top}，{m.group(3)} V → {m.group(4)} V，{m.group(5)} A，"
                f"{m.group(6)} kHz，D = {m.group(7)}）")
    m = re.match(r"^(.+) held (high|low) \(driver (.+) Ω\): (.+) mV toward (.+), "
                 r"(.+) mV away$", text)
    if m:
        st = "高电平" if m.group(2) == "high" else "低电平"
        return (f"{m.group(1)} 保持{st}（驱动 {m.group(3)} Ω）：{m.group(4)} mV 朝向 "
                f"{m.group(5)}，距其 {m.group(6)} mV")
    m = re.match(r"^its (.+) edge is slow enough that the PDN is still capacitive at its "
                 r"(.+): no ESL spike stands out from the droop \(−(.+) mV over the edge\)$",
                 text)
    if m:
        return (f"其 {m.group(1)} 边沿足够慢，PDN 在 {m.group(2)} 时仍呈容性："
                f"没有超出下垂的 ESL 尖峰（边沿内 −{m.group(3)} mV）")
    m = re.match(r"^ESL spike L·di/dt = (.+) × (.+) A/µs = (.+) mV over its (.+) edge; "
                 r"−(.+) mV there with the droop$", text)
    if m:
        return (f"ESL 尖峰 L·di/dt = {m.group(1)} × {m.group(2)} A/µs = {m.group(3)} mV"
                f"（{m.group(4)} 边沿内）；连同下垂为 −{m.group(5)} mV")
    m = re.match(r"^VRM bandwidth (.+)$", text)
    if m:
        return f"VRM 带宽 {m.group(1)}"
    m = re.match(r"^(.+): (.+) against (.+)$", text)
    if m:
        return f"{m.group(1)}：{m.group(2)} 对 {m.group(3)}"

    # Keep leading/trailing spaces: "Mode: " and table cells use them.
    stripped = text.strip()
    if stripped != text:
        hit = _lookup(stripped)
        if hit is not None:
            lead = text[:len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            return lead + hit + trail

    _log_missing(text)
    return text


def _log_missing(text: str) -> None:
    path = os.environ.get("KIPI_I18N_LOG")
    if not path or len(text) < 3 or len(text) > 300 or text in _MISSING_SEEN:
        return
    if text.startswith("<") or "://" in text or text.startswith(("KIPI_", "%", "/")):
        return
    if not re.search(r"[A-Za-z]{2}", text):
        return
    if re.search(r"[一-鿿]", text):
        return
    _MISSING_SEEN.add(text)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text.replace("\n", " ") + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Qt hooks
# ---------------------------------------------------------------------------

def _wrap_setter(cls, name: str, at: int = 0, each: bool = False,
                 key: str = "text") -> None:
    """Remember the English argument of ``cls.name``, then translate it."""
    original = getattr(cls, name, None)
    if original is None:
        return

    def wrapper(self, *args, **kwargs):
        if _TRANSLATING:
            return original(self, *args, **kwargs)
        args = list(args)
        if len(args) > at:
            if each and isinstance(args[at], (list, tuple)):
                _store_list(self, key, list(args[at]))
                args[at] = [tr(v) for v in args[at]]
            elif isinstance(args[at], str):
                _source_text(self, key, args[at])
                args[at] = tr(args[at])
        if kwargs:
            for k in ("text", "title", "label", "toolTip"):
                if k in kwargs and isinstance(kwargs[k], str):
                    _source_text(self, key, kwargs[k])
                    kwargs[k] = tr(kwargs[k])
        return original(self, *args, **kwargs)

    try:
        setattr(cls, name, wrapper)
    except (TypeError, AttributeError):
        pass


def _wrap_combo() -> None:
    """Keep each combo item's English text beside its translated one."""
    from qtpy.QtWidgets import QComboBox

    def _sources(combo):
        return _source_list(combo, "items",
                            [combo.itemText(i) for i in range(combo.count())])

    def add_item(self, *args, **kwargs):
        if _TRANSLATING or not args or not isinstance(args[0], str):
            return add_item.original(self, *args, **kwargs)
        sources = _sources(self)
        sources.append(args[0])
        _store_list(self, "items", sources)
        args = list(args)
        args[0] = tr(args[0])
        return add_item.original(self, *args, **kwargs)

    def add_items(self, *args, **kwargs):
        if _TRANSLATING or not args or not isinstance(args[0], (list, tuple)):
            return add_items.original(self, *args, **kwargs)
        sources = _sources(self)
        sources.extend(str(v) for v in args[0])
        _store_list(self, "items", sources)
        args = list(args)
        args[0] = [tr(v) for v in args[0]]
        return add_items.original(self, *args, **kwargs)

    def insert_item(self, *args, **kwargs):
        if _TRANSLATING or len(args) < 2 or not isinstance(args[1], str):
            return insert_item.original(self, *args, **kwargs)
        sources = _sources(self)
        index = max(0, min(int(args[0]), len(sources)))
        sources.insert(index, args[1])
        _store_list(self, "items", sources)
        args = list(args)
        args[1] = tr(args[1])
        return insert_item.original(self, *args, **kwargs)

    def set_item_text(self, *args, **kwargs):
        if _TRANSLATING or len(args) < 2 or not isinstance(args[1], str):
            return set_item_text.original(self, *args, **kwargs)
        sources = _sources(self)
        index = int(args[0])
        if 0 <= index < len(sources):
            sources[index] = args[1]
            _store_list(self, "items", sources)
        args = list(args)
        args[1] = tr(args[1])
        return set_item_text.original(self, *args, **kwargs)

    def remove_item(self, *args, **kwargs):
        if not _TRANSLATING and args:
            sources = _sources(self)
            index = int(args[0])
            if 0 <= index < len(sources):
                del sources[index]
                _store_list(self, "items", sources)
        return remove_item.original(self, *args, **kwargs)

    def clear(self):
        if not _TRANSLATING:
            _store_list(self, "items", [])
        return clear.original(self)

    for name, function in (("addItem", add_item), ("addItems", add_items),
                           ("insertItem", insert_item), ("setItemText", set_item_text),
                           ("removeItem", remove_item), ("clear", clear)):
        original = getattr(QComboBox, name, None)
        if original is None:
            continue
        function.original = original
        try:
            setattr(QComboBox, name, function)
        except (TypeError, AttributeError):
            pass


def _wrap_tabs() -> None:
    """Keep each tab's English text beside its translated one."""
    from qtpy.QtWidgets import QTabWidget

    def _sources(tabs):
        return _source_list(tabs, "tabs",
                            [tabs.tabText(i) for i in range(tabs.count())])

    def add_tab(self, *args, **kwargs):
        if _TRANSLATING or len(args) < 2 or not isinstance(args[1], str):
            return add_tab.original(self, *args, **kwargs)
        sources = _sources(self)
        sources.append(args[1])
        _store_list(self, "tabs", sources)
        args = list(args)
        args[1] = tr(args[1])
        return add_tab.original(self, *args, **kwargs)

    def insert_tab(self, *args, **kwargs):
        if _TRANSLATING or len(args) < 3 or not isinstance(args[2], str):
            return insert_tab.original(self, *args, **kwargs)
        sources = _sources(self)
        index = max(0, min(int(args[0]), len(sources)))
        sources.insert(index, args[2])
        _store_list(self, "tabs", sources)
        args = list(args)
        args[2] = tr(args[2])
        return insert_tab.original(self, *args, **kwargs)

    def set_tab_text(self, *args, **kwargs):
        if _TRANSLATING or len(args) < 2 or not isinstance(args[1], str):
            return set_tab_text.original(self, *args, **kwargs)
        sources = _sources(self)
        index = int(args[0])
        if 0 <= index < len(sources):
            sources[index] = args[1]
            _store_list(self, "tabs", sources)
        args = list(args)
        args[1] = tr(args[1])
        return set_tab_text.original(self, *args, **kwargs)

    def remove_tab(self, *args, **kwargs):
        if not _TRANSLATING and args:
            sources = _sources(self)
            index = int(args[0])
            if 0 <= index < len(sources):
                del sources[index]
                _store_list(self, "tabs", sources)
        return remove_tab.original(self, *args, **kwargs)

    def clear(self):
        if not _TRANSLATING:
            _store_list(self, "tabs", [])
        return clear.original(self)

    for name, function in (("addTab", add_tab), ("insertTab", insert_tab),
                           ("setTabText", set_tab_text), ("removeTab", remove_tab),
                           ("clear", clear)):
        original = getattr(QTabWidget, name, None)
        if original is None:
            continue
        function.original = original
        try:
            setattr(QTabWidget, name, function)
        except (TypeError, AttributeError):
            pass


def _wrap_static(cls, name: str, title_at: int = 1, text_at: int = 2) -> None:
    original = getattr(cls, name, None)
    if original is None:
        return

    def wrapper(*args, **kwargs):
        args = list(args)
        if len(args) > title_at:
            args[title_at] = tr(args[title_at])
        if len(args) > text_at:
            args[text_at] = tr(args[text_at])
        return original(*args, **kwargs)

    try:
        setattr(cls, name, staticmethod(wrapper))
    except (TypeError, AttributeError):
        pass


def _patch_widgets() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    from qtpy import QtGui, QtWidgets as W

    _wrap_setter(W.QLabel, "setText", key="text")
    _wrap_setter(W.QAbstractButton, "setText", key="text")
    _wrap_setter(W.QWidget, "setWindowTitle", key="title")
    _wrap_setter(W.QWidget, "setToolTip", key="tooltip")
    _wrap_setter(W.QGroupBox, "setTitle", key="title")
    _wrap_setter(W.QMenu, "setTitle", key="title")
    _wrap_setter(QtGui.QAction, "setText", key="text")
    _wrap_setter(QtGui.QAction, "setToolTip", key="tooltip")
    _wrap_setter(W.QLineEdit, "setPlaceholderText", key="placeholder")
    _wrap_setter(W.QAbstractSpinBox, "setSpecialValueText", key="special")
    _wrap_setter(W.QStatusBar, "showMessage", key="status")
    _wrap_setter(W.QTableWidget, "setHorizontalHeaderLabels", each=True,
                 key="horizontal_headers")
    _wrap_setter(W.QTableWidget, "setVerticalHeaderLabels", each=True,
                 key="vertical_headers")
    _wrap_combo()
    _wrap_tabs()
    for name in ("information", "warning", "critical", "question"):
        _wrap_static(W.QMessageBox, name)


def _install_qt_translations(enabled: bool) -> None:
    """Qt's own Chinese translations: standard buttons, file dialogs, message boxes."""
    global _QT_TRANSLATOR
    try:
        from qtpy.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
    except Exception:  # noqa: BLE001
        return
    if _QT_TRANSLATOR is not None:
        try:
            QCoreApplication.removeTranslator(_QT_TRANSLATOR)
        except Exception:  # noqa: BLE001
            pass
        _QT_TRANSLATOR = None
    if not enabled:
        return
    name = QLocale.system().name()
    if not name.lower().startswith("zh"):
        name = "zh_CN"          # Chinese chosen on a non-Chinese system
    folder = None
    try:
        folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    except AttributeError:
        try:
            folder = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
        except Exception:  # noqa: BLE001
            folder = None
    if not folder:
        return
    for stem in (f"qtbase_{name}", "qtbase_zh_CN", f"qt_{name}", "qt_zh_CN"):
        translator = QTranslator()
        if translator.load(stem, folder):
            QCoreApplication.installTranslator(translator)
            # Keep it alive: Qt does not own the Python object.
            _QT_TRANSLATOR = translator
            break


def _make_filter():
    """A QObject event filter; subclassing is what lets Qt call ``eventFilter``."""
    from qtpy.QtCore import QEvent, QObject

    class _TranslateFilter(QObject):
        def eventFilter(self, obj, event):  # noqa: N802 - Qt spelling
            try:
                module = (type(obj).__module__ or "").lower()
                if event.type() == QEvent.Type.Show and not module.startswith(
                        ("vtk", "pyvistaqt", "pyvista")):
                    # Translate this widget only. Walking the whole tree here (as this
                    # filter first did) reaches VTK's native window and stops the embedded
                    # 3D view from drawing inside a QTabWidget on Qt 6.
                    _translate_one(obj)
                    from qtpy.QtWidgets import QMenu, QMenuBar, QToolBar
                    if isinstance(obj, (QMenu, QMenuBar, QToolBar)):
                        for action in obj.actions():
                            _translate_one(action)
            except Exception:  # noqa: BLE001 - never break the event Qt is delivering
                if os.environ.get("KIPI_I18N_DEBUG"):
                    import traceback
                    traceback.print_exc()
            return False

        def install(self) -> None:
            from qtpy.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)

    return _TranslateFilter()


def _keep_filter():
    global _FILTER
    if _FILTER is None:
        _FILTER = _make_filter()
    return _FILTER


def translate_tree(root) -> None:
    """Translate (or restore) ``root`` and every widget/action below it."""
    global _TRANSLATING
    if root is None or _TRANSLATING:
        return
    from qtpy.QtGui import QAction
    from qtpy.QtWidgets import QWidget

    _TRANSLATING = True
    stack = [root]
    try:
        _translate_stack(stack, QAction, QWidget)
    finally:
        _TRANSLATING = False


def _translate_stack(stack, QAction, QWidget) -> None:
    while stack:
        item = stack.pop()
        if item is None:
            continue
        # Never touch VTK's native windows: translating their widgets (setting titles and
        # tooltips) when they are shown stops the embedded 3D view from drawing inside a
        # QTabWidget on Qt 6.
        module = (type(item).__module__ or "").lower()
        if module.startswith(("vtk", "pyvistaqt", "pyvista")):
            continue
        try:
            if item in _SEEN:
                continue
            _SEEN.add(item)
        except TypeError:
            pass
        try:
            _translate_one(item)
        except (RuntimeError, AttributeError):
            continue
        try:
            if item.property("kipi_i18n_skip_children"):
                continue
        except Exception:  # noqa: BLE001
            pass
        try:
            if isinstance(item, QWidget):
                stack.extend(item.findChildren(QWidget))
                stack.extend(item.findChildren(QAction))
        except Exception:  # noqa: BLE001
            pass
        try:
            actions: Iterable = item.actions()
        except Exception:  # noqa: BLE001
            actions = ()
        for action in actions:
            if isinstance(action, QAction):
                stack.append(action)


def _translate_headers(table, key: str, count: int, item_getter, enabled: bool) -> None:
    if count <= 0:
        return
    current = [item_getter(i).text() if item_getter(i) is not None else ""
               for i in range(count)]
    originals = _source_list(table, key, current)
    for i, original in enumerate(originals):
        header = item_getter(i)
        if header is None:
            continue
        target = tr(original) if enabled else original
        if header.text() != target:
            header.setText(target)


def _translate_one(item) -> None:
    global _TRANSLATING
    from qtpy.QtGui import QAction
    from qtpy.QtWidgets import (QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit,
                                QMenu, QTabWidget, QTableWidget, QWidget)

    previous = _TRANSLATING
    _TRANSLATING = True
    try:
        enabled = language()
        if isinstance(item, QAction):
            _apply_text(item, "text", item.text, item.setText, enabled)
            _apply_text(item, "tooltip", item.toolTip, item.setToolTip, enabled)
            menu = item.menu()
            if menu is not None:
                _apply_text(menu, "title", menu.title, menu.setTitle, enabled)
            return
        if isinstance(item, QWidget):
            if item.windowTitle():
                _apply_text(item, "title", item.windowTitle, item.setWindowTitle, enabled)
            if item.toolTip():
                _apply_text(item, "tooltip", item.toolTip, item.setToolTip, enabled)
            if isinstance(item, QLabel) and item.text():
                _apply_text(item, "text", item.text, item.setText, enabled)
            if isinstance(item, QAbstractButton) and item.text():
                _apply_text(item, "text", item.text, item.setText, enabled)
            if isinstance(item, QGroupBox) and item.title():
                _apply_text(item, "title", item.title, item.setTitle, enabled)
            if isinstance(item, QMenu) and item.title():
                _apply_text(item, "title", item.title, item.setTitle, enabled)
            if isinstance(item, QLineEdit) and item.placeholderText():
                _apply_text(item, "placeholder", item.placeholderText,
                            item.setPlaceholderText, enabled)
            if isinstance(item, QTabWidget) and item.count():
                _apply_list(item, "tabs",
                            lambda: [item.tabText(i) for i in range(item.count())],
                            item.tabText, item.setTabText, enabled)
            if isinstance(item, QComboBox) and item.count():
                _apply_list(item, "items",
                            lambda: [item.itemText(i) for i in range(item.count())],
                            item.itemText, item.setItemText, enabled)
            if isinstance(item, QTableWidget):
                _translate_headers(item, "horizontal_headers", item.columnCount(),
                                   item.horizontalHeaderItem, enabled)
                _translate_headers(item, "vertical_headers", item.rowCount(),
                                   item.verticalHeaderItem, enabled)
    finally:
        _TRANSLATING = previous


def retranslate_all() -> None:
    """Re-apply the current language to every open window and dialog."""
    from qtpy.QtWidgets import QApplication
    global _SEEN
    _SEEN = weakref.WeakSet()
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        try:
            translate_tree(widget)
        except RuntimeError:          # the widget went away while we walked
            continue


def install() -> None:
    """Install the language layer (once). Safe to call more than once."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    try:
        _install_qt_translations(language())
        _patch_widgets()
        _keep_filter().install()
    except Exception as exc:  # noqa: BLE001 - never keep KiPI from starting
        print(f"KiPI: language interface could not be installed: {exc}", file=sys.stderr)


def uninstall_for_tests() -> None:
    """Forget what was installed (tests only)."""
    global _INSTALLED, _SEEN
    _INSTALLED = False
    _SEEN = weakref.WeakSet()
