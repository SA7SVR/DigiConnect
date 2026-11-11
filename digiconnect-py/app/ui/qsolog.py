"""QSO journal page + Log analysis window."""
from collections import Counter
from ..qt import QtWidgets as W, QtCore, Qt
from ..rules import NETS
from .widgets import *

COLS = [("callsign", "Callsign"), ("start_utc", "UTC"), ("system", "System"), ("dest", "TG / reflector / room"), ("name", "Name"), ("country", "Country"), ("grid", "Grid locator")]
PER = 50


class QsoLog(W.QWidget):
    def __init__(self, ctx, on_new_qso):
        super().__init__(); self.ctx = ctx; self.page = 0; self.trash = False; self.rows = []
        v = vbox(self, s=10)
        h = hbox(); t = vbox(s=2); title = label("QSO log"); title.setStyleSheet("font-size:24px;font-weight:700;")
        t.addWidget(title); t.addWidget(label("Your contacts, notes and recordings.", muted=True)); h.addLayout(t); h.addStretch()
        self.nq = button("New QSO", "primary", "plus"); self.an = button("Log analysis", "", "bars"); h.addWidget(self.nq); h.addWidget(self.an); v.addLayout(h)
        f = hbox(s=8); self.q = W.QLineEdit(); self.q.setPlaceholderText("Search the log…"); self.sys = W.QComboBox(); self.sys.addItems(["All networks", *NETS, "ADIF"])
        self.d1 = W.QLineEdit(); self.d1.setPlaceholderText("from yyyy-mm-dd"); self.d2 = W.QLineEdit(); self.d2.setPlaceholderText("to yyyy-mm-dd")
        self.cty = W.QLineEdit(); self.cty.setPlaceholderText("Country"); self.refresh_b = button("Refresh")
        for w in (self.q, self.sys, self.d1, self.d2, self.cty, self.refresh_b): f.addWidget(w)
        v.addLayout(f)
        a = hbox(s=8)
        self.imp = button("Import ADIF"); self.eadif = button("Export ADIF"); self.ecsv = button("Export CSV")
        self.trash_b = button("Trash", checkable=True); self.delete = button("Delete"); self.restore = button("Restore"); self.restore.setVisible(False)
        for b in (self.imp, self.eadif, self.ecsv, self.trash_b, self.delete, self.restore): a.addWidget(b)
        a.addStretch(); v.addLayout(a)
        self.table = W.QTableWidget(0, len(COLS)); self.table.setHorizontalHeaderLabels([c[1] for c in COLS])
        self.table.horizontalHeader().setStretchLastSection(True); self.table.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeMode.Stretch); v.addWidget(self.table, 1)
        self.empty = label("No QSOs logged"); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty.setStyleSheet("font-size:16px;font-weight:700;")
        v.addWidget(self.empty)
        p = hbox(); self.count = label("0 QSO · 0–0", muted=True); self.prev = button("Previous"); self.next = button("Next")
        p.addWidget(self.count); p.addStretch(); p.addWidget(self.prev); p.addWidget(self.next); v.addLayout(p)
        for w in (self.q, self.d1, self.d2, self.cty): w.textChanged.connect(self._reset)
        self.sys.currentIndexChanged.connect(self._reset); self.refresh_b.clicked.connect(self.reload)
        self.prev.clicked.connect(lambda: self._pg(-1)); self.next.clicked.connect(lambda: self._pg(1))
        self.nq.clicked.connect(on_new_qso); self.an.clicked.connect(self._analysis); self.trash_b.toggled.connect(self._trash)
        self.delete.clicked.connect(lambda: self._mark(True)); self.restore.clicked.connect(lambda: self._mark(False))
        self.eadif.clicked.connect(lambda: self._export("adif")); self.ecsv.clicked.connect(lambda: self._export("csv")); self.imp.clicked.connect(self._import)
        self.reload()

    def _reset(self): self.page = 0; self.reload()
    def _pg(self, d): self.page = max(0, self.page + d); self.reload()
    def _trash(self, on): self.trash = on; self.delete.setVisible(not on); self.restore.setVisible(on); self._reset()

    def filtered(self):
        s = self.sys.currentText()
        return self.ctx.store.search_qso(self.q.text().strip(), "" if s == "All networks" else s, self.d1.text().strip(), self.d2.text().strip(), self.cty.text().strip(), self.trash)

    def reload(self):
        self.rows = self.filtered(); total = len(self.rows); self.page = min(self.page, max(0, (total - 1) // PER))
        chunk = self.rows[self.page * PER:(self.page + 1) * PER]
        self.table.setRowCount(len(chunk))
        for i, r in enumerate(chunk):
            for j, (k, _) in enumerate(COLS):
                it = W.QTableWidgetItem(str(r.get(k) or "").replace("T", " ")); it.setData(Qt.ItemDataRole.UserRole, r["id"]); self.table.setItem(i, j, it)
        self.empty.setVisible(not chunk); self.table.setVisible(bool(chunk))
        a = self.page * PER
        self.count.setText(f"{total} QSO · {a + 1 if total else 0}–{min(total, a + PER)}")
        self.prev.setEnabled(self.page > 0); self.next.setEnabled((self.page + 1) * PER < total)

    def _ids(self):
        return sorted({self.table.item(i.row(), 0).data(Qt.ItemDataRole.UserRole) for i in self.table.selectedIndexes()})

    def _mark(self, deleted):
        ids = self._ids()
        if not ids: self.ctx.toast.emit("Select the rows you intend to " + ("remove" if deleted else "restore") + " first."); return
        self.ctx.store.set_deleted(ids, deleted); self.reload()
        self.ctx.toast.emit(f"{len(ids)} contact(s) " + ("moved to Trash" if deleted else "restored"))

    def _export(self, kind):
        rows = self.filtered()          # exports use the current filters, not only the visible page
        fn, _ = W.QFileDialog.getSaveFileName(self, "Export", f"digiconnect-log.{'adi' if kind == 'adif' else 'csv'}")
        if not fn: return
        txt = self.ctx.store.to_adif(rows, self.ctx.store.settings["callsign"]) if kind == "adif" else self.ctx.store.to_csv(rows)
        open(fn, "w", encoding="utf-8", newline="").write(txt); self.ctx.toast.emit(f"Exported {len(rows)} contact(s)")

    def _import(self):
        fn, _ = W.QFileDialog.getOpenFileName(self, "Import ADIF", "", "ADIF (*.adi *.adif *.adx)")
        if not fn: return
        txt = open(fn, encoding="utf-8", errors="replace").read(); recs = self.ctx.store.parse_adif(txt)
        if W.QMessageBox.question(self, "Import ADIF", f"{len(recs)} contact(s) found. Duplicates (same callsign, network and exact UTC time) are skipped. Import?") != W.QMessageBox.StandardButton.Yes: return
        a, s = self.ctx.store.import_adif(txt); self.reload(); self.ctx.toast.emit(f"Import finished: added {a}, skipped {s}")

    def _analysis(self):
        rows = self.filtered(); d = W.QDialog(self); d.setWindowTitle("Log analysis"); d.resize(560, 520); l = vbox(d, m=(18, 18, 18, 18), s=8)
        l.addWidget(label("Log analysis")); l.itemAt(0).widget().setStyleSheet("font-size:20px;font-weight:700;")
        l.addWidget(label(f"Contacts: {len(rows)}   ·   Stations: {len({r['callsign'] for r in rows})}   ·   Countries: {len({r['country'] for r in rows if r['country']})}"))
        def block(title, cnt, n):
            l.addWidget(label(title, section=True)); l.addWidget(label("\n".join(f"{k or '—'}: {v}" for k, v in cnt.most_common(n)) or "—", muted=True))
        block("BY NETWORK", Counter(r["system"] for r in rows), 10); block("BY DAY (UTC)", Counter((r["start_utc"] or "")[:10] for r in rows), 10)
        block("TOP COUNTRIES (20)", Counter(r["country"] for r in rows if r["country"]), 20); block("MOST WORKED STATIONS (12)", Counter(r["callsign"] for r in rows), 12)
        l.addStretch(); d.exec()
