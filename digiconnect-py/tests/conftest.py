"""One QApplication for the whole test run, created before any test and kept until the interpreter exits.
(A test that creates it as a local variable would delete it when the test ends, and Qt objects of later tests would crash at exit.)"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.qt import QtWidgets

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
