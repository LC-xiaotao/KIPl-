"""Only one KiPI runs at a time; a second one brings the first to the front."""

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytest.importorskip("qtpy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import QApplication  # noqa: E402

from kipi.gui import single_instance as si  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """A lock and socket of this test's own, so a KiPI the developer has open is untouched."""
    name = f"kipi-test-{os.getpid()}-{tmp_path.name}"
    monkeypatch.setattr(si, "server_name", lambda: name)
    monkeypatch.setattr(si, "lock_path", lambda: tmp_path / "kipi.lock")
    return name


def test_second_instance_finds_the_lock_taken(isolated):
    first = si.acquire()
    assert first is not None and first.locked
    assert si.acquire() is None
    assert si.running_pid() == os.getpid()
    first.release()
    again = si.acquire()
    assert again is not None and again.locked
    again.release()


def test_a_dead_owner_does_not_lock_the_next_kipi_out(isolated, tmp_path):
    # A KiPI that crashed: its lock file names a process that no longer exists.
    p = subprocess.run([sys.executable, "-c", textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, ".")
        from kipi.gui import single_instance as si
        g = si.acquire(__import__("pathlib").Path(r"{tmp_path / 'kipi.lock'}"))
        assert g is not None and g.locked
        os._exit(0)                       # never unlocks
    """)], cwd=ROOT, env=dict(os.environ, QT_API="pyside6"), timeout=60)
    assert p.returncode == 0 and (tmp_path / "kipi.lock").exists()
    g = si.acquire()
    assert g is not None and g.locked
    g.release()


def test_an_unwritable_lock_still_lets_kipi_start(monkeypatch, tmp_path):
    g = si.acquire(tmp_path / "no such folder" / "kipi.lock")
    assert g is not None and not g.locked
    assert g.listen(lambda: None) is False
    g.release()


def test_second_instance_brings_the_first_to_the_front(app, isolated):
    first = si.acquire()
    activated = []
    assert first.listen(lambda: activated.append(True))
    # The second KiPI is another process, as it is when KiCad starts it again.
    child = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import logging, sys
        sys.path.insert(0, ".")
        logging.basicConfig(level=logging.INFO)   # says why, if the handoff fails
        from kipi.gui import single_instance as si
        si.server_name = lambda: "{isolated}"
        sys.exit(0 if si.activate_running(timeout_ms=10000) else 3)
    """)], cwd=ROOT, env=dict(os.environ, QT_API="pyside6"))
    deadline = time.monotonic() + 60
    while child.poll() is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    first.release()
    assert child.returncode == 0 and activated == [True]


def test_activation_fails_cleanly_with_nobody_listening(app, isolated):
    assert si.activate_running(timeout_ms=500) is False


@pytest.mark.parametrize("has_splash", [True, False])
def test_repeated_launch_during_preload_then_after_window_opens(app, monkeypatch, has_splash):
    from types import SimpleNamespace
    from kipi.gui import app as gui_app, identity

    splash = object() if has_splash else None
    window = object()
    activated = []
    callbacks = []
    released = []
    monkeypatch.setattr(si, "bring_to_front", activated.append)
    monkeypatch.setattr(identity, "tag_window", lambda win: None)
    monkeypatch.setattr(gui_app, "set_status", lambda *args: None)
    monkeypatch.setitem(sys.modules, "kipi.gui.main_window",
                        SimpleNamespace(MainWindow=lambda **kwargs: window))

    def preload(_splash):
        # The second click must already have a listener while cold imports run.
        assert len(callbacks) == 1
        callbacks[0]()
        assert activated == ([splash] if has_splash else [])

    def event_loop():
        callbacks[0]()
        assert activated[-1] is window
        return 0

    monkeypatch.setattr(gui_app, "preload", preload)
    monkeypatch.setattr(identity, "make_app", lambda: SimpleNamespace(exec=event_loop))
    guard = SimpleNamespace(listen=callbacks.append, release=lambda: released.append(True))
    # A minimal splash exercises activation without starting its animation timer.
    if has_splash:
        class Welcome:
            def isVisible(self):
                return False
        splash = Welcome()
    assert gui_app.run(instance=guard, splash=splash) == 0
    assert len(callbacks) == 1 and released == [True]
