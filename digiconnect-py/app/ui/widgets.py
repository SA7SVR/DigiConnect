from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .icons import icon
from .. import i18n
from ..i18n import tr

i18n.install()


def label(text="", **props) -> W.QLabel:
    l = W.QLabel(); l.setText(text)
    for k, v in props.items():
        l.setProperty(k, v)
    return l


def button(text="", kind="", icon_name="", checkable=False, tip="") -> W.QPushButton:
    b = W.QPushButton(); b.setText(text)
    if kind: b.setProperty("kind", kind)
    if icon_name: b.setIcon(icon(icon_name)); b.setIconSize(QtCore.QSize(18, 18)); b.setProperty("icon_name", icon_name)
    b.setCheckable(checkable)
    if tip: b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def repaint_icons():
    """After a theme change: redraw every icon that was made with icon(name) in the new colour."""
    for w in W.QApplication.allWidgets():
        n = w.property("icon_name") if isinstance(w, W.QAbstractButton) else None
        if n: w.setIcon(icon(n))


def checkbox(text="") -> W.QCheckBox:
    c = W.QCheckBox(); c.setText(text); return c


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


class FlowLayout(W.QLayout):
    """Lays widgets out left-to-right and wraps to the next row when the width runs out (no overlap on small windows)."""
    def __init__(self, parent=None, hspace=8, vspace=8):
        super().__init__(parent); self._items = []; self._h = hspace; self._v = vspace
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QtCore.QRect(0, 0, w, 0), True)
    def setGeometry(self, r): super().setGeometry(r); self._do(r, False)
    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        s = QtCore.QSize()
        for it in self._items: s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins(); return s + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        m = self.contentsMargins(); r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, row_h = r.x(), r.y(), 0
        for it in self._items:
            if it.widget() is not None and not it.widget().isVisibleTo(it.widget().parentWidget()): continue
            sz = it.sizeHint()
            if x + sz.width() > r.right() + 1 and row_h > 0:
                x = r.x(); y += row_h + self._v; row_h = 0
            if not test: it.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), sz))
            x += sz.width() + self._h; row_h = max(row_h, sz.height())
        return y + row_h - rect.y() + m.bottom()
