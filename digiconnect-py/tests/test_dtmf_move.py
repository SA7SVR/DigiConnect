"""The DTMF keypad can be dragged to any place of the window (it used to stay where it opened) and stays there when opened again."""
import os, sys, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.qt import QtWidgets as W, QtCore, QtGui, Qt
from app.store import Store
from app.context import Ctx
from app.ui.main_window import MainWindow


def _ev(w, t, x, y, btn=Qt.MouseButton.LeftButton, down=True):
    pt = QtCore.QPointF(x, y); gp = w.mapToGlobal(pt)                          # a move has no "changed" button, but the left button is held down
    W.QApplication.sendEvent(w, QtGui.QMouseEvent(t, pt, gp, btn, Qt.MouseButton.LeftButton if down else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))


def _drag(w, x0, y0, x1, y1):
    E = QtCore.QEvent.Type
    _ev(w, E.MouseButtonPress, x0, y0); _ev(w, E.MouseMove, (x0 + x1) / 2, (y0 + y1) / 2, Qt.MouseButton.NoButton); _ev(w, E.MouseMove, x1, y1, Qt.MouseButton.NoButton)
    _ev(w, E.MouseButtonRelease, x1, y1, down=False)


def _open(tmp_path):
    app = W.QApplication.instance() or W.QApplication([])
    w = MainWindow(Ctx(Store(tmp_path))); w.resize(1280, 800); w.show(); app.processEvents()
    fav = w.favs
    fav._dtmf(); app.processEvents()
    return w, fav, fav.pad, app


def test_keypad_is_dragged_by_its_title_and_any_empty_place(tmp_path):
    w, fav, pad, app = _open(tmp_path)
    assert pad.isVisible() and not pad.moved
    p0 = pad.pos()
    _drag(pad, 40, 22, 40 - 150, 22 + 120)                                   # by the title row
    assert pad.moved and pad.pos() == p0 + QtCore.QPoint(-150, 120) or pad.x() == 0 or pad.y() == w.height() - pad.height(), (p0, pad.pos())
    p1 = pad.pos(); assert p1 != p0
    _drag(pad.note, 5, 5, 35, -5); assert pad.pos() != p1                    # by the text at the bottom (a label passes the mouse on to the keypad)
    _drag(pad.disp, 5, 5, -20, 5); assert pad.moved


def test_keypad_stays_inside_the_window(tmp_path):
    w, fav, pad, app = _open(tmp_path)
    _drag(pad, 40, 22, -5000, -5000); assert pad.pos() == QtCore.QPoint(0, 0)
    _drag(pad, 40, 22, 9000, 9000); assert pad.x() == w.width() - pad.width() and pad.y() == w.height() - pad.height()


def test_keys_still_click_and_do_not_drag(tmp_path):
    w, fav, pad, app = _open(tmp_path)
    p0 = pad.pos(); pad.keys["5"].click(); pad.keys["#"].click(); assert pad.seq == "5#" and pad.pos() == p0 and not pad.moved
    _drag(pad.keys["1"], 5, 5, 85, 85)                                       # a drag that starts on a key is the key's business, not a move
    assert pad.pos() == p0 and not pad.moved


def test_keypad_opens_where_the_user_left_it(tmp_path):
    w, fav, pad, app = _open(tmp_path)
    _drag(pad, 40, 22, 40 - 200, 22 + 150); where = pad.pos()
    fav._dtmf(); app.processEvents(); assert not pad.isVisible()             # second press closes it
    fav._dtmf(); app.processEvents(); assert pad.isVisible() and pad.pos() == where
