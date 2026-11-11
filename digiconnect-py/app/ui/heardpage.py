"""'Last heard' page: every station received on any network, newest first (live)."""
from ..qt import QtWidgets as W, Qt
from .widgets import label, button, panel, vbox, hbox
from ..i18n import tr


class HeardPage(W.QWidget):
    COLS = ["Time (UTC)", "Callsign", "To", "Network", "Gateway"]

    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        v = vbox(self, s=10)
        top = hbox(); t = label("Last heard"); t.setStyleSheet("font-size:22px;font-weight:700;"); top.addWidget(t); top.addStretch()
        self.clear = button("Clear list"); top.addWidget(self.clear); v.addLayout(top)
        self.note = label("Every station received on the links you are listening to appears here as it is heard.", muted=True); self.note.setWordWrap(True); v.addWidget(self.note)
        self.tbl = W.QTableWidget(0, len(self.COLS)); self.tbl.setHorizontalHeaderLabels([tr(c) for c in self.COLS])
        self.tbl.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers); self.tbl.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False); self.tbl.horizontalHeader().setStretchLastSection(True); self.tbl.setAlternatingRowColors(False)
        v.addWidget(self.tbl, 1)
        self.clear.clicked.connect(self._clear); ctx.changed.connect(self.reload); self.reload()

    def retranslate(self): self.tbl.setHorizontalHeaderLabels([tr(c) for c in self.COLS])

    def _clear(self): self.ctx.last_heard.clear(); self.reload()

    def reload(self):
        rows = self.ctx.last_heard
        if self.tbl.rowCount() == len(rows) and rows and self.tbl.item(0, 1) and self.tbl.item(0, 1).text() == rows[0]["src"] and self.tbl.item(0, 0).text() == f"{rows[0]['ts']:%H:%M:%S}": return
        self.tbl.setRowCount(len(rows))
        for r, h in enumerate(rows):
            for c, val in enumerate((f"{h['ts']:%H:%M:%S}", h["src"], h["dst"] or h["target"], h["net"], h.get("gw", ""))):
                self.tbl.setItem(r, c, W.QTableWidgetItem(val))
