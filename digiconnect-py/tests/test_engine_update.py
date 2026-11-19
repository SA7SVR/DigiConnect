"""Engine updates: the C++ protocol engine comes through the automatic update like the Python code. Package safety, install checks, rollback, the
updater's order (engine first, Python after), the start-up choice of the engine and the fall-back when an updated engine does not start."""
import gzip, hashlib, io, json, os, shutil, subprocess, sys, tarfile, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pytest
import bootstrap
from app import engine_update as EU, updater as U
from app.engine_update import EngineError
import test_updater as TU
from test_updater import pkg, server, _wait, W, QtCore, Store, ES, SEED, PUB       # noqa: F401  (the server fixture and helpers of the updater tests)

HOST = EU.host()
FAKE = EU.EXE


def make_dir(tmp_path, name="eng", body=b"fake engine"):
    d = tmp_path / name; d.mkdir(); (d / FAKE).write_bytes(body); (d / "lib.dat").write_bytes(b"x" * 1000)
    return d


def fake_pkg(tmp_path, version="9.0.0", os_arch=HOST, name="src"):
    return EU.build_package(make_dir(tmp_path, name), version, os_arch[0], os_arch[1], tmp_path / ("out_" + name)).read_bytes()


def raw_tar(entries, meta=None):
    """A .dceng built by hand with arbitrary (also hostile) entries. entries: [(name, kind, data_or_link)]"""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        m = json.dumps(meta or {"app": "digiconnect-engine", "format": 1, "version": "9.0.0", "os": HOST[0], "arch": HOST[1]}).encode()
        ti = tarfile.TarInfo("engine.json"); ti.size = len(m); tf.addfile(ti, io.BytesIO(m))
        for name, kind, d in entries:
            ti = tarfile.TarInfo(name)
            if kind == "file": ti.size = len(d); tf.addfile(ti, io.BytesIO(d))
            elif kind == "sym": ti.type = tarfile.SYMTYPE; ti.linkname = d; tf.addfile(ti)
            elif kind == "hard": ti.type = tarfile.LNKTYPE; ti.linkname = d; tf.addfile(ti)
            elif kind == "dev": ti.type = tarfile.CHRTYPE; tf.addfile(ti)
            elif kind == "fifo": ti.type = tarfile.FIFOTYPE; tf.addfile(ti)
    return gzip.compress(raw.getvalue())


# ---- the package is never trusted ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("entries", [
    [("../evil", "file", b"x")], [("/abs/evil", "file", b"x")], [("a/../../evil", "file", b"x")], [("C:/evil", "file", b"x")],
    [("ok/link", "sym", "../../outside")], [("ok/link", "sym", "/etc/passwd")], [("l", "hard", "x")], [("d", "dev", b"")], [("f", "fifo", b"")],
])
def test_hostile_packages_are_rejected_and_leave_nothing(tmp_path, entries):
    if os.name == "nt" and entries[0][1] == "sym": pytest.skip("symbolic links are not used on Windows")
    blob = raw_tar([(FAKE, "file", b"x")] + entries)
    with pytest.raises(EngineError): EU.install(blob, tmp_path / "upd", check=lambda e: True)
    assert not (tmp_path / "upd" / "engine" / "current.json").exists() and not list((tmp_path / "upd" / "engine").glob("e*")) if (tmp_path / "upd" / "engine").exists() else True
    assert not (tmp_path / "evil").exists() and not (tmp_path.parent / "evil").exists()


def test_a_link_inside_the_folder_is_allowed(tmp_path):
    if os.name == "nt": pytest.skip("symbolic links are not used on Windows")
    blob = raw_tar([(FAKE, "file", b"x"), ("lib/real.so", "file", b"y"), ("lib/real.so.1", "sym", "real.so"), ("bin2", "sym", "lib")])
    cur = EU.install(blob, tmp_path / "upd", check=lambda e: True)
    d = tmp_path / "upd" / "engine" / cur["dir"]
    assert (d / "lib" / "real.so.1").is_symlink() and (d / "lib" / "real.so.1").read_bytes() == b"y"


