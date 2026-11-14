"""The "Choose DMR server" window: search, network filter, one row per server from the downloaded lists (nothing typed in, nothing changed),
a Choose button on every row, pages of 100, and Manual entry / Refresh / Close.
It only picks: the caller stores the choice (Settings > Radio networks gets the same Server and Port)."""
import re
from ..qt import QtWidgets as W, QtCore, Qt
from ..i18n import tr
from .widgets import *

PAGE = 100
_HOST = re.compile(r"^(?:\d{1,3}(?:\.\d{1,3}){3}|[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+)$")


def display_name(e: dict) -> str:
    """The name as the list gives it; '_' is only the list's word separator (BM_2001_Europe_HAMNET -> BM 2001 Europe HAMNET)."""
    return (e.get("name") or e.get("host") or "").replace("_", " ")


def network_of(e: dict) -> str:
    p = (e.get("name") or "").split("_", 1)[0].strip()
    if e.get("src") == "api": return "BrandMeister"
    return "BrandMeister" if p.upper() == "BM" else (p or "Other")


def master_id(e: dict) -> str:
    if e.get("ident"): return str(e["ident"])
    m = re.match(r"^(?:BM|BrandMeister)[ _](\d{3,5})\b", e.get("name") or "", re.I)
    return m.group(1) if m else ""


def parse_manual(text: str) -> tuple[str, int] | None:
    """'host' or 'host:port' (default port 62031) -> (host, port); None when it is not a usable address."""
    t = (text or "").strip().replace(" ", "")
    host, _, port = t.partition(":")
    if not _HOST.match(host) or (port and not (port.isdigit() and 0 < int(port) < 65536)): return None
    return host, int(port) if port else 62031


