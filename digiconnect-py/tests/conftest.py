"""One QApplication for the whole test run, created before any test and kept until the interpreter exits.
(A test that creates it as a local variable would delete it when the test ends, and Qt objects of later tests would crash at exit.)"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.qt import QtWidgets

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


import pytest


@pytest.fixture(autouse=True)
def no_background_downloads(monkeypatch):
    """The UI starts list downloads in background threads (real network). A thread still running when the tests end emits a Qt signal on an
    object that is already gone and the interpreter aborts at exit (seen on macOS / Windows CI after all tests had passed). Tests never need them."""
    from app.context import Ctx
    monkeypatch.setattr(Ctx, "refresh_hosts", lambda self, force=False: None)
    monkeypatch.setattr(Ctx, "refresh_asl", lambda self, force=False: None)


_STATUS = [0]


def pytest_sessionfinish(session, exitstatus):
    _STATUS[0] = int(exitstatus)


def pytest_unconfigure(config):
    """Qt/PySide objects of finished tests are destroyed in an unpredictable order when the interpreter shuts down; on CI that crashed
    (segfault / abort, "shared QObject was deleted directly") AFTER every test had passed. Leave right after pytest has printed its result:
    the result and the exit status are the test run's own, nothing of the program is skipped."""
    import sys
    try: sys.stdout.flush(); sys.stderr.flush()
    except Exception: pass
    if sys.platform == "win32":          # os._exit() still runs the DLL shutdown of Qt on Windows (access violation there): end the process directly
        import ctypes
        ctypes.windll.kernel32.TerminateProcess(ctypes.windll.kernel32.GetCurrentProcess(), _STATUS[0])
    os._exit(_STATUS[0])
