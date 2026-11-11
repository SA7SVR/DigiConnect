"""NXDN, P25 and M17 resolve their server from the worldwide list and pass the right parameters to the engine."""
import os, sys, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.qt import QtWidgets as W
from app.store import Store
from app.rules import Target
from app.engine_client import EngineClient


def test_params_for_nxdn_p25_m17(tmp_path):
    W.QApplication.instance() or W.QApplication([])
    st = Store(tmp_path); st.settings.update(callsign="SA7SVR", dmr_id="2401234", nxdn_id="12345")
    eng = EngineClient("/nonexistent", st)
    e = lambda net, proto, id_, host, port: dict(net=net, proto=proto, id=id_, name=id_, sub="", activity="", host=host, port=port, country="")
    eng.servers.hosts._set([e("NXDN", "NXDN", "65000", "nx.example", 41400), e("P25", "P25", "10100", "p.example", 41000), e("M17", "M17", "M17-DEU A", "m.example", 17000)], {}, 1e12)
    p, err = eng._params(Target("NXDN", "65000", "x")); assert not err and (p["mode"], p["nxdnid"], p["name"], p["host"], p["port"]) == ("NXDN", 12345, "65000", "nx.example", 41400)
    p, err = eng._params(Target("P25", "10100", "x")); assert not err and (p["mode"], p["dmrid"], p["port"]) == ("P25", 2401234, 41000)
    p, err = eng._params(Target("M17", "M17-DEU C", "x")); assert not err and (p["mode"], p["name"], p["module"], p["host"]) == ("M17", "M17-DEU", "C", "m.example")
    st.settings["nxdn_id"] = ""
    p, err = eng._params(Target("NXDN", "65000", "x")); assert p is None and "NXDN ID" in err
    p, err = eng._params(Target("NXDN", "1", "x")); assert p is None and err == "NEED_ENDPOINT"
