# DigiConnect (Python / Qt) — HELLAS Zone

Cross-platform digital-voice client (DMR / D-Star / EchoLink / C4FM). Original code; layout and operating
rules follow the HORIZON DIGI CONNECT 1.0.11 manual and screenshots. Branding: DigiConnect / HELLAS Zone.

## Layout
- `app/` — the Qt user interface (PySide6) and the operating rules.
- `engine/` — `dcengine`, the headless C++ protocol engine (Qt6). The UI starts one helper process per link and talks
  to it with JSON lines on stdin/stdout (`app/engine_client.py`). A crash in the engine never freezes the UI.
- `LICENSES/` — GPL-3.0 text and third-party notices. `packaging/` — PyInstaller spec and Windows installer script.

## Build the engine (needs Qt 6, Multimedia + SerialPort)
    cmake -S engine -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --parallel
Windows: build with MinGW (the bundled codec2 uses C99 variable-length arrays). The GitHub workflow does all of this
for Windows, Linux and macOS and bundles the engine next to the app.

## Run from source
    pip install -r requirements.txt
    DC_ENGINE=/path/to/dcengine python run.py        # without DC_ENGINE the UI starts in preview mode

## Tests
    DC_ENGINE=/path/to/dcengine QT_QPA_PLATFORM=offscreen python -m pytest -q tests
    python engine/tests/check_ysf_loopback.py /path/to/dcengine    # engine against a fake YSF reflector

## Status (honest)
Verified here: operating rules, UI, engine connect/transmit/receive/disconnect against a fake YSF reflector, and the UI
driving the real engine end to end (tests). NOT verified here (no radio/network/audio hardware in the build
environment): real audio quality, the real servers, DMR master login, D-Star reflectors (DCS/REF/XRF), EchoLink (not
implemented yet). Server addresses are never guessed: the app asks once for host:port and remembers it (`servers.json`).


## Worldwide server lists (0.3)
DigiConnect downloads the public host files (the same ones Pi-Star / WPSD use) for **YSF reflectors, D-Star REF / XRF / DCS / XLX reflectors and DMR masters**
(`app/hostlists.py`), keeps a copy in the data folder (`hosts.json`, works offline) and refreshes it every 24 h or with the **Refresh** button.
The station directory shows them after the HELLAS Zone entries; selecting one and pressing **Listen** / **Connect (TX)** connects without asking for an address.
Order of address lookup: your own `servers.json` > built-in > downloaded list. DMR masters: **Choose DMR server** in the DMR workspace.
The parsers accept `;`, TAB or blank separated files; entries they cannot read are skipped. EchoLink needs a validated account (not in this build).
