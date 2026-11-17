"""Recordings page: the folder where the program keeps its recordings, how many there are and how big they are, and a button to open the folder.
Recording the received audio is not in this build yet; the page shows what is already in the folder."""
from pathlib import Path
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from .widgets import label, button, vbox, hbox


def recordings_dir(ctx) -> Path:
    """Chosen in the settings (rec_dir); otherwise DigiConnect/Recordings in the user's data folder. Created when first needed."""
    d = ctx.store.settings.get("rec_dir") or str(Path.home() / "DigiConnect" / "Recordings")
    p = Path(d); p.mkdir(parents=True, exist_ok=True); return p


class RecordPage(W.QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        v = vbox(self, m=(24, 18, 24, 18), s=10)
        t = label("Recordings"); t.setStyleSheet("font-size:22px;font-weight:700;"); v.addWidget(t)
        v.addWidget(label("DigiConnect", muted=True))
        self.count = label(""); self.count.setStyleSheet("font-weight:700;"); v.addWidget(self.count)
        self.path = label(""); self.path.setWordWrap(True); self.path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); v.addWidget(self.path)
        self.list = W.QListWidget(); v.addWidget(self.list, 1)
        r = hbox(s=10); self.open_btn = button("Recordings folder", "primary", "folder"); r.addWidget(self.open_btn); r.addStretch(1)
        self.refresh_btn = button("Refresh"); r.addWidget(self.refresh_btn); v.addLayout(r)
        self.open_btn.clicked.connect(self._open); self.refresh_btn.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self):
        d = recordings_dir(self.ctx)
        files = sorted([f for f in d.iterdir() if f.is_file() and f.suffix.lower() in (".wav", ".mp3", ".ogg")], key=lambda f: f.stat().st_mtime, reverse=True)
        total = sum(f.stat().st_size for f in files)
        self.count.setText(f"{len(files)} · {total / 1048576:.1f} MB")
        self.path.setText(str(d))
        self.list.clear()
        for f in files: self.list.addItem(f"{f.name}   ({f.stat().st_size / 1024:.0f} KB)")
        if not files: self.list.addItem("No recordings yet.")

    def _open(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(recordings_dir(self.ctx))))
