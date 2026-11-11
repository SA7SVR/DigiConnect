"""Automatic update: package validation, install, activation at start-up, rollback of a bad update, and a real download from a local server."""
import os, sys, json, gzip, base64, hashlib, pathlib, subprocess, threading, http.server, functools, shutil
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pytest
import bootstrap
from app import updater as U
from app.qt import QtWidgets as W, QtCore
from app.store import Store


def pkg(version="2.0.1", min_shell="2.0.0", extra=None, bad_py=False, app="digiconnect-py"):
    files = {"app/__init__.py": "", "app/version.py": f'APP_VERSION = "{version}"\n', "assets/x.txt": "hello"}
    if bad_py: files["app/broken.py"] = "def (:\n"
    files.update(extra or {})
    return gzip.compress(json.dumps({"app": app, "format": 2, "version": version, "minShell": min_shell, "files": {k: base64.b64encode(v.encode()).decode() for k, v in files.items()}}).encode())


def test_install_and_activate(tmp_path):
    cur = U.install_package(pkg(), tmp_path)
    assert cur["version"] == "2.0.1" and (tmp_path / "v2.0.1" / "app" / "version.py").is_file()
    assert bootstrap.current(tmp_path)["version"] == "2.0.1"
    before = list(sys.path)
    try:
        assert bootstrap.activate("2.0.0", tmp_path) == "2.0.1" and sys.path[0] == str(tmp_path / "v2.0.1")
    finally: sys.path[:] = before
    assert (tmp_path / "starting").exists()
    bootstrap.started_ok(tmp_path); assert not (tmp_path / "starting").exists()
    # an update that is not newer than the shell is not used
    assert bootstrap.activate("2.0.1", tmp_path) is None


def test_crash_marker_rolls_back(tmp_path):
    U.install_package(pkg(), tmp_path)
    before = list(sys.path)
    try:
        bootstrap.activate("2.0.0", tmp_path)            # first start: marker written, never cleared = crash
        sys.path[:] = before
        assert bootstrap.activate("2.0.0", tmp_path) is None            # second start: update switched off
    finally: sys.path[:] = before
    assert "2.0.1" in json.loads((tmp_path / "bad.json").read_text()) and bootstrap.current(tmp_path) is None


def test_rejects_bad_packages(tmp_path):
    for blob, why in ((pkg(extra={"../evil.py": "x"}), "forbidden"), (pkg(extra={"/abs.py": "x"}), "forbidden"), (pkg(extra={"engine/dcengine": "x"}), "forbidden"),
                      (pkg(bad_py=True), "invalid syntax|broken"), (pkg(app="other"), "not for this"), (b"junk", "not a valid")):
        with pytest.raises(U.UpdateError): U.install_package(blob, tmp_path)
    with pytest.raises(U.UpdateError, match="SHA-256"): U.install_package(pkg(), tmp_path, expect_sha="0" * 64)
    with pytest.raises(U.UpdateError, match="size"): U.install_package(pkg(), tmp_path, expect_size=5)
    assert bootstrap.current(tmp_path) is None              # nothing was activated by a rejected package


def test_min_shell_blocks_activation(tmp_path):
    U.install_package(pkg(min_shell="9.0.0"), tmp_path)
    assert bootstrap.current(tmp_path) is None


def test_overlay_code_really_runs_in_a_new_process(tmp_path):
    big = pkg("2.5.0", extra={"app/marker.py": "WHO = 'overlay'\n"})
    U.install_package(big, tmp_path)
    code = "import sys; sys.path.insert(0, %r); import bootstrap; v = bootstrap.activate('2.0.0'); import app.marker as m; import app.version as ver; print(v, m.WHO, ver.APP_VERSION)" % str(ROOT)
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, env={**os.environ, "DC_UPDATES_DIR": str(tmp_path)}, cwd=str(tmp_path))
    assert out.stdout.strip() == "2.5.0 overlay 2.5.0", out.stderr


@pytest.fixture
def server(tmp_path):
    www = tmp_path / "www"; www.mkdir(); state = {"manifest": {}, "hits": []}
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            state["hits"].append(self.path)
            if self.path.startswith("/manifest.php"):
                body = json.dumps(state["manifest"]).encode(); ct = "application/json"
            else: body = (www / self.path.split("?")[0].lstrip("/")).read_bytes(); ct = "application/octet-stream"
            self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", www, state
    srv.shutdown()


def _wait(app, cond, t=10):
    import time; end = time.time() + t
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if cond(): return True
    return False


def test_download_from_server_end_to_end(tmp_path, server):
    base, www, state = server; app = W.QApplication.instance() or W.QApplication([])
    blob = pkg("2.0.7"); (www / "DigiConnect-2.0.7.dcpkg").write_bytes(blob)
    state["manifest"] = dict(ok=True, checkEvery=3600, state="demo", update="available", version="2.0.7", min_shell="2.0.0", pkg=base + "/DigiConnect-2.0.7.dcpkg",
                             sha256=hashlib.sha256(blob).hexdigest(), size=len(blob))
    (tmp_path / "data").mkdir(); root = tmp_path / "upd"; st = Store(tmp_path / "data"); u = U.Updater(st, root, base + "/manifest.php"); states = []; u.changed.connect(lambda s, m: states.append((s, m)))
    u.check(); assert _wait(app, lambda: u.state == "ready"), states
    assert u.pending == "2.0.7" and bootstrap.current(root)["version"] == "2.0.7" and ("downloading", "2.0.7") in states
    q = state["hits"][0]; assert "id=" in q and f"v={bootstrap.BASE_VERSION}" in q and "shell=2.0.0" in q and "os=" in q
    # next check: the same version is not downloaded again
    n = len(state["hits"]); u.check(); assert _wait(app, lambda: u.state == "uptodate") and not any("DigiConnect-2.0.7" in h for h in state["hits"][n:])
    # a package that needs a newer shell is announced, not installed
    state["manifest"].update(version="3.0.0", min_shell="3.0.0"); u.check(); assert _wait(app, lambda: u.state == "needs_installer") and bootstrap.current(root)["version"] == "2.0.7"
    # a damaged download is rejected and the installed update stays
    state["manifest"].update(version="2.0.8", min_shell="2.0.0", sha256="0" * 64); u.check(); assert _wait(app, lambda: u.state == "error") and bootstrap.current(root)["version"] == "2.0.7"


def test_build_tool_makes_a_valid_package(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "build_dcpkg.py"), "2.3.4", "--out", str(tmp_path)], capture_output=True, text=True); assert out.returncode == 0, out.stderr
    blob = (tmp_path / "DigiConnect-2.3.4.dcpkg").read_bytes(); cur = U.install_package(blob, tmp_path / "root")
    assert cur["version"] == "2.3.4" and 'APP_VERSION = "2.3.4"' in (tmp_path / "root" / "v2.3.4" / "app" / "version.py").read_text()
    assert (tmp_path / "root" / "v2.3.4" / "app" / "updater.py").is_file() and (tmp_path / "root" / "v2.3.4" / "assets" / "logo.png").is_file()


def test_shell_base_version_matches_source_tree():
    from app.version import APP_VERSION
    assert bootstrap.BASE_VERSION == APP_VERSION, "bump bootstrap.BASE_VERSION together with app/version.py when the shell is rebuilt"


def test_run_py_imports_nothing_from_app_before_activate():
    src = (ROOT / "run.py").read_text(); head = src.split("def main")[0]
    assert "import app" not in head and "from app" not in head
