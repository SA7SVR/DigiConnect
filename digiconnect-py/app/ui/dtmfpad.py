"""DTMF keypad: a small panel with the sequence display, the 12 keys (A-D on request), delete / clear, Send and Stop TX.
It sends the tones to the active connection (an AllStarLink node or an EchoLink peer)."""
from ..qt import QtWidgets as W, QtCore, Qt, Signal
from ..theme import C
from ..i18n import tr
from .widgets import *

KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#")
MAXLEN = 32


class DtmfPad(W.QFrame):
    closed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent); self.setObjectName("dtmfpad"); self.ctx = ctx; self.seq = ""; self.setFixedWidth(250)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"QFrame#dtmfpad{{background:{C['panel']};border:1px solid {C['green']};border-radius:16px;}}")
        v = vbox(self, m=(12, 10, 12, 10), s=6)
        h = hbox(); ic = W.QLabel(); ic.setPixmap(icon("grid", C["green"]).pixmap(22, 22)); h.addWidget(ic)
        t = label("DTMF keypad"); t.setStyleSheet("font-size:16px;font-weight:700;"); h.addWidget(t); h.addStretch()
        x = button("", "rail", "close"); x.setFixedSize(26, 26); x.clicked.connect(self.close_pad); h.addWidget(x); v.addLayout(h)
        self.hint = label(""); self.hint.setWordWrap(True); self.hint.setStyleSheet("font-weight:600;"); v.addWidget(self.hint)
        v.addWidget(label("DTMF sequence", muted=True))
        self.disp = label(""); self.disp.setAlignment(Qt.AlignmentFlag.AlignCenter); self.disp.setMinimumHeight(34)
        self._disp_css = f"background:{C['groove']};border-radius:10px;font-family:Consolas,Menlo,monospace;font-size:16px;font-weight:700;padding:2px 6px;"
        v.addWidget(self.disp)
        g = W.QGridLayout(); g.setSpacing(6); self.keys = {}
        for i, k in enumerate(KEYS): g.addWidget(self._key(k), i // 3, i % 3)
        v.addLayout(g)
        self.ad_toggle = W.QToolButton(); self.ad_toggle.setCheckable(True); self.ad_toggle.setText("▸ " + tr("A–D keys")); self.ad_toggle.setStyleSheet("QToolButton{border:none;background:transparent;font-weight:600;text-align:left;}")
        self.ad_toggle.setCursor(Qt.CursorShape.PointingHandCursor); self.ad_toggle.toggled.connect(self._ad); v.addWidget(self.ad_toggle)
        self.ad = W.QWidget(); ar = hbox(self.ad, s=8)
        for k in "ABCD": ar.addWidget(self._key(k))
        self.ad.setVisible(False); v.addWidget(self.ad)
        r = hbox(); self.back = button("", "", "backspace"); self.back.setFixedWidth(52); self.clear = button("Clear"); r.addWidget(self.back); r.addStretch(); r.addWidget(self.clear); v.addLayout(r)
        r = hbox(s=10); self.send = button("Send", "primary", "wave"); self.stop = button("Stop TX", "danger", "stop"); self.send.setFixedHeight(34); self.stop.setFixedHeight(34)
        r.addWidget(self.send, 3); r.addWidget(self.stop, 2); v.addLayout(r)
        self.status = label(""); self.status.setWordWrap(True); self.status.setStyleSheet("font-weight:600;"); v.addWidget(self.status)
        self.note = label("Audio tones to the active connection. Use the repeater codes; execution depends on its configuration.", muted=True); self.note.setWordWrap(True); v.addWidget(self.note)
        self.back.clicked.connect(lambda: self._set(self.seq[:-1])); self.clear.clicked.connect(lambda: self._set(""))
        self.send.clicked.connect(self._send); self.stop.clicked.connect(self.ctx.stop_tx)
        ctx.changed.connect(self.refresh); self.refresh()

    def _key(self, k):
        b = W.QPushButton(k); b.setFixedHeight(38); b.setCursor(Qt.CursorShape.PointingHandCursor); b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setStyleSheet(f"QPushButton{{background:{C['panel2']};border:1px solid {C['groove']};border-radius:14px;font-size:16px;font-weight:700;}}QPushButton:hover{{border-color:{C['accent']};}}QPushButton:pressed{{background:{C['sel']};}}")
        b.clicked.connect(lambda _=False, k=k: self.press(k)); self.keys[k] = b; return b

    def _ad(self, on): self.ad.setVisible(on); self.ad_toggle.setText(("▾ " if on else "▸ ") + tr("A–D keys"))

    def press(self, k):
        if len(self.seq) < MAXLEN: self._set(self.seq + k)

    def _set(self, s): self.seq = s; self.refresh()

    def target(self): return self.ctx.dtmf_peer()

    def refresh(self):
        t = self.target()
        self.disp.setText(self.seq or "0-9  ·  *  ·  #"); self.disp.setStyleSheet(self._disp_css + ("" if self.seq else f"color:{C['muted']};"))
        self.hint.setText((tr("Sending to {} {}").format(t.net, t.name or t.id)) if t else tr("Choose an EchoLink or AllStarLink connection."))
        self.send.setEnabled(t is not None and bool(self.seq)); self.stop.setEnabled(bool(self.ctx.rules.ptt)); self.back.setEnabled(bool(self.seq)); self.clear.setEnabled(bool(self.seq))

    def _send(self):
        t = self.target()
        if t is None or not self.seq: return
        if self.ctx.send_dtmf(self.seq, t): self._set("")

    def keyPressEvent(self, e):
        k = e.text().upper()
        if k and k in "0123456789ABCD*#" and len(k) == 1: self.press(k)
        elif e.key() == Qt.Key.Key_Backspace: self._set(self.seq[:-1])
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self._send()
        elif e.key() == Qt.Key.Key_Escape: self.close_pad()
        else: super().keyPressEvent(e)

    def close_pad(self): self.hide(); self.closed.emit()
