# DigiConnect — HELLAS Zone (Python/Qt + C++ engine)

Digital-voice client for radio amateurs: DMR, D-STAR, C4FM/YSF, NXDN, P25, M17 (EchoLink is prepared, not connected yet).

## Layout
- `app/` — the user interface (PySide6) and the operating rules (`rules.py`).
- `engine/` — `dcengine`, the headless C++ protocol engine (Qt 6). The UI starts one helper process per link and talks to it
  with JSON lines on stdin/stdout (`app/engine_client.py`). A crash in the engine never freezes the UI.
- `bootstrap.py`, `app/updater.py`, `tools/build_dcpkg.py` — automatic updates without re-installing (`docs/UPDATES.md`).
- `packaging/` — PyInstaller spec, Windows installer (Inno Setup, Greek + English) with its images and texts.
- `LICENSES/` — GPL-3.0 text and third-party notices.

## Servers
Servers come from public lists (the same host files Pi-Star / WPSD use, plus the BrandMeister talkgroup list), downloaded by
`app/hostlists.py`, stored in the data folder (`hosts.json`, works offline) and refreshed every 24 h or from Settings.
Nothing is invented: if a list could not be downloaded, Settings › Server lists shows which one and why.
For every station the host and port of its server are shown and can be overridden (and reset to the list value).
Lookup order: your own override > built-in > downloaded list. What the program really did is written to `digiconnect.log`.

## Build the engine (Qt 6 with Multimedia and SerialPort)
    cmake -S engine -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --parallel
Windows: MinGW (the bundled codec2 needs C99 variable-length arrays). The GitHub workflow builds the engine and the app for
Windows, Linux and macOS (Intel + Apple Silicon).

## Run from source
    pip install -r requirements.txt
    DC_ENGINE=/path/to/dcengine python run.py        # without DC_ENGINE the UI starts in preview mode

## Tests
    DC_ENGINE=/path/to/dcengine QT_QPA_PLATFORM=offscreen python -m pytest -q tests
    python engine/tests/check_ysf_loopback.py /path/to/dcengine    # engine against a fake YSF reflector

## What is verified and what is not
Verified by tests: operating rules, UI, the engine connecting/transmitting/receiving against a fake YSF reflector, the UI driving
the real engine, list parsers, updater (real local HTTP download with progress), installer (compiled and run).
Not verifiable in the build environment: real audio hardware and levels, the real public servers, DMR master login
(needs your DMR ID and the master password), real radios.
