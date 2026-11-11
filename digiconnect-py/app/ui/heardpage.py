"""'Last heard' page: every station received on any network, newest first (live)."""
from ..qt import QtWidgets as W, Qt
from .widgets import label, button, panel, vbox, hbox
from ..i18n import tr


def duration(h) -> str:
    """Length of the transmission so far, '4 s'."""
    d = max(0, int((h["last"] - h["ts"]).total_seconds())) if h.get("last") else 0
    return f"{d} s"


def html_rows(rows, muted: str, limit: int = 12) -> str:
    """Structured 'last heard' block for the side column: callsign + network on the first line, destination / time / length on the second."""
    out = []
    for h in rows[:limit]:
        who = h["src"] + (f" <span style='color:{muted}'>({tr('you')})</span>" if h.get("me") else "")
        bits = [f"{h['ts']:%H:%M:%S} UTC"]
        if h["dst"]: bits.insert(0, "→ " + h["dst"])
        bits.append(duration(h))
        out.append(f"<tr><td style='padding-top:7px'><b>{who}</b></td><td align='right' style='padding-top:7px'><span style='color:{muted}'>{h['net']}</span></td></tr>"
                   f"<tr><td colspan='2' style='padding-bottom:2px'><span style='color:{muted}'>{' · '.join(bits)}</span></td></tr>")
    return "<table width='100%' cellspacing='0' cellpadding='1'>" + "".join(out) + "</table>"


class HeardPage(W.QWidget):
    COLS = ["Time (UTC)", "Callsign", "To", "Network", "Gateway", "Duration"]

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
        self.tbl.setRowCount(len(rows))
        for r, h in enumerate(rows):
            for c, val in enumerate((f"{h['ts']:%H:%M:%S}", h["src"] + ("  (you)" if h.get("me") else ""), h["dst"] or "—", h["net"], h.get("gw", "") or "—", duration(h))):
                it = W.QTableWidgetItem(tr(val) if c == 1 else val); self.tbl.setItem(r, c, it)
        self.tbl.resizeColumnsToContents(); self.tbl.horizontalHeader().setStretchLastSection(True)