def test_install_checks_size_hash_meta_system_and_version(tmp_path):
    blob = fake_pkg(tmp_path); up = tmp_path / "upd"; ok = lambda e: True
    with pytest.raises(EngineError, match="size"): EU.install(blob, up, expect_size=5, check=ok)
    with pytest.raises(EngineError, match="SHA-256"): EU.install(blob, up, expect_sha="0" * 64, check=ok)
    with pytest.raises(EngineError, match="does not match the offer"): EU.install(blob, up, expect_version="9.0.1", check=ok)
    other = ("linux", "x64") if HOST[0] != "linux" else ("windows", "x64")
    with pytest.raises(EngineError, match="this is"): EU.install(fake_pkg(tmp_path, os_arch=other, name="o"), up, check=ok)
    with pytest.raises(EngineError, match="not an engine"): EU.install(raw_tar([(FAKE, "file", b"x")], {"app": "other", "format": 1, "version": "9.0.0", "os": HOST[0], "arch": HOST[1]}), up, check=ok)
    with pytest.raises(EngineError, match="valid version"): EU.install(raw_tar([(FAKE, "file", b"x")], {"app": "digiconnect-engine", "format": 1, "version": "9.x", "os": HOST[0], "arch": HOST[1]}), up, check=ok)
    with pytest.raises(EngineError, match="not in the package"): EU.install(raw_tar([("readme.txt", "file", b"x")]), up, check=ok)
    with pytest.raises(EngineError, match="not a valid"): EU.install(b"junk", up, check=ok)
    assert EU.current(up) is None
    cur = EU.install(blob, up, expect_version="9.0.0", expect_sha=hashlib.sha256(blob).hexdigest(), expect_size=len(blob), check=ok)
    assert cur["version"] == "9.0.0" and os.path.isfile(cur["path"])


def test_an_engine_that_does_not_start_is_not_installed(tmp_path):
    up = tmp_path / "upd"
    with pytest.raises(EngineError, match="did not start"): EU.install(fake_pkg(tmp_path), up, check=lambda e: False)
    assert EU.current(up) is None and not list((up / "engine").glob("e*"))                       # not even a half-unpacked folder is left


def test_the_installed_engine_is_never_overwritten_in_place(tmp_path):
    up = tmp_path / "upd"; blob = fake_pkg(tmp_path); EU.install(blob, up, check=lambda e: True)
    first = EU.current(up)["path"]; ino = os.stat(first).st_ino if os.name != "nt" else None
    EU.install(fake_pkg(tmp_path, name="again"), up, check=lambda e: True)                      # the same version again: a new folder replaces the old one
    assert os.path.isfile(EU.current(up)["path"])


def test_newer_than_installer_only_and_bad_engines_are_dropped(tmp_path):
    up = tmp_path / "upd"
    EU.install(fake_pkg(tmp_path, "1.0.0", name="old"), up, check=lambda e: True)
    assert EU.current(up) is None and EU.installed_version(up) == bootstrap.ENGINE_VERSION          # older than the installer's own engine: not used
    EU.install(fake_pkg(tmp_path, "9.0.0"), up, check=lambda e: True)
    assert EU.current(up)["version"] == "9.0.0" and EU.installed_version(up) == "9.0.0" and bootstrap.engine_version(up) == "9.0.0"
    EU.mark_bad("9.0.0", up)
    assert EU.current(up) is None and EU.installed_version(up) == bootstrap.ENGINE_VERSION and bootstrap.engine_version(up) == bootstrap.ENGINE_VERSION
    EU.install(fake_pkg(tmp_path, "9.0.0", name="again"), up, check=lambda e: True)             # a repaired package of the same version is allowed again
    assert EU.current(up)["version"] == "9.0.0"


def test_old_engine_folders_are_pruned(tmp_path):
    up = tmp_path / "upd"
    for v in ("9.0.0", "9.0.1", "9.0.2", "9.0.3"): EU.install(fake_pkg(tmp_path, v, name="s" + v.replace(".", "")), up, check=lambda e: True)
    dirs = sorted(d.name for d in (up / "engine").glob("e*"))
    assert dirs == ["e9.0.2", "e9.0.3"] and EU.current(up)["version"] == "9.0.3"


