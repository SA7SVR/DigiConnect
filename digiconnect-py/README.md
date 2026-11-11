# DigiConnect (Python / Qt) — HELLAS Zone

Cross-platform digital-voice client (DMR / D-Star / EchoLink / C4FM). Original code; layout and operating
rules follow the HORIZON DIGI CONNECT 1.0.11 manual and screenshots. Branding: DigiConnect / HELLAS Zone.

## Run from source (Windows / macOS / Linux)
    pip install -r requirements.txt
    python run.py

## Tests
    QT_QPA_PLATFORM=offscreen python -m pytest -q tests      # Windows: set QT_QPA_PLATFORM=offscreen

## Layout
- `app/rules.py` — operating rules (Listen vs Connect(TX), single/multiple listening, PTT hold/latch, limit, ducking, validators). No Qt.
- `app/engine.py` — interface the protocol back-ends implement. `NullEngine` is the current placeholder.
- `app/store.py` — settings, favorites (JSON) and QSO journal (SQLite); ADIF/CSV import/export.
- `app/ui/` — main window, workspace, favorites, QSO log, mixer/dock/PTT controls, Settings and New QSO drawers.
- `docs/SPEC.md` — UI inventory and rules distilled from the manual.

## Status (honest)
Working: all pages and controls, rules enforced through the UI (tests), favorites, QSO journal, ADIF/CSV, backup/restore,
profiles, diagnostics, device lists and speaker/microphone tests.
NOT yet working: any real network audio. `NullEngine` connects nothing and says so in the UI. DMR/D-Star/YSF/EchoLink
back-ends, live directories, callbooks, recording, real DTMF, languages other than English, light theme are the next steps.
