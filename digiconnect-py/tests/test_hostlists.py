"""World-wide server lists: parsers (the formats of the public host files), a real HTTP download from a local
test server, the offline cache, and the connection lookup that uses the downloaded entries."""
import os, sys, pathlib, tempfile, threading, http.server, functools
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app import hostlists as H
from app.rules import Target

YSF = """# YSF hosts
00006;GR-HELLAS;Zone A (YCS202);ysf.example.gr;42000;012
00010;DX Zone;with www.note.org in text;dx.example.gr;42001;003
10001;Some Reflector;desc;93.184.216.34;42000;000
FCS00101;FCS001-01;foo;fcs001.xreflector.net;62500;000
badline
"""
DPLUS = "# dplus\nREF001\t1.2.3.4\t20001\nREF030  ref030.example.org  20001\nXYZ999 9.9.9.9\n"
DEXTRA = "XRF001  xrf001.example.net  30001\nXRF757\t5.6.7.8\n"
DCS = "DCS001;dcs001.example.com;30051\n"
XLX = "XLX001;xlx001.example.org;4\nXLXQRZ;xlxqrz.example.gr;\n"
DMR = ("# name\n"
       "BM_Greece_202\t0\t0\t0\t0\tgreece.master.example.net\tpassw0rd\t62031\n"
       "BM_United_States_3101\t0\t0\t0\t0\t3101.master.example.net\tpassw0rd\t62031\n"
       "DMR+_IPSC2-Test\t0\t0\t0\t0\tdmrplus.example.de\tpassw0rd\t55555\n")
XLXAPI = """<?xml version="1.0"?><reflectorlist><reflector><name>XLX001</name><lastip>1.1.1.1</lastip><dns>xlx001.example.org</dns><country>Germany</country><comment>Test net</comment></reflector>
<reflector><name>XLX999</name><dns>xlx999.example.org</dns><country>Sweden</country></reflector></reflectorlist>"""


def test_parsers():
    y = H.parse_ysf(YSF); assert [e["id"] for e in y] == ["00006", "00010", "10001"]       # FCS and junk are not YSF
    assert y[0]["host"] == "ysf.example.gr" and y[0]["port"] == 42000
    assert y[1]["host"] == "dx.example.gr" and y[1]["port"] == 42001                          # a dotted word in the description is not the host
    assert y[2]["host"] == "93.184.216.34"
    d = H.parse_dstar(DPLUS, "REF"); assert [(e["id"], e["host"], e["port"]) for e in d] == [("REF001 C", "1.2.3.4", 20001), ("REF030 C", "ref030.example.org", 20001)]
    x = H.parse_dstar(DEXTRA, "XRF"); assert x[1]["host"] == "5.6.7.8" and x[1]["port"] == 30001   # default port when the file has none
    assert H.parse_dstar(DCS, "DCS")[0]["host"] == "dcs001.example.com"
    assert [e["id"] for e in H.parse_dstar(XLX, "XLX")] == ["XLX001 A", "XLXQRZ A"]
    m = H.parse_dmr(DMR); assert len(m) == 3 and m[0]["country"] == "Greece" and m[1]["country"] == "United States" and m[2]["port"] == 55555
    assert m[0]["host"] == "greece.master.example.net" and m[0]["port"] == 62031
    a = H.parse_xlx_api(XLXAPI); assert {e["id"] for e in a} == {"XLX001 A", "XLX999 A"} and a[0]["country"] == "Germany"