# ---- the Python update needs the engine it was written for ---------------------------------------------------------------------
def test_python_update_is_switched_off_without_its_engine(tmp_path):
    up = tmp_path / "upd"
    blob = gzip.compress(json.dumps({"app": "digiconnect-py", "format": 2, "version": "2.9.0", "minShell": "2.0.0", "minEngine": "9.0.0",
                                     "files": {"app/__init__.py": "", "app/version.py": "QVBQX1ZFUlNJT04gPSAiMi45LjAiCg=="}}).encode())
    U.install_package(blob, up)
    assert bootstrap.current(up) is None                                                       # needs engine 9.0.0, which is not there
    EU.install(fake_pkg(tmp_path, "9.0.0"), up, check=lambda e: True)
    assert bootstrap.current(up)["version"] == "2.9.0"
    EU.mark_bad("9.0.0", up)                                                                   # the engine fell back to the installer's: the matching Python code goes too
    assert bootstrap.current(up) is None


# ---- the updater: engine first, Python after ----------------------------------------------------------------------------------
def offer(base, www, tmp_path, version="2.9.1", engine="9.0.0", with_eng=True, corrupt=False, wrong_system=False):
    py = pkg(version, extra={}); (www / f"DigiConnect-{version}.dcpkg").write_bytes(py)
    man = dict(ok=True, checkEvery=3600, state="demo", update="available", version=version, min_shell="2.0.0", pkg=f"{base}/DigiConnect-{version}.dcpkg",
               sha256=hashlib.sha256(py).hexdigest(), size=len(py), min_engine=engine)
    if with_eng:
        other = ("linux", "x64") if HOST[0] != "linux" else ("windows", "x64")
        eb = fake_pkg(tmp_path, engine, other if wrong_system else HOST, name="srv" + version.replace(".", ""))
        (www / "eng.dceng").write_bytes(eb)
        man["eng"] = {"version": engine, "sha256": ("0" * 64) if corrupt else hashlib.sha256(eb).hexdigest(), "size": len(eb)}
        man["engine_pkg"] = base + "/eng.dceng"
    return man


def make_updater(tmp_path, base):
    (tmp_path / "data").mkdir(exist_ok=True); st = Store(tmp_path / "data"); root = tmp_path / "upd"
    u = U.Updater(st, root, base + "/manifest.php", pubkeys=[PUB]); u.engine_check = lambda e: True
    return u, root


def test_updater_installs_the_engine_first_then_the_python_code(tmp_path, server):
    base, www, state = server; app = W.QApplication.instance() or W.QApplication([])
    state["manifest"] = offer(base, www, tmp_path); u, root = make_updater(tmp_path, base); states = []; u.changed.connect(lambda s, m: states.append(s))
    u.check(); assert _wait(app, lambda: u.state == "ready"), (u.state, u.message)
    assert EU.current(root)["version"] == "9.0.0" and bootstrap.current(root)["version"] == "2.9.1"
    hits = [h.split("?")[0] for h in state["hits"]]; assert hits.index("/eng.dceng") < hits.index("/DigiConnect-2.9.1.dcpkg")          # the engine came before the Python code
    assert states.count("downloading") == 2 and "installing" in states
    n = len(state["hits"]); state["manifest"] = offer(base, www, tmp_path, "2.9.2")             # next release, same engine: the engine is not downloaded again
    u.check(); assert _wait(app, lambda: u.pending == "2.9.2"), (u.state, u.message)
    assert not any("eng.dceng" in h for h in state["hits"][n:])


@pytest.mark.parametrize("what", ["corrupt", "missing", "wrong_system"])
def test_a_bad_engine_stops_the_whole_update(tmp_path, server, what):
    base, www, state = server; app = W.QApplication.instance() or W.QApplication([])
    state["manifest"] = offer(base, www, tmp_path, with_eng=(what != "missing"), corrupt=(what == "corrupt"), wrong_system=(what == "wrong_system"))
    u, root = make_updater(tmp_path, base); u.check(); assert _wait(app, lambda: u.state == "error"), (u.state, u.message)
    assert "engine" in u.message and EU.current(root) is None and bootstrap.current(root) is None        # neither engine nor Python code was switched on
    assert not any("DigiConnect-2.9.1.dcpkg" in h for h in state["hits"])


