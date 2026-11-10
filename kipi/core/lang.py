"""Which language KiPI's reports are written in: Chinese or English.

The reports (:mod:`kipi.core.report_i18n`) ask here; the GUI (:mod:`kipi.gui.i18n`) reads
the same ``KIPI_LANG`` and system locale, so a report comes out in the window's language.
``KIPI_LANG=en`` forces English, ``KIPI_LANG=zh_CN`` (or any ``zh…``) Chinese; otherwise
the system's locale decides, and Chinese is the default when it cannot be read.
"""

from __future__ import annotations

import os
from typing import Optional

_SYSTEM: Optional[bool] = None      # the system locale's answer, read once


def chinese() -> bool:
    """Whether KiPI speaks Chinese. ``KIPI_LANG`` is read on every call (it is cheap, and
    a change to it then always counts); then the language chosen in KiPI's menu; only the
    system locale is remembered."""
    global _SYSTEM
    choice = os.environ.get("KIPI_LANG", "").strip().lower()
    if choice in ("en", "english", "en_us", "en-us", "en_gb", "en-gb"):
        return False
    if choice.startswith("zh"):
        return True
    try:
        from qtpy.QtCore import QSettings
        saved = str(QSettings("KiPI", "KiPI").value("ui/language", "system") or "system")
        saved = saved.strip().lower()
        if saved.startswith("zh"):
            return True
        if saved in ("en", "english", "en_us", "en-us", "en_gb", "en-gb"):
            return False
    except Exception:  # noqa: BLE001 - no Qt, or no settings: fall back to the system
        pass
    if _SYSTEM is None:
        try:
            from qtpy.QtCore import QLocale
            _SYSTEM = QLocale.system().name().lower().startswith("zh")
        except Exception:  # noqa: BLE001 - no Qt yet: Chinese is this build's default
            _SYSTEM = True
    return _SYSTEM


def reset() -> None:
    """Read the system locale again on the next call (tests)."""
    global _SYSTEM
    _SYSTEM = None