@pytest.fixture
def web(tmp_path):
    root = tmp_path / "www"; root.mkdir()
    for n, t in {"YSFHosts.txt": YSF, "DPlus_Hosts.txt": DPLUS, "DExtra_Hosts.txt": DEXTRA, "DCS_Hosts.txt": DCS, "XLXHosts.txt": XLX, "DMR_Hosts.txt": DMR, "xlx.xml": XLXAPI}.items():
        (root / n).write_text(t, encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/", root
    srv.shutdown()


def test_download_cache_and_resolve(tmp_path, web):
    base, root = web
    store = type("S", (), {"root": tmp_path / "d", "settings": {}})(); store.root.mkdir()
    hl = H.HostLists(store.root); assert hl.stale() and not hl.entries
    # first mirror is dead on purpose: the second one must be used
    n, problems = hl.download(mirrors=["http://127.0.0.1:9/", base], xlx_api=base + "xlx.xml")
    assert not problems and n >= 10, (n, problems)
    assert {k: v for k, v in hl.status.items()} and all(v.startswith("ok") for v in hl.status.values()), hl.status
    assert hl.find("YSF", "00006") == {"host": "ysf.example.gr", "port": 42000}
    assert hl.find("REF", "ref030") == {"host": "ref030.example.org", "port": 20001}
    assert hl.find("XLX", "XLX999")["host"] == "xlx999.example.org"                          # added from the API
    assert [e["country"] for e in hl.entries if e["id"] == "XLX001 A"] == ["Germany"]
    assert len(hl.dmr_masters()) == 3 and len(hl.for_net("C4FM")) == 3 and len(hl.for_net("D-Star")) >= 6
    assert not hl.stale()
    # persisted: a new object (a later start of the program, maybe offline) sees the same data
    again = H.HostLists(store.root); assert len(again.entries) == len(hl.entries) and again.find("XRF", "XRF001")["host"] == "xrf001.example.net"
    # one list disappears from the server: the old copy of it is kept, the problem is reported
    (root / "DCS_Hosts.txt").unlink()
    n2, problems2 = hl.download(mirrors=[base], xlx_api="")
    assert any("DCS" in p for p in problems2) and hl.find("DCS", "DCS001")["host"] == "dcs001.example.com"
    # everything unreachable: nothing is lost
    before = len(hl.entries); n3, p3 = hl.download(mirrors=["http://127.0.0.1:9/"], xlx_api="")
    assert len(hl.entries) == before and p3


def test_servers_resolve_from_lists(tmp_path, web):
    from app.servers import Servers
    base, _ = web
    store = type("S", (), {"root": tmp_path / "d2", "settings": {}})(); store.root.mkdir()
    sv = Servers(store); assert sv.resolve(Target("C4FM", "00006")) is None                  # nothing downloaded: never guessed
    sv.hosts.download(mirrors=[base], xlx_api="")
    assert sv.resolve(Target("C4FM", "00006")) == {"host": "ysf.example.gr", "port": 42000}
    assert sv.resolve(Target("D-Star", "REF001 B")) == {"host": "1.2.3.4", "port": 20001}    # module is not part of the address
    assert sv.resolve(Target("D-Star", "XRF757 A")) == {"host": "5.6.7.8", "port": 30001}
    assert sv.resolve(Target("C4FM", "99999")) is None
    sv.user["C4FM:00006"] = {"host": "mine.example", "port": 1}                              # the user's own entry wins
    assert sv.resolve(Target("C4FM", "00006")) == {"host": "mine.example", "port": 1}


def test_directory_and_ui(tmp_path, web):
    from app.qt import QtWidgets
    from app.store import Store
    from app.context import Ctx
    from app.theme import qss
    from app.ui.main_window import MainWindow
    base, _ = web
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    (tmp_path / "ui").mkdir(); st = Store(tmp_path / "ui"); st.settings["callsign"] = "SA7SVR"
    ctx = Ctx(st); app.setStyleSheet(qss(14)); w = MainWindow(ctx); w.show(); app.processEvents()
    ws = w.ws["D-Star"]; before = ws.list.count()
    assert "not downloaded yet" in ws.count.text()
    ctx.hosts.download(mirrors=[base], xlx_api=base + "xlx.xml"); ctx.hosts_changed.emit(); app.processEvents()
    texts = [ws.list.item(i).text() for i in range(ws.list.count())]
    assert any("REF030" in t for t in texts) and ws.list.count() > before
    assert "Germany" in [ws.country.itemText(i) for i in range(ws.country.count())]
    ws.country.setCurrentText("Germany"); app.processEvents(); assert all("XLX001" in ws.list.item(i).text() for i in range(ws.list.count())) and ws.list.count() == 1
    ws.country.setCurrentIndex(0); ws.search.setText("REF030"); app.processEvents(); assert ws.list.count() == 1
    ws.module.setCurrentText("F"); ws.list.setCurrentRow(0); assert ctx.selected == Target("D-Star", "REF030 F", "REF030")
    assert w.ws["C4FM"].list.count() == 5                                                     # 4 seed (00006/00010 also in the list, shown once) + 10001
    w.close()