def test_the_engine_offer_is_part_of_what_the_server_signed(tmp_path, server):
    base, www, state = server; app = W.QApplication.instance() or W.QApplication([])
    man = offer(base, www, tmp_path)
    state["manifest"] = man; u, root = make_updater(tmp_path, base)
    # an attacker who can alter the unsigned fields cannot swap the engine: the hash that counts is the signed one
    evil = fake_pkg(tmp_path, "9.0.0", name="evil"); (www / "eng.dceng").write_bytes(evil + b"tamper")
    u.check(); assert _wait(app, lambda: u.state == "error"), (u.state, u.message)
    assert EU.current(root) is None


def test_plain_updates_without_an_engine_still_work(tmp_path, server):
    base, www, state = server; app = W.QApplication.instance() or W.QApplication([])
    py = pkg("2.9.3"); (www / "DigiConnect-2.9.3.dcpkg").write_bytes(py)
    state["manifest"] = dict(ok=True, checkEvery=3600, state="demo", update="available", version="2.9.3", min_shell="2.0.0", pkg=f"{base}/DigiConnect-2.9.3.dcpkg", sha256=hashlib.sha256(py).hexdigest(), size=len(py))
    u, root = make_updater(tmp_path, base); u.check(); assert _wait(app, lambda: u.state == "ready"), (u.state, u.message)
    assert bootstrap.current(root)["version"] == "2.9.3" and EU.current(root) is None


# ---- which engine runs, and the way back -----------------------------------------------------------------------------------------
def test_find_engine_prefers_the_updated_one_but_never_over_dc_engine(tmp_path, monkeypatch):
    from app import engine_client as EC
    up = tmp_path / "upd"; monkeypatch.setenv("DC_UPDATES_DIR", str(up))
    EU.install(fake_pkg(tmp_path, "9.0.0"), up, check=lambda e: True); path = EU.current(up)["path"]
    monkeypatch.delenv("DC_ENGINE", raising=False)
    assert EC.find_engine() == path
    monkeypatch.setenv("DC_ENGINE", str(tmp_path / "other"))                                    # tests / developers point at their own engine: that wins
    assert EC.find_engine() != path


def test_an_updated_engine_that_cannot_start_is_dropped_for_good(tmp_path, monkeypatch):
    from app import engine_client as EC
    up = tmp_path / "upd"; monkeypatch.setenv("DC_UPDATES_DIR", str(up)); monkeypatch.delenv("DC_ENGINE", raising=False)
    EU.install(fake_pkg(tmp_path, "9.0.0"), up, check=lambda e: True)
    inst = str(tmp_path / "installer-engine"); monkeypatch.setattr(EC, "builtin_engine", lambda: inst)             # stands for the engine of the installer
    (tmp_path / "data").mkdir(); client = EC.EngineClient(EC.find_engine(), Store(tmp_path / "data")); notes = []; client.notice.connect(notes.append)
    assert client.path == EU.current(up)["path"]
    assert client._updated_engine_failed() is True
    assert EU.current(up) is None and client.path == inst and notes and "went back" in notes[0]
    assert client._updated_engine_failed() is False                                             # the installer's engine is not "an updated engine"
    assert EC.find_engine() == inst                                                             # and the next start does not pick the bad one again


def test_start_up_check_drops_a_damaged_engine(tmp_path, monkeypatch):
    from app import engine_client as EC
    up = tmp_path / "upd"; monkeypatch.setenv("DC_UPDATES_DIR", str(up)); monkeypatch.delenv("DC_ENGINE", raising=False)
    EU.install(fake_pkg(tmp_path, "9.0.0"), up, check=lambda e: True)
    inst = str(tmp_path / "installer-engine"); monkeypatch.setattr(EC, "builtin_engine", lambda: inst)
    (tmp_path / "data").mkdir(); client = EC.EngineClient(EC.find_engine(), Store(tmp_path / "data"))
    monkeypatch.setattr(EU, "hello", lambda exe, timeout=25.0: False)                           # a fake engine cannot answer hello: the same as a spoilt file
    EC.check_updated_engine(client)
    import time; end = time.time() + 10
    while time.time() < end and EU.current(up): time.sleep(0.05)
    assert EU.current(up) is None and EU.installed_version(up) == bootstrap.ENGINE_VERSION and client.path == inst


