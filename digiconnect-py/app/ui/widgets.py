from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .icons import icon


def label(text="", **props) -> W.QLabel:
    l = W.QLabel(text)
    for k, v in props.items():
        l.setProperty(k, v)
    return l


def button(text="", kind="", icon_name="", checkable=False, tip="") -> W.QPushButton:
    b = W.QPushButton(text)
    if kind: b.setProperty("kind", kind)
    if icon_name: b.setIcon(icon(icon_name)); b.setIconSize(QtCore.QSize(18, 18))
    b.setCheckable(checkable)
    if tip: b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def panel(name="panel") -> W.QFrame:
    f = W.QFrame(); f.setObjectName(name); return f


def vbox(parent=None, m=(0, 0, 0, 0), s=8) -> W.QVBoxLayout:
    l = W.QVBoxLayout(parent) if parent else W.QVBoxLayout(); l.setContentsMargins(*m); l.setSpacing(s); return l


def hbox(parent=None, m=(0, 0, 0, 0), s=8) -> W.QHBoxLayout:
    l = W.QHBoxLayout(parent) if parent else W.QHBoxLayout(); l.setContentsMargins(*m); l.setSpacing(s); return l


def repolish(w: W.QWidget):
    w.style().unpolish(w); w.style().polish(w); w.update()


def field(title: str, widget: W.QWidget) -> W.QWidget:
    box = W.QWidget(); l = vbox(box, s=4); l.addWidget(label(title, muted=True)); l.addWidget(widget); return box
