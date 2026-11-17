"""Microphone page: input gain, 3-band equaliser, high-pass filter, noise gate, compressor and output level.
Every change is sent to the protocol engine at once, so a hold-to-talk press on this page lets you hear the effect on the
other station's receiver. The values are kept per computer (settings['mic'])."""
import math
from ..qt import QtWidgets as W, QtCore, Qt
from .widgets import label, button, vbox, hbox
from ..i18n import tr

DEFAULT = dict(gain=0, bass=0, mid=0, treble=0, highpass=0, gate=-60, comp=0, out=100)
HP_CHOICES = [("Off", 0), ("80 Hz", 80), ("120 Hz", 120), ("200 Hz", 200)]
H = 350   # both panels share this height: the sliders run from the top to the bottom of the waveform box


class Wave(W.QFrame):
    """Box that draws the microphone waveform: a line of samples in -1..1, newest on the right. Empty until the engine sends samples."""
    def __init__(self):
        super().__init__(); self.setObjectName("wave"); self.setMinimumSize(300, 300); self.samples: list = []
    def set_samples(self, xs):
        self.samples = list(xs)[-400:]; self.update()
    def paintEvent(self, ev):
        from ..qt import QtGui
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height(); mid = h / 2
        p.fillRect(self.rect(), QtGui.QColor("#0d1b33"))
        p.setPen(QtGui.QPen(QtGui.QColor("#2c4575"), 1)); p.drawLine(0, int(mid), w, int(mid))
        p.setPen(QtGui.QPen(QtGui.QColor("#5ad39a"), 1))
        xs = self.samples
        if xs:
            step = w / max(1, len(xs) - 1)
            for i in range(1, len(xs)):
                p.drawLine(int((i - 1) * step), int(mid - xs[i - 1] * mid * 0.9), int(i * step), int(mid - xs[i] * mid * 0.9))
        else:
            p.setPen(QtGui.QColor("#8ea6c8")); p.drawText(self.rect().adjusted(12, 12, -12, -12), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "Waveform: appears when the microphone sends sound")
        p.end()


