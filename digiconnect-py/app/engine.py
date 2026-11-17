"""Engine interface between the UI/rules and the protocol back-ends.

The UI never talks to DMR/D-Star/YSF/EchoLink directly. A back-end implements Engine.
NullEngine is the honest placeholder: it connects nothing and reports that clearly,
so the UI can never claim a link that does not exist."""
from .rules import Target


class Engine:
    name = "engine"
    def start_rx(self, handle: int, target: Target) -> str: ...
    def stop_rx(self, handle: int) -> None: ...
    def connect_tx(self, target: Target) -> str: ...
    def disconnect_tx(self) -> None: ...
    def ptt(self, on: bool) -> None: ...
    def set_record(self, on: bool, path: str = "") -> None: pass   # recording of the received audio; a no-op without an engine
    def set_mic(self, settings: dict) -> None: pass   # microphone processing (Microphone page); a no-op without an engine
    def mic_level(self) -> float: return 0.0          # the microphone meter: moves only while I am transmitting
    def rx_level(self) -> float: return 0.0           # the level of the received audio: shown on what I am listening to


class NullEngine(Engine):
    name = "none"
    preview = True      # UI preview: the rules run, nothing connects
    def start_rx(self, handle, target): return "No protocol engine connected (UI preview)"
    def stop_rx(self, handle): pass
    def connect_tx(self, target): return "No protocol engine connected (UI preview)"
    def disconnect_tx(self): pass
    def ptt(self, on): pass
