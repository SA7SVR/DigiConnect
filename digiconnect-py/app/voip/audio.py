"""Sound card side of a call: the microphone to 20 ms frames at 8000 Hz, and frames from the call to the speakers.

The sound card usually works at 44100 or 48000 Hz, a telephone call at 8000 Hz: a streaming resampler (low-pass filter + interpolation) sits between them.
PortAudio (sounddevice) opens the devices. The device names chosen in Settings come from the protocol engine (Qt), the names of PortAudio can differ a little,
so a name is matched loosely and the system default is used when nothing matches (the program says which device it really uses)."""
import threading
import numpy as np

FRAME = 160
RATE = 8000


def _lowpass(cut: float, taps: int = 81) -> np.ndarray:
    """Windowed-sinc low-pass: cut is the cut-off as a fraction of the sampling rate (0..0.5)."""
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(2 * cut * n) * np.hamming(taps); return (h / h.sum()).astype(np.float32)


class Resampler:
    """Streaming sample-rate conversion; the output does not depend on how the input is cut into blocks."""

    def __init__(self, src: int, dst: int):
        self.src, self.dst = src, dst; self.step = src / dst; self.pos = 0.0; self.skip = 0; self.carry = np.zeros(0, np.float32)
        self.h = _lowpass(0.46 * dst / src) if dst < src else None                      # going down: cut what the lower rate cannot carry (going up needs no filter before the interpolation)
        self.hist = np.zeros(0 if self.h is None else len(self.h) - 1, np.float32)

    def process(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, np.float32)
        if self.src == self.dst: return x
        if self.h is not None:                                                         # going down: remove what the lower rate cannot carry
            ext = np.concatenate([self.hist, x]); x = np.convolve(ext, self.h, mode="valid").astype(np.float32); self.hist = ext[-(len(self.h) - 1):]
        if self.skip:                                                                  # samples of this block that the last block already passed over (the step is larger than 1)
            d = min(self.skip, len(x)); x = x[d:]; self.skip -= d
        buf = np.concatenate([self.carry, x]); n = len(buf)
        if n < 2: self.carry = buf; return np.zeros(0, np.float32)
        last = int(np.floor((n - 1 - self.pos) / self.step))
        if last < 0: self.carry = buf; return np.zeros(0, np.float32)
        p = self.pos + np.arange(last + 1) * self.step; i0 = p.astype(np.int64); fr = (p - i0).astype(np.float32)
        out = buf[i0] * (1 - fr) + buf[np.minimum(i0 + 1, n - 1)] * fr
        nxt = self.pos + (last + 1) * self.step; drop = int(nxt); self.skip = max(0, drop - n); self.carry = buf[drop:]; self.pos = nxt - drop
        return out.astype(np.float32)


def match_device(name: str, devices: list, want_input: bool):
    """Index of the PortAudio device that best fits a name from Settings; None = use the system default. devices = sounddevice.query_devices() as a list of dicts."""
    key = "max_input_channels" if want_input else "max_output_channels"
    cand = [(i, d) for i, d in enumerate(devices) if d.get(key, 0) > 0]
    nm = (name or "").strip().casefold()
    if not nm or nm in ("default", "system default", "—"): return None
    for i, d in cand:
        if d["name"].strip().casefold() == nm: return i
    for i, d in cand:
        dn = d["name"].strip().casefold()
        if nm in dn or dn in nm: return i
    words = [w for w in nm.replace("(", " ").replace(")", " ").split() if len(w) > 2]
    best, score = None, 0
    for i, d in cand:
        dn = d["name"].casefold(); s = sum(1 for w in words if w in dn)
        if words and words[0] in dn and s > score: best, score = i, s              # the first word (Speakers, Microphone, Headset...) must fit: another card of the same maker is not this one
    return best if score >= max(1, len(words) - 1) else None                      # at most one word may differ; otherwise the system default is used, never a guess


