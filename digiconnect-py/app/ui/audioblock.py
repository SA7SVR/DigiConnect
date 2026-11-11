"""One audio block (microphone, speakers, test buttons, microphone volume) used by every radio page and by Settings.
All instances show the same choice: a change in one is applied to the settings and to the others."""
import threading
from ..qt import QtWidgets as W, QtCore, Qt, Signal
from ..i18n import tr
from .. import audio_devices as AD
from .widgets import label, button, field, vbox, hbox, FlowLayout

SYSTEM_DEFAULT = "System default"


class _Bus(QtCore.QObject):
    """Process-wide: devices were reloaded / a choice was made / a background test finished."""
    changed = Signal()
    result = Signal(str, dict)
    gain = Signal(int)


_bus = None
def bus() -> _Bus:
    global _bus
    if _bus is None: _bus = _Bus()
    return _bus


class AudioBlock(W.QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent); self.ctx = ctx
        v = vbox(self, s=8)
        self.mic = W.QComboBox(); self.spk = W.QComboBox()
        v.addWidget(field("Microphone", self.mic)); v.addWidget(field("Speakers", self.spk))
        ar = FlowLayout(hspace=6, vspace=6)
        self.b_ref = button("Refresh devices"); self.b_tm = button("Test microphone"); self.b_ts = button("Test speakers")
        for b in (self.b_ref, self.b_tm, self.b_ts): ar.addWidget(b)
        v.addLayout(ar)
        self.gain = W.QSlider(Qt.Orientation.Horizontal); self.gain.setRange(0, 300)
        self.gain.setValue(int(ctx.store.settings.get("mic_gain", 100))); self.gain_val = label("", muted=True)
        gr = hbox(); gr.addWidget(label("Microphone volume", muted=True)); gr.addWidget(self.gain, 1); gr.addWidget(self.gain_val); v.addLayout(gr)
        self.gain.setToolTip("100% = the microphone level. Raise it above 100% if the other stations hear you too quietly.")
        self.info = label("", muted=True); self.info.setWordWrap(True); v.addWidget(self.info)
        self._busy = False
        self.b_ref.clicked.connect(lambda: self.reload(True)); self.b_tm.clicked.connect(self._test_mic); self.b_ts.clicked.connect(self._test_spk)
        self.mic.activated.connect(self._picked); self.spk.activated.connect(self._picked)
        self.gain.valueChanged.connect(self._gain); self._gain_text(self.gain.value())
        bus().changed.connect(self._fill); bus().result.connect(self._result); bus().gain.connect(self._gain_from_bus)
        self._fill()

    # ---- list / choice -----------------------------------------------------------
    def reload(self, force=False):
        ins, outs, err = AD.list_devices(force)
        self._fill()
        if force:
            self.info.setText(err or f"Devices refreshed: {len(ins)} microphone(s), {len(outs)} speaker(s) found.")   # template in i18n: "Devices refreshed: {} microphone(s), {} speaker(s) found."
        bus().changed.emit()

    def _fill(self):
        ins, outs, err = AD.list_devices(False); st = self.ctx.store.settings
        for combo, items, key in ((self.mic, ins, "mic"), (self.spk, outs, "speakers")):
            combo.blockSignals(True); combo.clear()
            combo.addItem(tr(SYSTEM_DEFAULT), "")
            for n in items: combo.addItem(n, n)
            i = combo.findData(st.get(key) or "")
            combo.setCurrentIndex(i if i >= 0 else 0)
            combo.blockSignals(False)
        if not self.info.text(): self.info.setText(err or f"{len(ins)} available microphone{'s' if len(ins) != 1 else ''}")

    def selected(self) -> tuple[str, str]:
        return self.mic.currentData() or "", self.spk.currentData() or ""

    def _picked(self, *_):
        m, s = self.selected(); st = self.ctx.store.settings
        st["mic"], st["speakers"] = m, s; self.ctx.store.save_settings(); bus().changed.emit()
        self.info.setText("Audio devices are used from the next connection on.")

    def _gain_text(self, v): self.gain_val.setText(f"{v}%")

    def _gain(self, v):
        self._gain_text(v); self.ctx.set_mic_gain(v); bus().gain.emit(v)

    def _gain_from_bus(self, v):
        if self.gain.value() != v:
            self.gain.blockSignals(True); self.gain.setValue(v); self.gain.blockSignals(False); self._gain_text(v)

    # ---- tests ---------------------------------------------------------------------
    def _run(self, kind, fn, name):
        if self._busy: return
        self._busy = True
        for b in (self.b_tm, self.b_ts, self.b_ref): b.setEnabled(False)
        self.info.setText("Testing the microphone… speak now." if kind == "mic" else "Playing the test tone…")
        def work():
            try: r = fn(name)
            except Exception as ex: r = {"ok": False, "msg": f"{ex.__class__.__name__}: {ex}"}
            bus().result.emit(kind, r)
        threading.Thread(target=work, daemon=True).start()

    def _test_mic(self): self._run("mic", AD.test_mic, self.selected()[0])
    def _test_spk(self): self._run("spk", AD.test_speakers, self.selected()[1])

    def _result(self, kind, r):
        if not self._busy: return
        self._busy = False
        for b in (self.b_tm, self.b_ts, self.b_ref): b.setEnabled(True)
        if kind == "mic": self.info.setText(AD.mic_text(r))
        else: self.info.setText("Speaker test played — you should have heard a tone." if r.get("ok") else (f"Speaker test failed: {r['msg']}" if r.get("msg") else "Speaker test failed: the output could not be opened."))
