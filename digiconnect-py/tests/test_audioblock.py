"""Audio block: device list, working test buttons (through the real engine), microphone volume."""
import os, time, pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.qt import QtWidgets, QtCore
from app.engine_client import find_engine
from app import audio_devices as AD

needs_engine = pytest.mark.skipif(not find_engine(), reason="dcengine not built (set DC_ENGINE)")


def pump(app, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if cond(): return True
    return False


def test_mic_text_levels():
    assert "OK" in AD.mic_text({"ok": True, "peak": 0.4}) and "very low" in AD.mic_text({"ok": True, "peak": 0.05})
    assert "no signal" in AD.mic_text({"ok": True, "peak": 0.0}) and "failed" in AD.mic_text({"ok": False, "msg": "x"})


@needs_engine
def test_block_buttons_and_gain(tmp_path):
    from app.store import Store
    from app.context import Ctx
    from app.engine_client import EngineClient
    from app.ui.audioblock import AudioBlock
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    st = Store(tmp_path); eng = EngineClient(find_engine(), st); ctx = Ctx(st, eng)
    blk = AudioBlock(ctx)
    assert blk.mic.itemData(0) == "" and blk.spk.itemData(0) == ""                          # 'System default' is always first
    blk.b_ref.click(); assert "refreshed" in blk.info.text()                                 # visible feedback (a sandbox has no devices)
    blk.b_tm.click(); assert not blk.b_tm.isEnabled()
    assert pump(app, lambda: blk.b_tm.isEnabled()) and blk.info.text().startswith("Microphone test")   # the test ran and reported
    blk.b_ts.click(); assert pump(app, lambda: blk.b_ts.isEnabled()) and blk.info.text().startswith("Speaker test")
    blk.gain.setValue(250); assert st.settings["mic_gain"] == 250 and abs(eng.mic_gain() - 2.5) < 1e-9
    other = AudioBlock(ctx); assert other.gain.value() == 250
    blk.gain.setValue(120); app.processEvents(); assert other.gain.value() == 120            # all pages show the same setting
    eng.shutdown()