class Audio:
    """Starts and stops the sound cards for one call. on_mic(frame) is called every 20 ms with 160 int16 samples; get_speaker() must return the next 160 samples (silence when it has nothing)."""

    def __init__(self, on_mic, get_speaker, mic_name: str = "", spk_name: str = ""):
        self.on_mic, self.get_speaker, self.mic_name, self.spk_name = on_mic, get_speaker, mic_name, spk_name
        self.muted = False; self.mic_level = 0.0; self.spk_level = 0.0; self.in_stream = self.out_stream = None; self.mic_used = self.spk_used = ""; self.error = ""
        self._in_buf = np.zeros(0, np.float32); self._out_fifo = np.zeros(0, np.float32); self._in_rs = self._out_rs = None; self.in_rate = self.out_rate = RATE; self._lock = threading.Lock(); self.volume = 1.0

    # ---- the two callbacks (also called directly by the tests)
    def feed_mic(self, block: np.ndarray):
        """block: float32 mono at the microphone's rate."""
        x = self._in_rs.process(block) if self._in_rs else np.asarray(block, np.float32)
        self._in_buf = np.concatenate([self._in_buf, x])
        while len(self._in_buf) >= FRAME:
            f, self._in_buf = self._in_buf[:FRAME], self._in_buf[FRAME:]
            pcm = np.clip(f * 32768.0, -32768, 32767).astype(np.int16)
            self.mic_level = float(np.sqrt(np.mean((pcm.astype(np.float32) / 32768.0) ** 2)))
            self.on_mic(np.zeros(FRAME, np.int16) if self.muted else pcm)

    def fill_speaker(self, n: int) -> np.ndarray:
        """n float32 samples for the speakers at their rate."""
        while len(self._out_fifo) < n:
            fr = self.get_speaker(); f = np.asarray(fr, np.float32) / 32768.0
            self.spk_level = float(np.sqrt(np.mean(f ** 2)))
            if self._out_rs: f = self._out_rs.process(f)
            self._out_fifo = np.concatenate([self._out_fifo, f * self.volume])
            if len(f) == 0 and self._out_rs and len(self._out_fifo) < n:                      # the converter holds a sample back: ask once more
                continue
        out, self._out_fifo = self._out_fifo[:n], self._out_fifo[n:]
        return out

    # ---- the sound cards
    def _devices(self):
        import sounddevice as sd
        devs = [dict(d) for d in sd.query_devices()]
        return sd, devs, match_device(self.mic_name, devs, True), match_device(self.spk_name, devs, False)

    def _open(self, want_in: bool) -> bool:
        """Opens the microphone (want_in) or the speakers: first at 8000 Hz, else at the card's own rate (the resampler converts)."""
        try: sd, devs, mi, so = self._devices()
        except Exception as ex: self.error = f"Audio is not available ({ex.__class__.__name__}: {ex})"; return False
        idx = mi if want_in else so; errs = []
        try:
            d = sd.default.device[0 if want_in else 1] if idx is None else idx
            used = devs[d]["name"] if isinstance(d, int) and 0 <= d < len(devs) else "default"
        except Exception: used = "default"
        rates = [8000]
        try:
            info = sd.query_devices(idx, "input" if want_in else "output"); rates += [int(info["default_samplerate"]), 48000, 44100]
        except Exception: rates += [48000, 44100]
        seen = []
        for r in [x for x in rates if x not in seen and not seen.append(x)]:
            blk = r // 50
            try:
                if want_in:
                    st = sd.InputStream(device=idx, samplerate=r, channels=1, dtype="float32", blocksize=blk, callback=self._in_callback)
                    self.in_rate = r; self._in_rs = Resampler(r, RATE) if r != RATE else None; self._in_buf = np.zeros(0, np.float32)
                else:
                    st = sd.OutputStream(device=idx, samplerate=r, channels=1, dtype="float32", blocksize=blk, callback=self._out_callback)
                    self.out_rate = r; self._out_rs = Resampler(RATE, r) if r != RATE else None; self._out_fifo = np.zeros(0, np.float32)
                st.start()
                if want_in: self.in_stream, self.mic_used = st, used
                else: self.out_stream, self.spk_used = st, used
                return True
            except Exception as ex: errs.append(f"{r} Hz: {ex}")
        self.error = ("No microphone: " if want_in else "No speakers: ") + (errs[-1] if errs else "")
        return False

    def start_speakers(self) -> bool: return self.out_stream is not None or self._open(False)
    def start_mic(self) -> bool: return self.in_stream is not None or self._open(True)

    def start(self) -> bool:
        a = self.start_speakers(); b = self.start_mic(); return a and b

    def _in_callback(self, indata, frames, t, status):
        try: self.feed_mic(indata[:, 0].copy())
        except Exception: pass

    def _out_callback(self, outdata, frames, t, status):
        try: outdata[:, 0] = self.fill_speaker(frames)
        except Exception: outdata[:] = 0

    def stop(self):
        for s in (self.in_stream, self.out_stream):
            try:
                if s: s.stop(); s.close()
            except Exception: pass
        self.in_stream = self.out_stream = None