# ---- the build tools -------------------------------------------------------------------------------------------------------------
def test_build_tools_make_what_the_program_installs(tmp_path):
    d = make_dir(tmp_path, "tool")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_engine_pkg.py"), str(d), "9.1.0", HOST[0], HOST[1], "--out", str(tmp_path / "o")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    cur = EU.install((tmp_path / "o" / f"DigiConnect-engine-9.1.0-{HOST[0]}-{HOST[1]}.dceng").read_bytes(), tmp_path / "upd", expect_version="9.1.0", check=lambda e: True)
    assert os.path.isfile(cur["path"])
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_dcpkg.py"), "2.9.9", "--min-engine", "9.1.0", "--out", str(tmp_path / "p")], capture_output=True, text=True); assert r.returncode == 0, r.stderr
    meta = json.loads(gzip.decompress((tmp_path / "p" / "DigiConnect-2.9.9.dcpkg").read_bytes())); assert meta["minEngine"] == "9.1.0"


def test_the_engine_sources_and_ENGINE_VERSION_move_together():
    sys.path.insert(0, str(ROOT / "tools")); import engine_src_hash as H
    rec = H.RECORD.read_text().strip()
    assert H.compute() == rec, ("The engine sources changed. Raise ENGINE_VERSION in bootstrap.py to the new release, build the engine packages "
                                "(tools/build_engine_pkg.py; the CI does it), then run:  python3 tools/engine_src_hash.py --write")


# ---- the real engine, packed and unpacked like a user's computer does it ----------------------------------------------------------
def _stage_real_engine(tmp_path):
    exe = os.environ.get("DC_ENGINE")
    if not exe or not os.path.isfile(exe): pytest.skip("no real engine (DC_ENGINE)")
    p = pathlib.Path(exe).resolve(); st = tmp_path / "stage"
    app = next((a for a in p.parents if a.suffix == ".app"), None)
    if app: st.mkdir(); shutil.copytree(app, st / app.name, symlinks=True)                     # macOS: the whole dcengine.app (frameworks and links)
    elif p.parent.name == "bin" and (p.parent.parent / "lib").is_dir(): shutil.copytree(p.parent.parent, st, symlinks=True)       # Linux package: bin/ + lib/ ...
    elif (p.parent / "Qt6Core.dll").exists() or sys.platform.startswith("win"): shutil.copytree(p.parent, st)                    # Windows: exe + DLLs
    else: st.mkdir(); shutil.copy2(p, st / p.name)                                              # a single binary built on this machine
    return st


def test_the_real_engine_survives_pack_unpack_and_starts(tmp_path):
    st = _stage_real_engine(tmp_path)
    blob = EU.build_package(st, "9.2.0", HOST[0], HOST[1], tmp_path / "o").read_bytes()
    cur = EU.install(blob, tmp_path / "upd", expect_version="9.2.0")                            # default check = the real test start ({"cmd":"hello"})
    assert EU.hello(cur["path"]) and EU.current(tmp_path / "upd")["path"] == cur["path"]
    if os.name != "nt": assert os.access(cur["path"], os.X_OK)


def test_the_diagnostics_say_which_engine_runs(tmp_path, monkeypatch):
    from app import diagnostics
    up = tmp_path / "upd"; monkeypatch.setenv("DC_UPDATES_DIR", str(up))
    assert f"Engine version: {bootstrap.ENGINE_VERSION} (the installer)" in diagnostics.report()
    EU.install(fake_pkg(tmp_path, "9.0.0"), up, check=lambda e: True)
    assert "Engine version: 9.0.0 (from an update)" in diagnostics.report()
    EU.mark_bad("9.0.0", up)
    r = diagnostics.report(); assert "(the installer)" in r and "dropped after a failed start: 9.0.0" in r
