"""Audio devices and the microphone / speaker tests.

Device names, the lists and the tests all come from the protocol engine (dcengine), i.e. from the very same Qt audio code that
transmits and receives. A name chosen here is therefore always found again by the engine. If the engine is not available
(e.g. a UI preview) the PortAudio library (sounddevice) is used instead and the result is marked as such."""
import json, os, queue, subprocess, sys, threading, time

_cache: dict = {"ins": None, "outs": None, "err": "", "src": ""}


def _engine() -> str | None:
    from .engine_client import find_engine
    return find_engine()


def probe(cmd: dict, want: str, timeout: float = 6.0) -> dict | None:
    """Starts a short-lived engine process, sends one command and returns the first event named `want` (None on timeout)."""
    exe = _engine()
    if not exe: return None
    kw = {}
    if sys.platform.startswith("win"): kw["creationflags"] = 0x08000000        # CREATE_NO_WINDOW
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    try:
        p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, **kw)
    except OSError:
        return None
    q: "queue.Queue[dict]" = queue.Queue()
    def rd():
        for line in p.stdout:
            line = line.strip()
            if line.startswith(b"{"):
                try: q.put(json.loads(line))
                except ValueError: pass
    threading.Thread(target=rd, daemon=True).start()
    try:
        p.stdin.write((json.dumps(cmd) + "\n").encode()); p.stdin.flush()
        end = time.time() + timeout
        while time.time() < end:
            try: e = q.get(timeout=0.1)
            except queue.Empty: continue
            if e.get("ev") == want: return e
        return None
    except OSError:
        return None
    finally:
        try: p.stdin.close()
        except OSError: pass
        try: p.kill()
        except OSError: pass


def _sd_lists():
    import sounddevice as sd
    devs = sd.query_devices()
    return [d["name"] for d in devs if d["max_input_channels"] > 0], [d["name"] for d in devs if d["max_output_channels"] > 0]


def list_devices(force: bool = False):
    """(inputs, outputs, error). Cached; force=True asks the system again (the Refresh button)."""
    if not force and _cache["ins"] is not None: return _cache["ins"], _cache["outs"], _cache["err"]
    ins, outs, err, src = [], [], "", ""
    e = probe({"cmd": "devices"}, "devices", 8.0)
    if e is not None:
        ins, outs, src = list(e.get("inputs", [])), list(e.get("outputs", [])), "engine"
    else:
        try: ins, outs = _sd_lists(); src = "portaudio"
        except Exception as ex: err = f"Audio devices unavailable ({ex.__class__.__name__})"
    _cache.update(ins=ins, outs=outs, err=err, src=src)
    try:
        from . import diag; diag.log(f"audio devices ({src or 'none'}): in={ins} out={outs} {err}")
    except Exception: pass
    return ins, outs, err


def test_mic(name: str, ms: int = 1500) -> dict:
    """Records for ~1.5 s from `name` ('' = system default). Returns {ok, peak (0..1), device, msg}."""
    e = probe({"cmd": "test_mic", "device": name, "ms": ms}, "test_mic", ms / 1000 + 6)
    if e is not None:
        e["ok"] = bool(e.get("ok"))
    else:
        try:
            import sounddevice as sd, numpy as np
            a = sd.rec(int(48000 * ms / 1000), samplerate=48000, channels=1, dtype="float32"); sd.wait()
            e = {"ok": True, "peak": float(abs(a).max()), "device": name or "default", "src": "portaudio"}
        except Exception as ex:
            e = {"ok": False, "msg": f"{ex.__class__.__name__}: {ex}"}
    try:
        from . import diag; diag.log(f"mic test: {e}")
    except Exception: pass
    return e


def test_speakers(name: str) -> dict:
    """Plays a short tone on `name` ('' = system default)."""
    e = probe({"cmd": "test_spk", "device": name}, "test_spk", 6.0)
    if e is not None:
        e["ok"] = bool(e.get("ok"))
    else:
        try:
            import sounddevice as sd, numpy as np
            t = np.linspace(0, .6, int(48000 * .6), False); sd.play((0.25 * np.sin(2 * np.pi * 880 * t)).astype("float32"), 48000); sd.wait()
            e = {"ok": True, "device": name or "default", "src": "portaudio"}
        except Exception as ex:
            e = {"ok": False, "msg": f"{ex.__class__.__name__}: {ex}"}
    try:
        from . import diag; diag.log(f"speaker test: {e}")
    except Exception: pass
    return e


def mic_text(r: dict) -> str:
    """One-line result of the microphone test (English source text with fixed templates; translated by the UI)."""
    if not r.get("ok"):
        if r.get("msg"): return f"Microphone test failed: {r['msg']}"
        return "Microphone test failed: no sound received — choose another microphone or allow microphone access in Windows Settings › Privacy › Microphone."
    pk = int(round(float(r.get("peak", 0)) * 100))
    if pk < 2: return f"Microphone test: no signal (peak {pk}%) — speak while testing, choose another microphone, or check that it is not muted."
    if pk < 10: return f"Microphone test: peak level {pk}% — very low, raise the microphone volume."
    return f"Microphone test: peak level {pk}% — OK."
