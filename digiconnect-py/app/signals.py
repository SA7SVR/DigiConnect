"""Short sounds ("signals") for a station that connects or leaves, like every EchoLink program has (the AllStarLink node says it in its own voice): a rising double tone when the station has answered
(Connected) and a falling one when the link ends (Disconnected).

They are played by the protocol engine, with the same audio code as the speaker test and on the speakers chosen in Settings, so nothing in the
program shell is needed. The sounds are DigiConnect's own (two plain sine tones). They are only played for a real event: an EchoLink station that really answered / really went away. The user can turn them off (Settings > Audio: "Play a sound when a station connects or disconnects").
"""
import threading

NETWORKS = ("EchoLink",)          # where a connection is a call to one station, like in every EchoLink program. An AllStarLink node announces the connection itself (its own voice), and the others are servers one stays logged in to
NAMES = ("connected", "disconnected")


def enabled(store) -> bool:
    return bool(store.settings.get("sound_signals", True))


def play(name: str, speakers: str = "", runner=None) -> bool:
    """Plays 'connected' or 'disconnected' in the background. runner(cmd, want, timeout) is audio_devices.probe (given by the tests to avoid sound).
    Returns False when the name is not one of NAMES (nothing is played)."""
    if name not in NAMES: return False
    if runner is None:
        from . import audio_devices
        runner = audio_devices.probe

    def work():
        try: runner({"cmd": "test_spk", "device": speakers or "", "tone": name}, "test_spk", 6.0)
        except Exception: pass
    threading.Thread(target=work, daemon=True).start()
    return True
