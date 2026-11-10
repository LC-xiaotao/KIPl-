"""Build KiPI.exe, the Windows quick-start launcher, with PyInstaller.

    python tools/build_windows_exe.py

The exe is written to ``dist/KiPI.exe`` and copied to the KiPI folder as ``KiPI.exe``,
beside ``kipi_launcher.pyw``. It is a small bootstrap, not a frozen copy of KiPI: it
starts the launcher with KiPI's own environment, so the solvers, Qt and VTK stay in the
environment KiPI already installed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        import PyInstaller  # noqa: F401 - only checks that the build tool is installed
    except ImportError:
        print("PyInstaller is not installed. Run: python -m pip install pyinstaller",
              file=sys.stderr)
        return 1
    icon = ROOT / "resources" / "kipi.ico"
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "KiPI",
    ]
    if icon.is_file():
        command += ["--icon", str(icon)]
    command += [
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"),
        str(ROOT / "tools" / "kipi_shortcut.py"),
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    name = "KiPI.exe" if sys.platform == "win32" else "KiPI"
    built = ROOT / "dist" / name
    if not built.is_file():
        print(f"PyInstaller did not write {built}", file=sys.stderr)
        return 1
    if sys.platform == "win32":
        shutil.copy2(built, ROOT / name)
        print(f"Copied to {ROOT / name}")
    print(f"Built {built} ({built.stat().st_size / (1024 * 1024):.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
