"""End to end: UI context -> EngineClient -> real dcengine process -> fake YSF reflector."""
import os, socket, threading, time, pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.qt import QtWidgets, QtCore
from app.engine_client import EngineClient, find_engine
from app.context import Ctx
from app.store import Store
from app.rules import Target

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
PORT = 42177


@pytest.fixture
def reflector():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("127.0.0.1", PORT)); sock.settimeout(0.2)
    stop = threading.Event(); seen = {"ysfp": 0, "ysfd": 0}
    def run():
        while not stop.is_set():
            try: data, addr = sock.recvfrom(2048)
            except socket.timeout: continue
            if data[:4] == b"YSFP": seen["ysfp"] += 1; sock.sendto(b"YSFP" + b"TESTREFLEC", addr)
            elif data[:4] == b"YSFD": seen["ysfd"] += 1
    th = threading.Thread(target=run, daemon=True); th.start()
    yield seen
    stop.set(); th.join(1); sock.close()


def pump(app, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if cond(): return True
    return False


def test_listen_and_tx_through_real_engine(tmp_path, reflector):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store = Store(tmp_path); store.settings["callsign"] = "SA7SVR"
    eng = EngineClient(ENGINE, store); ctx = Ctx(store, eng)
    t = Target("C4FM", "00006", "Test reflector")
    # entry not in the worldwide list -> nothing is connected and the user is told (never asked for host:port)
    msgs = []; ctx.toast.connect(msgs.append); ctx._auto_dl = True      # no network in tests
    ctx.select(t); ctx.toggle_listen()
    assert not ctx.rules.rx and any("worldwide" in m for m in msgs)
    # entry present in the downloaded list -> plain Listen connects
    eng.servers.hosts._set([dict(net="C4FM", proto="YSF", id="00006", name="Test", sub="", activity="", host="127.0.0.1", port=PORT, country="")], {}, 1e12)
    ctx.toggle_listen()
    assert ctx.rules.rx, "receiver should be registered"
    assert pump(app, lambda: reflector["ysfp"] > 0, 30), "engine never contacted the reflector"      # a loaded CI runner starts the engine slowly
    assert pump(app, lambda: eng.links and next(iter(eng.links.values())).state == "connected", 20)
    # Connect (TX) on the same destination reuses the same engine process
    ctx.toggle_tx()
    assert ctx.rules.tx_connected and len(eng.links) == 1
    ctx.ptt_down(); pump(app, lambda: reflector["ysfd"] >= 3, 8)
    ctx.ptt_up()
    assert reflector["ysfd"] >= 3, "PTT must produce voice frames at the reflector"
    # stopping everything ends the engine process
    ctx.stop_all(); assert pump(app, lambda: not eng.links, 3)
    eng.shutdown()


def test_no_callsign_is_refused_with_message(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store = Store(tmp_path); eng = EngineClient(ENGINE, store); ctx = Ctx(store, eng)
    msgs = []; ctx.toast.connect(msgs.append)
    ctx.select(Target("C4FM", "00006", "x")); ctx.toggle_listen()
    assert not ctx.rules.rx and any("callsign" in m.lower() for m in msgs)


def test_volume_mute_and_ducking_reach_the_engine(tmp_path):
    from app.rules import Receiver
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store = Store(tmp_path); sent = []
    eng = EngineClient(ENGINE, store); eng.set_rx_volume = lambda h, v: sent.append((h, v))
    ctx = Ctx(store, eng)
    t = Target("C4FM", "00006", "x"); ctx.rules.listen(t); h = ctx.rules.rx[0].handle
    ctx._sync_audio(); assert sent[-1] == (h, 1.0)
    ctx.rules.net_volume["C4FM"] = 0.4; ctx._sync_audio(); assert sent[-1] == (h, 0.4)
    ctx.rules.net_muted["C4FM"] = True; ctx._sync_audio(); assert sent[-1] == (h, 0.0)
    n = len(sent); ctx._sync_audio(); assert len(sent) == n, "unchanged volume must not be re-sent"
