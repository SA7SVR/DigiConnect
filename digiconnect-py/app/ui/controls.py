"""Operating controls driven by Ctx: TxControls (workspace column), Dock (bottom bar), Mixer."""
from ..qt import QtWidgets as W, QtCore, Qt, Signal
from ..rules import NETS, ListenMode
from ..theme import NET_COLOR, C
from .widgets import *
from .knob import MicKnob


def _mmss(s): return f"{s // 60:02d}:{s % 60:02d}"


class _Sync:
    """Shared behaviour: wire PTT buttons and keep them in sync with ctx."""
    def _wire(self, ctx, hold, latch, limit, countdown):
        self.ctx, self.hold, self.latch, self.limit, self.countdown = ctx, hold, latch, limit, countdown
        hold.pressed.connect(lambda: ctx.ptt_down(False)); hold.released.connect(ctx.ptt_up)
        latch.clicked.connect(lambda: ctx.ptt_down(True))
        limit.addItems(["60 s", "120 s", "180 s"]); limit.setCurrentText(f"{ctx.rules.limit} s")
        limit.currentTextChanged.connect(lambda t: ctx.set_limit(int(t.split()[0])))

    def _sync_ptt(self):
        r = self.ctx.rules
        self.hold.setEnabled(r.ptt_available); self.latch.setEnabled(r.ptt_available)
        self.latch.setText("Stop TX" if r.ptt and r.latched else "Latch PTT")
        self.limit.setEnabled(not r.ptt)
        if self.limit.currentText() != f"{r.limit} s" and not r.ptt: self.limit.setCurrentText(f"{r.limit} s")
        self.countdown.setText(_mmss(r.remaining if r.ptt else r.limit))
        self.countdown.setStyleSheet(f"color:{C['red'] if r.countdown_red else C['text']}; font-weight:700; font-size:16px;")


class TxControls(W.QWidget, _Sync):
    """Middle-column block: status, Connect (TX), Stop all, Hold/Latch PTT, Limit, Record, New QSO."""
    def __init__(self, ctx, on_new_qso):
        super().__init__()
        self.ctx = ctx
        l = vbox(self, s=10)
        self.status = label("Listening stopped", tone="echo")
        self.listen = button("Listen", "primary", "headphones"); self.connect = button("Connect (TX)", "primary", "power")
        self.stopall = button("Stop all", "danger")
        self.listen.setToolTip("Connect to the selected server and listen (reception only)"); self.connect.setToolTip("Connect your transmit link to the selected server so you can use PTT")
        row = FlowLayout(hspace=8, vspace=6); row.addWidget(self.listen); row.addWidget(self.connect); row.addWidget(self.stopall)
        self.hold = button("Hold PTT", "ptt", "mic"); self.latch = button("Latch PTT", "latch", "lock")
        pr = hbox(s=10); pr.addWidget(self.hold, 3); pr.addWidget(self.latch, 2)
        self.knob = MicKnob(ctx, 84); pr.addWidget(self.knob, 0, Qt.AlignmentFlag.AlignVCenter)
        self.limit = W.QComboBox(); self.limit.setFixedSize(84, 30); self.limit.setStyleSheet("padding:2px 8px;"); self.countdown = label("02:00")
        self.dest = label("No TX destination", muted=True)
        lr = hbox(); lr.addWidget(label("Limit", muted=True)); lr.addWidget(self.limit); lr.addStretch(); lr.addWidget(self.countdown)
        self.rec = button("Record audio", "", "circle"); self.nq = button("New QSO", "", "plus")
        rr = FlowLayout(hspace=8, vspace=6); rr.addWidget(self.rec); rr.addWidget(self.nq)
        self.txstate = label("Transmit disconnected", muted=True); self.stats = label("RX — · lost — · TX —", muted=True)
        for x in (self.status,): l.addWidget(x)
        l.addLayout(row); l.addLayout(pr); l.addLayout(lr); l.addWidget(self.dest); l.addLayout(rr); l.addWidget(self.txstate); l.addWidget(self.stats)
        self._wire(ctx, self.hold, self.latch, self.limit, self.countdown)
        self.listen.clicked.connect(ctx.toggle_listen); self.connect.clicked.connect(ctx.toggle_tx)
        self.stopall.clicked.connect(ctx.stop_all); self.nq.clicked.connect(on_new_qso)
        self.rec.clicked.connect(lambda: ctx.toast.emit("Audio recording needs a running receiver (engine step)"))
        ctx.changed.connect(self.refresh); self.refresh()

    def refresh(self):
        c, r = self.ctx, self.ctx.rules
        sel = c.selected
        self.status.setText(c.status_text()); self.txstate.setText(c.tx_text()); self.dest.setText(c.tx_target_text())
        self.listen.setEnabled(sel is not None); self.connect.setEnabled(sel is not None and not r.ptt)
        self.listen.setText("Stop listening" if sel and r.is_listening(sel) else "Listen")
        self.connect.setText("Disconnect" if r.tx_connected else "Connect (TX)")
        self._sync_ptt()


