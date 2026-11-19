"""Engine updates: the protocol engine (dcengine, C++) can be replaced by an automatic update, like the Python code - no re-install.

Package (.dceng) = gzip(tar): 'engine.json' {"app":"digiconnect-engine","format":1,"version":"2.4.0","os":"windows|macos|linux","arch":"x64|arm64"}
plus the engine folder exactly as the installer has it (Windows: dcengine.exe + Qt DLLs; Linux: bin/dcengine + lib/ + plugins;
macOS: dcengine.app).

It is installed into <updates>/engine/e<version>/ and never over an existing file (a macOS binary whose signature was changed in place is killed by
the system). <updates>/engine/current.json says which one is used. Before it is switched on the new engine must pass four checks: the package size and
SHA-256 (taken from the part of the offer the server signed), the package's own engine.json (this program, this system), the signature on macOS, and a real
start that answers {"cmd":"hello"}. If a started engine later fails, it is marked bad and the engine of the installer is used again.

Pure standard library: it is used by the updater, by find_engine and by the tests, with or without Qt."""
import gzip, hashlib, io, json, os, platform, posixpath, shutil, subprocess, sys, tarfile, threading
from pathlib import Path
import bootstrap

MAX_PKG = 200 * 1024 * 1024               # the download (a Qt engine with its libraries is a few tens of MB packed)
MAX_UNPACKED = 700 * 1024 * 1024
MAX_FILES = 20000
EXE = "dcengine.exe" if sys.platform.startswith("win") else "dcengine"


class EngineError(Exception): pass


def builtin_version() -> str:
    """Version of the engine that came with the installer (SHELL file bootstrap.py). A shell that does not know it counts as 0, so any engine offer is newer."""
    return str(getattr(bootstrap, "ENGINE_VERSION", "0"))


def host() -> tuple[str, str]:
    """(os, arch) the way the server and the packages name them."""
    m = platform.machine().lower(); arch = "arm64" if m in ("arm64", "aarch64") else ("x64" if m in ("x86_64", "amd64") else m)
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux"), arch


def root_dir(updates: Path | None = None) -> Path:
    return (updates or bootstrap.updates_root()) / "engine"


def exe_in(d: Path) -> str | None:
    """The engine program inside an engine folder (the places the installers put it)."""
    for sub in ("", "engine", "engine/bin", "bin"):
        b = d / sub if sub else d
        for c in (b / EXE, b / "dcengine.app" / "Contents" / "MacOS" / "dcengine"):
            if c.is_file(): return str(c)
    return None


def _read(p: Path, default):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default