class DmrServerPicker(W.QDialog):
    def __init__(self, parent, get_masters, current_host: str = "", refresh=None, hosts_changed=None):
        super().__init__(parent); self.setWindowTitle(tr("Choose DMR server")); self.setModal(True); self.resize(680, 760)
        self.get_masters, self.refresh_cb, self.chosen, self.page = get_masters, refresh, None, 0
        self.masters: list[dict] = []; self.shown: list[dict] = []
        v = vbox(self, m=(22, 18, 22, 18), s=10)
        head = hbox(); t = label(tr("Choose DMR server")); t.setStyleSheet("font-size:20px;font-weight:700;"); head.addWidget(t, 1)
        x = button("", "rail", "close"); x.setFixedSize(34, 34); x.clicked.connect(self.reject); head.addWidget(x); v.addLayout(head)
        fr = hbox(s=8); self.q = W.QLineEdit(); self.q.setPlaceholderText(tr("Search server, country, ID or address…"))
        self.net = W.QComboBox(); self.net.setMinimumWidth(190); fr.addWidget(self.q, 1); fr.addWidget(self.net); v.addLayout(fr)
        self.count = label("", muted=True); v.addWidget(self.count)
        self.sc = W.QScrollArea(); self.sc.setWidgetResizable(True); self.sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = W.QWidget(); self.body.setObjectName("scrollinner"); self.body.setStyleSheet("QWidget#scrollinner{background:transparent;}")
        self.rows = vbox(self.body, s=0); self.rows.addStretch(); self.sc.setWidget(self.body); v.addWidget(self.sc, 1)
        pr = hbox(); self.pos = label("", muted=True); self.prev = button(tr("Previous")); self.next = button(tr("Next"))
        pr.addWidget(self.pos, 1); pr.addWidget(self.prev); pr.addWidget(self.next); v.addLayout(pr)
        n = label(tr("Access and TGs depend on the network. Check your ID and password in Settings → Radio networks."), muted=True); n.setWordWrap(True); v.addWidget(n)
        bb = hbox(s=8); bb.addStretch(); self.manual = button(tr("Manual entry")); self.refresh = button(tr("Refresh")); close = button(tr("Close"))
        for b in (self.manual, self.refresh, close): bb.addWidget(b)
        v.addLayout(bb)
        close.clicked.connect(self.reject); self.manual.clicked.connect(self._manual); self.refresh.clicked.connect(self._refresh)
        self.prev.clicked.connect(lambda: self._go(-1)); self.next.clicked.connect(lambda: self._go(1))
        self.q.textChanged.connect(lambda *_: self._reset()); self.net.currentIndexChanged.connect(lambda *_: self._reset())
        if hosts_changed is not None: hosts_changed.connect(self.reload)
        self.current_host = (current_host or "").lower(); self.reload(first=True)

    # ---- data ------------------------------------------------------------------------------
    def reload(self, first=False):
        self.masters = list(self.get_masters()); keep = self.net.currentData()
        names = sorted({network_of(e) for e in self.masters}, key=lambda n: (n == "Other", n != "BrandMeister", n.lower()))
        self.net.blockSignals(True); self.net.clear(); self.net.addItem(tr("All networks"), "")
        for n in names: self.net.addItem(n, n)
        i = self.net.findData(keep) if keep else -1
        if first and i < 0:                                           # open on the network of the server used now
            cur = next((e for e in self.masters if e["host"].lower() == self.current_host), None); i = self.net.findData(network_of(cur)) if cur else -1
        self.net.setCurrentIndex(max(0, i)); self.net.blockSignals(False)
        api = sum(1 for e in self.masters if e.get("src") == "api"); lst = len(self.masters) - api
        parts = ([f"{tr('BrandMeister API')} : {api}"] if api else []) + ([f"{tr('Pi-Star')} : {lst}"] if lst else [])
        self.count.setText(" · ".join(parts) if parts else tr("The DMR server list is not downloaded yet — press Refresh."))
        self._filter()

    def _reset(self): self.page = 0; self._filter()

    def _filter(self):
        t = self.q.text().strip().lower(); want = self.net.currentData() or ""
        self.shown = [e for e in sorted(self.masters, key=lambda e: display_name(e).lower())
                      if (not want or network_of(e) == want) and (not t or t in " ".join((display_name(e), e.get("name", ""), e["host"], e.get("country", ""), master_id(e))).lower())]
        self.page = min(self.page, max(0, (len(self.shown) - 1) // PAGE)); self._draw()

    def _go(self, d): self.page = max(0, min(self.page + d, (len(self.shown) - 1) // PAGE)); self._draw(); self.sc.verticalScrollBar().setValue(0)

    # ---- drawing ---------------------------------------------------------------------------
    def _draw(self):
        while self.rows.count() > 1:
            it = self.rows.takeAt(0); w = it.widget()
            if w is not None: w.setParent(None); w.deleteLater()
        a = self.page * PAGE; chunk = self.shown[a:a + PAGE]
        for k, e in enumerate(chunk): self.rows.insertWidget(k, self._row(e))
        n = len(self.shown)
        self.pos.setText(f"{a + 1 if n else 0}–{a + len(chunk)} / {n}")
        self.prev.setEnabled(self.page > 0); self.next.setEnabled(a + PAGE < n)

    def _row(self, e: dict) -> W.QWidget:
        w = panel("dmrrow"); w.setStyleSheet("QFrame#dmrrow{background:transparent;border:none;border-bottom:1px solid rgba(128,128,160,0.25);border-radius:0;}")
        h = hbox(w, m=(2, 8, 2, 8), s=8); c = vbox(s=2)
        nm = label(display_name(e)); nm.setStyleSheet("font-weight:700;"); c.addWidget(nm)
        ident = master_id(e); c.addWidget(label(" · ".join(x for x in (network_of(e), e.get("country") or tr("Not specified"), ident) if x), muted=True))
        c.addWidget(label(f"{e['host']} : {e['port']}", muted=True)); h.addLayout(c, 1)
        b = button(tr("Choose")); b.clicked.connect(lambda _=False, e=e: self._pick(e)); h.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        if e["host"].lower() == self.current_host: nm.setText(nm.text() + "  ✓")
        return w

    # ---- actions ---------------------------------------------------------------------------
    def _pick(self, e: dict): self.chosen = e; self.accept()

    def _manual(self):
        text, ok = W.QInputDialog.getText(self, tr("Manual entry"), tr("Server address, e.g. 185.4.134.95:62031 (the port is optional, 62031 is the default)"))
        if not ok or not text.strip(): return
        r = parse_manual(text)
        if r is None: W.QMessageBox.warning(self, tr("Manual entry"), tr("That is not a usable server address.")); return
        self.chosen = dict(name="Manual entry", host=r[0], port=r[1], country="", src="manual"); self.accept()

    def _refresh(self):
        if self.refresh_cb: self.refresh_cb()
        self.count.setText(tr("Downloading the lists…"))


def chosen_name(ctx) -> str:
    """Name of the server in Settings: what was picked (when host and port still match), else what the list calls that address, else the address."""
    s = ctx.store.settings; host, port = str(s.get("dmr_server") or ""), s.get("dmr_port")
    p = s.get("dmr_server_pick") or {}
    if p.get("host") == host and p.get("port") == port and p.get("name"): return p["name"]
    for e in ctx.hosts.dmr_masters():
        if e["host"].lower() == host.lower() and e["port"] == port: return display_name(e)
    return host


def choose_dmr_server(parent, ctx):
    if not ctx.hosts.dmr_masters(): ctx.refresh_hosts(True)
    dlg = DmrServerPicker(parent, ctx.hosts.dmr_masters, str(ctx.store.settings.get("dmr_server") or ""), refresh=lambda: ctx.refresh_hosts(True), hosts_changed=ctx.hosts_changed)
    if dlg.exec() and dlg.chosen: ctx.set_dmr_server(dlg.chosen)
