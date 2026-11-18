"""Opens a QComboBox popup for every Qt widget style on THIS machine and prints where the popup lands compared with the combo."""
import os, sys
sys.path.insert(0, os.getcwd())
from PySide6 import QtWidgets as W, QtCore as QC
from app.theme import qss
app = W.QApplication([])
print("platform:", app.platformName(), "| styles:", W.QStyleFactory.keys(), "| default:", app.style().objectName(), "| screen:", app.primaryScreen().geometry().getRect(), "dpr:", app.primaryScreen().devicePixelRatio())
bad = 0
def probe(style, mode):
    global bad
    if style: app.setStyle(style)
    extra = "" if mode == "default" else f"QComboBox {{ combobox-popup: {mode}; }}"
    app.setStyleSheet(qss(14) + extra)
    win = W.QWidget(); win.resize(760, 520); win.move(20, 20)
    h = W.QHBoxLayout(win); h.addStretch(1)
    dr = W.QFrame(); dr.setFixedWidth(300); v = W.QVBoxLayout(dr)
    sc = W.QScrollArea(); sc.setWidgetResizable(True); inner = W.QWidget(); il = W.QVBoxLayout(inner)
    for i in range(6): il.addWidget(W.QLabel("row %d" % i))
    cb = W.QComboBox(); cb.addItems(["RadioID", "QRZ.com", "QRZCQ.com", "Ham Radio Deluxe"]); il.addWidget(cb); il.addStretch(1)
    sc.setWidget(inner); v.addWidget(sc); h.addWidget(dr)
    win.show(); app.processEvents(); cb.showPopup()
    for _ in range(20): app.processEvents(); QC.QThread.msleep(20)
    g = cb.view().window().geometry(); cg = QC.QRect(cb.mapToGlobal(QC.QPoint(0, 0)), cb.size())
    ok = abs(g.x() - cg.x()) <= 40 and g.width() <= cg.width() + 80 and abs(g.y() - cg.y()) <= 200
    bad += (not ok)
    print(f"{'OK ' if ok else 'BAD'} style={app.style().objectName():14s} mode={mode:7s} combo x={cg.x()} w={cg.width()} | popup x={g.x()} y={g.y()} w={g.width()} h={g.height()}")
    cb.hidePopup(); win.close(); app.processEvents()
for st in W.QStyleFactory.keys():
    for mode in ("default", "0"):
        probe(st, mode)
print("BAD COUNT", bad)