class Dock(W.QFrame, _Sync):
    """Bottom station dock shown on pages other than the workspace."""
    def __init__(self, ctx, on_go_workspace):
        super().__init__(); self.setObjectName("dock"); self.ctx = ctx
        self.setFixedHeight(128)
        l = hbox(self, m=(18, 8, 14, 8), s=12)
        info = vbox(s=2)
        info.addWidget(label("Selected station", muted=True))
        self.name = label("No station selected"); self.name.setStyleSheet("font-size:16px;font-weight:700;")
        self.txstate = label("Transmit disconnected", muted=True); self.status = label("Listening stopped", tone="echo")
        info.addWidget(self.name); info.addWidget(self.txstate); info.addWidget(self.status)
        self.dest = label("", muted=True); info.addWidget(self.dest)
        l.addLayout(info, 1)
        self.knob = MicKnob(ctx, 62); l.addWidget(self.knob)
        self.listen = button("Listen", "", "headphones"); self.connect = button("Connect (TX)", "primary", "power")
        self.rec = button("Record audio", "", "circle")
        l.addWidget(self.listen); l.addWidget(self.connect); l.addWidget(self.rec)
        self.hold = button("Hold PTT", "ptt", "mic"); self.latch = button("Latch PTT", "latch", "lock")
        self.limit = W.QComboBox(); self.limit.setFixedSize(84, 30); self.limit.setStyleSheet("padding:2px 8px;"); self.countdown = label("02:00")
        col = vbox(s=3); pr = hbox(s=6); pr.addWidget(self.hold); pr.addWidget(self.latch); self.hold.setMinimumHeight(34); self.latch.setMinimumHeight(34)
        lr = hbox(); lr.addWidget(label("Limit", muted=True)); lr.addWidget(self.limit); lr.addStretch(); lr.addWidget(self.countdown)
        col.addLayout(pr); col.addLayout(lr); l.addLayout(col)
        self.stop = button("", "danger", "close"); self.stop.setFixedSize(42, 42); self.stop.setToolTip("Stop all"); l.addWidget(self.stop)
        self._wire(ctx, self.hold, self.latch, self.limit, self.countdown)
        self.listen.clicked.connect(ctx.toggle_listen); self.connect.clicked.connect(ctx.toggle_tx); self.stop.clicked.connect(ctx.stop_all)
        self.rec.clicked.connect(lambda: ctx.toast.emit("Audio recording needs a running receiver (engine step)"))
        ctx.changed.connect(self.refresh); self.refresh()

    def refresh(self):
        c, r = self.ctx, self.ctx.rules; sel = c.selected
        self.name.setText(sel.name if sel else "No station selected")
        self.status.setText(c.status_text()); self.txstate.setText(c.tx_text()); self.dest.setText(c.tx_target_text())
        self.listen.setEnabled(sel is not None); self.connect.setEnabled(sel is not None and not r.ptt)
        self.listen.setText("Stop" if sel and r.is_listening(sel) else "Listen")
        self.connect.setText("Disconnect" if r.tx_connected else "Connect (TX)")
        self._sync_ptt()


