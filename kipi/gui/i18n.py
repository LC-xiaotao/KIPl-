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

#: A shortcut tacked onto a tooltip by ``with_keys``: "Open… (Ctrl+O)".
_SHORTCUT = re.compile(r"^(.*?)\s*\(([A-Za-z0-9+][A-Za-z0-9+ ]*)\)$")
#: A tab-separated accelerator Qt puts in an action's text: "Open…\tCtrl+O".
_TAB_SHORTCUT = re.compile(r"^(.*?)\t(.+)$")


def language() -> bool:
    """Whether the Chinese interface is on."""
    global _ENABLED
    if _ENABLED is None:
        choice = os.environ.get("KIPI_LANG", "").strip().lower()
        if choice in ("en", "english", "en_us", "en-gb"):
            _ENABLED = False
        elif choice.startswith("zh"):
            _ENABLED = True
        else:
            try:
                from qtpy.QtCore import QLocale
                _ENABLED = QLocale.system().name().lower().startswith("zh")
            except Exception:  # noqa: BLE001 - no Qt yet: Chinese is this build's default
                _ENABLED = True
    return _ENABLED


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

def _wrap_setter(cls, name: str, at: int = 0, each: bool = False) -> None:
    """Translate argument ``at`` of ``cls.name``; ``each`` for a list argument."""
    original = getattr(cls, name, None)
    if original is None:
        return

    def wrapper(self, *args, **kwargs):
        args = list(args)
        if len(args) > at:
            if each:
                args[at] = [tr(v) for v in args[at]] if isinstance(args[at], (list, tuple)) else args[at]
            else:
                args[at] = tr(args[at])
        if kwargs:
            for key in ("text", "title", "label", "toolTip"):
                if key in kwargs:
                    kwargs[key] = tr(kwargs[key])
        return original(self, *args, **kwargs)

    try:
        setattr(cls, name, wrapper)
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
    from qtpy import QtGui, QtWidgets as W

    _wrap_setter(W.QLabel, "setText")
    _wrap_setter(W.QAbstractButton, "setText")
    _wrap_setter(W.QWidget, "setWindowTitle")
    _wrap_setter(W.QWidget, "setToolTip")
    _wrap_setter(W.QGroupBox, "setTitle")
    _wrap_setter(W.QMenu, "setTitle")
    _wrap_setter(QtGui.QAction, "setText")
    _wrap_setter(QtGui.QAction, "setToolTip")
    _wrap_setter(W.QLineEdit, "setPlaceholderText")
    _wrap_setter(W.QAbstractSpinBox, "setSpecialValueText")
    _wrap_setter(W.QStatusBar, "showMessage")
    _wrap_setter(W.QTabWidget, "setTabText", at=1)
    _wrap_setter(W.QTabWidget, "addTab", at=1)
    _wrap_setter(W.QTabWidget, "insertTab", at=2)
    _wrap_setter(W.QTableWidget, "setHorizontalHeaderLabels", each=True)
    _wrap_setter(W.QTableWidget, "setVerticalHeaderLabels", each=True)
    _wrap_setter(W.QComboBox, "addItem")
    _wrap_setter(W.QComboBox, "addItems", each=True)
    _wrap_setter(W.QComboBox, "insertItem", at=1)
    for name in ("information", "warning", "critical", "question"):
        _wrap_static(W.QMessageBox, name)


def _qt_translations() -> None:
    """Qt's own Chinese translations: standard buttons, file dialogs, message boxes."""
    try:
        from qtpy.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
    except Exception:  # noqa: BLE001
        return
    name = QLocale.system().name()
    if not name.lower().startswith("zh"):
        name = "zh_CN"          # KIPI_LANG forced Chinese on a non-Chinese system
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
            kept = getattr(_qt_translations, "_translators", [])
            _qt_translations._translators = kept + [translator]
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
    """Translate ``root`` and every widget/action below it, once."""
    global _TRANSLATING
    if not language() or root is None or _TRANSLATING:
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


def _translate_one(item) -> None:
    from qtpy.QtGui import QAction
    from qtpy.QtWidgets import (QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit,
                                QMenu, QTabWidget, QWidget)

    if isinstance(item, QAction):
        item.setText(tr(item.text()))
        item.setToolTip(tr(item.toolTip()))
        menu = item.menu()
        if menu is not None:
            menu.setTitle(tr(menu.title()))
        return
    if isinstance(item, QWidget):
        title = item.windowTitle()
        if title:
            item.setWindowTitle(tr(title))
        tip = item.toolTip()
        if tip:
            item.setToolTip(tr(tip))
        if isinstance(item, QLabel):
            item.setText(tr(item.text()))
        if isinstance(item, QAbstractButton):
            item.setText(tr(item.text()))
        if isinstance(item, QGroupBox):
            item.setTitle(tr(item.title()))
        if isinstance(item, QMenu):
            item.setTitle(tr(item.title()))
        if isinstance(item, QLineEdit) and item.placeholderText():
            item.setPlaceholderText(tr(item.placeholderText()))
        if isinstance(item, QTabWidget):
            for i in range(item.count()):
                item.setTabText(i, tr(item.tabText(i)))
        if isinstance(item, QComboBox):
            for i in range(item.count()):
                text = item.itemText(i)
                zh = tr(text)
                if zh != text:
                    item.setItemText(i, zh)


def install() -> None:
    """Turn the Chinese interface on (once). Safe to call more than once."""
    global _INSTALLED
    if _INSTALLED or not language():
        return
    _INSTALLED = True
    try:
        _qt_translations()
        _patch_widgets()
        _keep_filter().install()
    except Exception as exc:  # noqa: BLE001 - never keep KiPI from starting
        print(f"KiPI: Chinese interface could not be installed: {exc}", file=sys.stderr)


def uninstall_for_tests() -> None:
    """Forget what was installed (tests only)."""
    global _INSTALLED, _SEEN
    _INSTALLED = False
    _SEEN = weakref.WeakSet()