def _write(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8"); os.replace(tmp, p)


def current(updates: Path | None = None) -> dict | None:
    """The updated engine that should run: {'version','dir','path'} or None (then the installer's engine is used)."""
    r = root_dir(updates); c = _read(r / "current.json", None)
    if not isinstance(c, dict) or not c.get("version") or not c.get("dir"): return None
    if c["version"] in _read(r / "bad.json", []): return None
    exe = exe_in(r / c["dir"])
    if not exe: return None
    if not bootstrap.newer(str(c["version"]), builtin_version()): return None          # the installer's own engine is as new or newer
    return {"version": str(c["version"]), "dir": str(c["dir"]), "path": exe}


def installed_version(updates: Path | None = None) -> str:
    """The newest engine this installation can use now."""
    c = current(updates)
    return c["version"] if c else builtin_version()


def mark_bad(version: str, updates: Path | None = None):
    r = root_dir(updates); bad = _read(r / "bad.json", [])
    if version not in bad: bad.append(version)
    _write(r / "bad.json", bad)


def prune(keep_dir: str, updates: Path | None = None, keep: int = 2):
    """Keeps the engine in use and the newest other one (so a rollback does not need a download), removes the rest."""
    r = root_dir(updates)
    dirs = sorted([d for d in r.glob("e*") if d.is_dir() and not d.name.endswith(".new")], key=lambda d: bootstrap.vtuple(d.name[1:]), reverse=True)
    n = 0
    for d in dirs:
        if d.name == keep_dir: n += 1; continue
        if n < keep: n += 1; continue
        shutil.rmtree(d, ignore_errors=True)


# ---- unpacking (never trusts the package) ----------------------------------------------------------------------------------
def _clean_name(name: str) -> str:
    n = name.replace("\\", "/")
    if n.startswith("/") or ":" in n or any(p == ".." for p in n.split("/")) or not n.strip("/"):
        raise EngineError(f"forbidden path {name!r}")
    return posixpath.normpath(n)


def _inside(base: Path, p: Path) -> bool:
    try: p.resolve().relative_to(base.resolve()); return True
    except Exception: return False


def read_meta(blob: bytes) -> dict:
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            for m in tf:
                if m.isreg() and _clean_name(m.name) == "engine.json":
                    return json.loads(tf.extractfile(m).read(65536).decode("utf-8"))
    except EngineError: raise
    except Exception: raise EngineError("not a valid engine package")
    raise EngineError("engine package has no engine.json")


def safe_extract(blob: bytes, dest: Path):
    """Unpacks a .dceng into dest: only plain files, folders and symbolic links that stay inside dest; modes reduced to rwxr-xr-x / rw-r--r--."""
    dest.mkdir(parents=True, exist_ok=True)
    total = 0; count = 0
    try:
        tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
    except Exception: raise EngineError("not a valid engine package")
    with tf:
        for m in tf:
            count += 1
            if count > MAX_FILES: raise EngineError("too many files in the engine package")
            name = _clean_name(m.name); target = dest / name
            if not _inside(dest, target.parent): raise EngineError(f"path leaves the engine folder: {name}")
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True); continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if m.issym():
                link = m.linkname.replace("\\", "/")
                if link.startswith("/") or ":" in link: raise EngineError(f"absolute link {name!r}")
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), link))
                if resolved == ".." or resolved.startswith("../"): raise EngineError(f"link leaves the engine folder: {name}")
                if os.name == "nt": raise EngineError("symbolic link in a Windows engine package")
                if target.is_symlink() or target.exists(): target.unlink()
                os.symlink(link, target); continue
            if not m.isreg(): raise EngineError(f"forbidden entry type: {name}")
            total += m.size
            if total > MAX_UNPACKED: raise EngineError("engine package unpacks too large")
            if target.is_symlink() or target.exists(): target.unlink()               # never write into an existing file (macOS signatures)
            src = tf.extractfile(m)
            with open(target, "wb") as f: shutil.copyfileobj(src, f, 1 << 20)
            os.chmod(target, 0o755 if m.mode & 0o111 else 0o644)


# ---- checks -------------------------------------------------------------------------------------------------------------------
def clean_env() -> dict:
    """Environment for the engine: it has its own Qt, so variables that point to another Qt or to the PyInstaller bundle must not reach it."""
    env = dict(os.environ)
    for k in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH", "QT_ROOT_DIR", "QT_DEBUG_PLUGINS",
              "DYLD_FRAMEWORK_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"): env.pop(k, None)
    if getattr(sys, "frozen", False) and "LD_LIBRARY_PATH" in env:
        orig = env.get("LD_LIBRARY_PATH_ORIG")
        if orig: env["LD_LIBRARY_PATH"] = orig
        else: env.pop("LD_LIBRARY_PATH", None)
    return env


def hello(exe: str, timeout: float = 25.0) -> bool:
    """Starts the engine and asks it to say hello (the same check the build pipeline does). True only when it answered."""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0          # no console window flashes up on Windows
        p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=clean_env(), cwd=str(Path(exe).parent), creationflags=flags)
    except Exception: return False
    ok = []
    def reader():
        try:
            line = p.stdout.readline()
            if b'"ev":"hello"' in line.replace(b" ", b""): ok.append(1)
        except Exception: pass
    t = threading.Thread(target=reader, daemon=True); t.start()
    try:
        p.stdin.write(b'{"cmd":"hello"}\n'); p.stdin.flush()
    except Exception: pass
    t.join(timeout)
    try:
        try: p.stdin.write(b'{"cmd":"quit"}\n'); p.stdin.flush(); p.stdin.close()
        except Exception: pass
        try: p.wait(5)
        except Exception: p.kill(); p.wait(5)
    except Exception: pass
    return bool(ok)


