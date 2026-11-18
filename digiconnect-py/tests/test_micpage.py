"""Microphone page: its settings must never collide with the capture-device name that the audio block keeps under settings['mic']
(a Windows user crashed at start: the device name is a string, the page read it as a dictionary)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.ui.micpage import MicPage


class _Sig:
    def emit(self, *a): self.last = a


class _Store:
    def __init__(self, settings): self.settings = settings; self.saved = 0
    def save_settings(self): self.saved += 1


class _Eng:
    preview = True
    def __init__(self): self.sent = []
    def set_mic(self, d): self.sent.append(dict(d))


class _Ctx:
    def __init__(self, settings): self.store = _Store(settings); self.engine = _Eng(); self.toast = _Sig()
    def ptt_down(self, latch=False): pass
    def ptt_up(self): pass


def test_device_name_in_settings_does_not_crash_and_survives_save():
    ctx = _Ctx({"mic": "Microphone (Realtek High Definition Audio)", "speakers": "Speakers"})
    page = MicPage(ctx)                                    # used to raise ValueError: dictionary update sequence element #0 has length 1
    assert ctx.engine.sent and ctx.engine.sent[-1]["gain"] == 0
    page.sliders["gain"].setValue(6); page._save()
    assert ctx.store.settings["mic"] == "Microphone (Realtek High Definition Audio)"      # the capture device is untouched
    assert ctx.store.settings["mic_fx"]["gain"] == 6 and ctx.store.saved == 1


def test_values_are_restored_from_mic_fx():
    ctx = _Ctx({"mic": "USB Mic", "mic_fx": {"gain": 4, "bass": -3, "highpass": 100}})
    page = MicPage(ctx)
    assert page.sliders["gain"].value() == 4 and page.sliders["bass"].value() == -3


def test_old_build_saved_the_values_under_mic_they_are_moved():
    ctx = _Ctx({"mic": {"gain": 5, "bass": 2, "highpass": 0}})
    page = MicPage(ctx)
    assert page.sliders["gain"].value() == 5 and "mic" not in ctx.store.settings and ctx.store.settings["mic_fx"]["gain"] == 5


def test_unknown_or_broken_values_are_ignored():
    ctx = _Ctx({"mic_fx": ["a", "b"]}); MicPage(ctx)
    ctx = _Ctx({"mic_fx": {"gain": 3, "evil": 1}}); p = MicPage(ctx); assert p.sliders["gain"].value() == 3