class MicPage(W.QWidget):
    ROWS = [("gain", "Input gain", -12, 12, "dB"), ("bass", "Bass", -12, 12, "dB"), ("mid", "Mid", -12, 12, "dB"),
            ("treble", "Treble", -12, 12, "dB"), ("gate", "Noise gate threshold", -60, 0, "dB (-60 = off)"),
            ("comp", "Compressor", 0, 100, "%"), ("out", "Output level to radio", 0, 150, "%")]

    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        self.cur = dict(DEFAULT); self.cur.update(ctx.store.settings.get("mic", {}) or {})
        # live push to the engine: a short pause after the last change, so dragging a slider sends one update
        self._push_timer = QtCore.QTimer(self); self._push_timer.setSingleShot(True); self._push_timer.setInterval(120)
        self._push_timer.timeout.connect(self._push)
        v = vbox(self, m=(24, 18, 24, 18), s=10)
        t = label("Microphone"); t.setStyleSheet("font-size:22px;font-weight:700;"); v.addWidget(t)
        v.addWidget(label("Adjust the sound that goes from this computer to the radio network. Hold Talk and speak: the other station hears each change.", muted=True))
        body = hbox(s=24)
        lw = W.QFrame(); lw.setObjectName("card"); lw.setFixedHeight(H); lw.setMaximumWidth(680)
        left = vbox(m=(18, 16, 18, 16), s=8); lw.setLayout(left)
        sec = label("CONTROLS"); sec.setStyleSheet("font-size:11px;font-weight:700;letter-spacing:1px;"); left.addWidget(sec)
        self.sliders: dict = {}; self.values: dict = {}
        for key, name, lo, hi, unit in self.ROWS:
            r = hbox(s=10); nm = label(name); nm.setFixedWidth(190); r.addWidget(nm)
            s = W.QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi); s.setValue(int(self.cur[key])); s.setMinimumWidth(260); s.setMaximumWidth(460); r.addWidget(s)
            val = label(f"{int(self.cur[key])} {unit.split(' ')[0]}"); val.setFixedWidth(120); r.addWidget(val); r.addStretch(1)
            s.valueChanged.connect(lambda x, k=key, u=unit, lab=val: (lab.setText(f"{x} {u.split(' ')[0]}"), self._push_timer.start()))
            left.addLayout(r); left.addStretch(1); self.sliders[key] = s; self.values[key] = val
        hp = hbox(s=10); hl = label("High-pass filter (cuts rumble)"); hl.setFixedWidth(190); hp.addWidget(hl)
        self.hp = W.QComboBox(); self.hp.addItems([n for n, _ in HP_CHOICES])
        self.hp.setCurrentIndex(next((i for i, (_, hz) in enumerate(HP_CHOICES) if hz == int(self.cur["highpass"])), 0))
        self.hp.setMaximumWidth(300); self.hp.currentIndexChanged.connect(lambda _: self._push_timer.start())
        hp.addWidget(self.hp); hp.addStretch(1); left.addLayout(hp); left.addStretch(1)
        btns = hbox(s=10); self.save = button("Save", "primary"); self.reset = button("Reset to defaults")
        self.talk = button("Hold to talk")
        self.talk.pressed.connect(lambda: ctx.ptt_down(False)); self.talk.released.connect(ctx.ptt_up)
        btns.addWidget(self.save); btns.addWidget(self.reset); btns.addWidget(self.talk); btns.addStretch(1); left.addLayout(btns)
        self.note = label("", muted=True); self.note.setWordWrap(True); left.addWidget(self.note)
        body.addWidget(lw, 0, Qt.AlignmentFlag.AlignTop)
        rc = W.QFrame(); rc.setObjectName("card"); rc.setFixedHeight(H); right = vbox(m=(18, 16, 18, 16), s=8); rc.setLayout(right)
        wl = label("LIVE WAVEFORM"); wl.setStyleSheet("font-size:11px;font-weight:700;letter-spacing:1px;"); right.addWidget(wl)
        self.wave = Wave(); right.addWidget(self.wave, 1)
        self.live = label("Not transmitting", muted=True); right.addWidget(self.live)
        body.addWidget(rc, 1, Qt.AlignmentFlag.AlignTop)
        v.addLayout(body); v.addStretch(1)
        self.save.clicked.connect(self._save); self.reset.clicked.connect(self._reset)
        wave_sig = getattr(ctx.engine, "mic_wave", None)
        if wave_sig is not None: wave_sig.connect(self.set_wave)
        self._push()                     # the engine keeps these, so every new connection starts with them
        self._show_state()

    def _values(self) -> dict:
        d = {k: s.value() for k, s in self.sliders.items()}
        d["highpass"] = HP_CHOICES[self.hp.currentIndex()][1]
        return d

    def _push(self):
        """Send the current values to the engine now (not saved until Save)."""
        self.ctx.engine.set_mic(self._values())

    def _save(self):
        self.ctx.store.settings["mic"] = self._values(); self.ctx.store.save_settings()
        self._push()
        self.ctx.toast.emit("Microphone settings saved.")
        self._show_state()

    def _reset(self):
        for k, s in self.sliders.items(): s.setValue(DEFAULT[k])
        self.hp.setCurrentIndex(0); self._push()

    def set_wave(self, samples, gate_open=True, lim_db=0.0):
        """The engine sends the processed microphone signal while transmitting: draw it and show what the processing did."""
        self.wave.set_samples(samples)
        peak = max((abs(x) for x in samples), default=0.0)
        db = 20.0 * math.log10(peak) if peak > 1e-4 else -90.0
        parts = [f"Level {db:.0f} dBFS", "gate open" if gate_open else "gate closed"]
        parts.append(f"limiter {lim_db:.1f} dB" if lim_db < -0.05 else "limiter idle")
        self.live.setText("   ·   ".join(parts))

    def _show_state(self):
        if getattr(self.ctx.engine, "preview", False):
            self.note.setText("No protocol engine is running (preview). Settings are saved, but nothing is sent to the radio.")
        else:
            self.note.setText("Applied to the transmitter: connect to a server, hold Hold to talk and speak. The waveform and the level above show what is sent.")
