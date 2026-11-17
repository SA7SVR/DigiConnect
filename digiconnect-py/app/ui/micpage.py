"""Microphone page: input gain, 3-band equaliser, high-pass filter, noise gate, compressor and output level.
The values are saved per computer (settings['mic']). The engine applies them to the transmit audio only after its audio step is built;
until then the page says so, and nothing pretends the sound has changed."""
from ..qt import QtWidgets as W, Qt
from .widgets import label, button, vbox, hbox
from ..i18n import tr

DEFAULT = dict(gain=0, bass=0, mid=0, treble=0, highpass=0, gate=-60, comp=0, out=100)
HP_CHOICES = [("Off", 0), ("80 Hz", 80), ("120 Hz", 120), ("200 Hz", 200)]


class Wave(W.QFrame):
    """Box that draws the microphone waveform: a line of samples in -1..1, newest on the right. Empty until the engine sends samples."""
    def __init__(self):
        super().__init__(); self.setObjectName("wave"); self.setFixedSize(300, 250); self.samples: list = []
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
        v = vbox(self, m=(24, 18, 24, 18), s=10)
        t = label("Microphone"); t.setStyleSheet("font-size:22px;font-weight:700;"); v.addWidget(t)
        v.addWidget(label("Adjust the sound that goes from this computer to the radio network. Watch the level meter while you speak.", muted=True))
        body = hbox(s=24); left = vbox(s=10); lw = W.QWidget(); lw.setLayout(left); lw.setMaximumWidth(620)
        self.sliders: dict = {}; self.values: dict = {}
        for key, name, lo, hi, unit in self.ROWS:
            r = hbox(s=10); nm = label(name); nm.setFixedWidth(190); r.addWidget(nm)
            s = W.QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi); s.setValue(int(self.cur[key])); s.setMaximumWidth(300); r.addWidget(s)
            val = label(f"{int(self.cur[key])} {unit.split(' ')[0]}"); val.setFixedWidth(120); r.addWidget(val); r.addStretch(1)
            s.valueChanged.connect(lambda x, k=key, u=unit, lab=val: lab.setText(f"{x} {u.split(' ')[0]}"))
            left.addLayout(r); self.sliders[key] = s; self.values[key] = val
        hp = hbox(s=10); hl = label("High-pass filter (cuts rumble)"); hl.setFixedWidth(190); hp.addWidget(hl)
        self.hp = W.QComboBox(); self.hp.addItems([n for n, _ in HP_CHOICES])
        self.hp.setCurrentIndex(next((i for i, (_, hz) in enumerate(HP_CHOICES) if hz == int(self.cur["highpass"])), 0))
        self.hp.setMaximumWidth(300); hp.addWidget(self.hp); hp.addStretch(1); left.addLayout(hp)
        btns = hbox(s=10); self.save = button("Save", "primary"); self.reset = button("Reset to defaults"); self.test = button("Speak to test")
        btns.addWidget(self.save); btns.addWidget(self.reset); btns.addWidget(self.test); btns.addStretch(1); left.addLayout(btns)
        self.note = label("", muted=True); self.note.setWordWrap(True); left.addWidget(self.note); left.addStretch(1)
        body.addWidget(lw, 0, Qt.AlignmentFlag.AlignTop); body.addStretch(1)
        self.wave = Wave(); body.addWidget(self.wave, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(body); v.addStretch(1)
        self.save.clicked.connect(self._save); self.reset.clicked.connect(self._reset)
        self.test.clicked.connect(lambda: ctx.toast.emit("Speak into the microphone with the transmit button held. The level is shown on the bar at the bottom."))
        self._show_state()

    def _values(self) -> dict:
        d = {k: s.value() for k, s in self.sliders.items()}
        d["highpass"] = HP_CHOICES[self.hp.currentIndex()][1]
        return d

    def _save(self):
        self.ctx.store.settings["mic"] = self._values(); self.ctx.store.save_settings()
        self.note.setText("Saved on this computer. The engine does not apply these values to the audio yet; they will take effect once the audio step is built.")
        self.ctx.toast.emit("Microphone settings saved.")

    def _reset(self):
        for k, s in self.sliders.items(): s.setValue(DEFAULT[k])
        self.hp.setCurrentIndex(0)

    def set_wave(self, samples):
        """Called with the microphone samples (-1..1) when the engine sends them."""
        self.wave.set_samples(samples)

    def _show_state(self):
        self.note.setText("Not yet applied: the engine has no microphone equaliser yet. Save keeps the values for when it does.")