def mac_signature_ok(exe: str) -> bool:
    """On macOS the system kills a program whose signature is wrong: check it with the system's own tool before the engine is used."""
    if sys.platform != "darwin": return True
    tool = shutil.which("codesign")
    if not tool: return True
    p = Path(exe)
    bundle = next((a for a in p.parents if a.suffix == ".app"), p)
    try: return subprocess.run([tool, "--verify", "--deep", "--strict", str(bundle)], capture_output=True, timeout=60).returncode == 0
    except Exception: return False


# ---- install ------------------------------------------------------------------------------------------------------------------
def install(blob: bytes, updates: Path | None = None, expect_version: str = "", expect_sha: str = "", expect_size: int = 0,
            os_arch: tuple[str, str] | None = None, on_step=None, check=hello) -> dict:
    """Validates, unpacks and tests an engine package, then switches to it. Returns {'version','dir','path'}. Raises EngineError and changes nothing then."""
    if on_step: on_step("verifying")
    if expect_size and len(blob) != expect_size: raise EngineError("engine size does not match the offer")
    if expect_sha and hashlib.sha256(blob).hexdigest().lower() != expect_sha.lower(): raise EngineError("engine SHA-256 does not match the offer")
    meta = read_meta(blob)
    ver = str(meta.get("version") or "")
    if meta.get("app") != "digiconnect-engine" or meta.get("format") != 1: raise EngineError("package is not an engine for this program")
    if not ver or not all(c.isdigit() or c == "." for c in ver): raise EngineError("engine package has no valid version")
    if expect_version and ver != expect_version: raise EngineError("engine version does not match the offer")
    me = os_arch or host()
    if (meta.get("os"), meta.get("arch")) != me: raise EngineError(f"engine is for {meta.get('os')}/{meta.get('arch')}, this is {me[0]}/{me[1]}")
    if on_step: on_step("installing")
    r = root_dir(updates); dname = "e" + ver; tmp = r / (dname + ".new"); final = r / dname
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        safe_extract(blob, tmp)
        exe = exe_in(tmp)
        if not exe: raise EngineError("the engine program is not in the package")
        if not mac_signature_ok(exe): raise EngineError("the engine's signature is not valid on this Mac")
        if not check(exe): raise EngineError("the new engine did not start")
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True); raise
    shutil.rmtree(final, ignore_errors=True)
    os.replace(tmp, final)
    _write(r / "current.json", {"version": ver, "dir": dname})
    bad = _read(r / "bad.json", [])
    if ver in bad: _write(r / "bad.json", [b for b in bad if b != ver])
    prune(dname, updates)
    return {"version": ver, "dir": dname, "path": exe_in(final)}


def build_package(src_dir: Path, version: str, os_name: str, arch: str, out: Path) -> Path:
    """Packs an engine folder as <out>/DigiConnect-engine-<version>-<os>-<arch>.dceng (used by the build pipeline and the tests)."""
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"DigiConnect-engine-{version}-{os_name}-{arch}.dceng"
    meta = json.dumps({"app": "digiconnect-engine", "format": 1, "version": version, "os": os_name, "arch": arch}).encode()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        ti = tarfile.TarInfo("engine.json"); ti.size = len(meta); ti.mode = 0o644; ti.mtime = 0; tf.addfile(ti, io.BytesIO(meta))
        for p in sorted(src_dir.rglob("*")):
            rel = p.relative_to(src_dir).as_posix()
            if p.is_symlink():
                ti = tarfile.TarInfo(rel); ti.type = tarfile.SYMTYPE; ti.linkname = os.readlink(p); ti.mtime = 0; ti.mode = 0o755; tf.addfile(ti)
            elif p.is_dir():
                ti = tarfile.TarInfo(rel); ti.type = tarfile.DIRTYPE; ti.mode = 0o755; ti.mtime = 0; tf.addfile(ti)
            elif p.is_file():
                ti = tarfile.TarInfo(rel); ti.size = p.stat().st_size; ti.mode = 0o755 if os.access(p, os.X_OK) or p.suffix in (".exe", ".dll") else 0o644; ti.mtime = 0
                with open(p, "rb") as fh: tf.addfile(ti, fh)
    f.write_bytes(gzip.compress(raw.getvalue(), 9, mtime=0))
    return f