class Mixer(W.QFrame):
    """Horizontal audio mixer: Single/Multiple, Hide, per-network volume+mute, per-DMR-receiver sliders."""
    hide_requested = Signal()

    def __init__(self, ctx):
        super().__init__(); self.setObjectName("mixer"); self.ctx = ctx
        l = vbox(self, m=(18, 10, 18, 8), s=6)
        top = hbox(); top.addWidget(label("Audio mixer", **{"h": "1"})); top.addStretch()
        self.single = button("Single listening", "seg", checkable=True); self.multi = button("Multiple listening", "seg", checkable=True)
        self.hidebtn = button("Hide  ✕", "")
        for b in (self.single, self.multi, self.hidebtn): top.addWidget(b)
        l.addLayout(top)
        strips = W.QGridLayout(); strips.setSpacing(10); self.sliders, self.mutes, self.caption = {}, {}, {}
        for i, n in enumerate(NETS):
            f = panel("card"); v = vbox(f, m=(12, 8, 12, 8), s=4)
            h = hbox(); nm = label(n, net=n); cap = label("RX volume", muted=True)
            mute = button("", "", "speaker", checkable=True); mute.setFixedSize(32, 28)
            h.addWidget(nm); h.addStretch(); h.addWidget(cap); h.addStretch(); h.addWidget(mute)
            s = W.QSlider(Qt.Orientation.Horizontal); s.setRange(0, 100); s.setValue(int(ctx.rules.net_volume[n] * 100))
            v.addLayout(h); v.addWidget(s); strips.addWidget(f, i // 4, i % 4); strips.setColumnStretch(i % 4, 1)
            s.valueChanged.connect(lambda val, n=n: self._vol(n, val)); mute.toggled.connect(lambda m, n=n: self._mute(n, m))
            self.sliders[n], self.mutes[n], self.caption[n] = s, mute, cap
        l.addLayout(strips)
        l.addWidget(label("Up to 4 DMR TGs + 1 receiver on every other network. A click adds a receiver; on the same non-DMR network it replaces the previous one.", muted=True))
        self.single.clicked.connect(lambda: ctx.set_mode(ListenMode.SINGLE)); self.multi.clicked.connect(lambda: ctx.set_mode(ListenMode.MULTIPLE))
        self.hidebtn.clicked.connect(self.hide_requested.emit)
        ctx.changed.connect(self.refresh); self.refresh()

    def _vol(self, n, v): self.ctx.rules.net_volume[n] = v / 100; self.refresh_caption()
    def _mute(self, n, m): self.ctx.rules.net_muted[n] = m; self._mute_look(n); self.refresh_caption(); self.ctx.changed.emit()

    def _mute_look(self, n):
        """The speaker button shows the state: open speaker with waves = sound on, red crossed speaker = muted."""
        b = self.mutes[n]; off = self.ctx.rules.net_muted[n]; name = "speaker_off" if off else "speaker"
        b.setProperty("icon_name", name); b.setIcon(icon(name))
        b.setToolTip("Muted - click to turn the sound on" if off else "Sound on - click to mute")

    def refresh_caption(self):
        for n in NETS: self.caption[n].setText("Reception muted" if self.ctx.rules.net_muted[n] else "RX volume")

    def refresh(self):
        m = self.ctx.rules.mode
        self.single.setChecked(m is ListenMode.SINGLE); self.multi.setChecked(m is ListenMode.MULTIPLE); self.refresh_caption()
        for n in NETS:                                   # keep the buttons in step with the rules (e.g. F4 = mute all)
            b = self.mutes[n]; b.blockSignals(True); b.setChecked(bool(self.ctx.rules.net_muted[n])); b.blockSignals(False); self._mute_look(n)
