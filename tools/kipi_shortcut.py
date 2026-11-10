"""Small Windows quick-start exe for KiPI.

Double-clicking it starts ``kipi_launcher.pyw`` with KiPI's own environment (or a system
Python on the first run), passing any arguments through, so a board file dropped on the
exe opens it. The exe must sit in the KiPI folder next to ``kipi_launcher.pyw``; set
``KIPI_ROOT`` when it lives elsewhere.

Build it with ``python tools/build_windows_exe.py``.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP = "KiPI"
LAUNCHER = "kipi_launcher.pyw" if os.name == "nt" else "kipi_launcher.py"


def _root() -> Path:
    """The KiPI folder: beside the exe, KIPI_ROOT, or the current directory."""
    if getattr(sys, "frozen", False):
        candidates = [Path(sys.executable).resolve().parent]
    else:
        candidates = [Path(__file__).resolve().parents[1]]
    env = os.environ.get("KIPI_ROOT")
    if env:
        candidates.insert(0, Path(env))
    candidates.append(Path.cwd())
    for candidate in candidates:
        if (candidate / LAUNCHER).is_file():
            return candidate
    return candidates[0]


def _data_dir() -> Path:
    env = os.environ.get("KIPI_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "KiPI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "KiPI"
    return (Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
            / "kipi")


def _python() -> Path | None:
    """KiPI's environment Python, else a system Python for the first setup."""
    names = ("pythonw.exe", "python.exe") if os.name == "nt" else ("python", "python3")
    folder = _data_dir() / "venv" / ("Scripts" if os.name == "nt" else "bin")
    for name in names:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def _say(text: str) -> None:
    try:
        print(text)
    except Exception:          # no console in the windowed exe
        pass


def _error(text: str) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, text, APP, 0x10)  # MB_ICONERROR
            return
        except Exception:      # no user32 (unlikely on Windows)
            pass
    _say(text)


def main(argv: list[str]) -> int:
    root = _root()
    launcher = root / LAUNCHER
    python = _python()
    if "--check" in argv[1:]:
        lines = [f"KiPI folder: {root}",
                 f"Launcher: {launcher} ({'ok' if launcher.is_file() else 'missing'})",
                 f"Python: {python or 'not found'}"]
        _say("\n".join(lines))
        try:
            (Path(tempfile.gettempdir()) / "kipi-shortcut-check.txt").write_text(
                "\n".join(lines), encoding="utf-8")
        except OSError:
            pass
        return 0 if launcher.is_file() and python is not None else 2
    if not launcher.is_file():
        _error("找不到 kipi_launcher.pyw。\n\n请把 KiPI.exe 放在 KiPI 文件夹中"
               "（与 kipi_launcher.pyw 同一目录），或设置 KIPI_ROOT 指向该文件夹。")
        return 2
    if python is None:
        _error("找不到 Python。\n\n请先安装 Python 3.10–3.13，再双击 KiPI.exe；"
               "首次启动会创建 KiPI 的运行环境。")
        return 2
    args = [str(python), str(launcher)] + [a for a in argv[1:] if a != "--check"]
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(args, cwd=str(root), close_fds=True, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as exc:
        _error(f"无法启动 KiPI：{exc}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
