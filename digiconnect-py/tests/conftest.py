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
