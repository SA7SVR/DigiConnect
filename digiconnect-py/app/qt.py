"""Qt binding shim: PySide6 (default) or PyQt6. Use scoped enums everywhere."""
try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork
    Signal = QtCore.Signal
    BINDING = "PySide6"
except ImportError:  # pragma: no cover
    from PyQt6 import QtCore, QtGui, QtWidgets, QtNetwork
    Signal = QtCore.pyqtSignal
    BINDING = "PyQt6"
Qt = QtCore.Qt
