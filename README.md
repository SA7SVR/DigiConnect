# DigiConnect — HELLAS Zone Net

Cross-platform digital-voice client for amateur radio: **DMR, D-Star (REF/XRF/DCS), YSF/C4FM (DN & VW), FCS, P25, NXDN, M17, EchoLink/AllStar**, with a built-in software vocoder (no AMBE dongle required). By **SA7SVR (Panagiotis Tsekouras)**, HELLAS Zone Net.

Server/host lists are pulled from **https://hellaszone.com/digiconnect/hosts/pub/**, with the HELLAS Zone reflectors listed first and auto-updated.

## Ready-made downloads
Every push to `main` builds binaries for **Linux, Windows and macOS (Intel + Apple Silicon)** automatically.
- Builds appear under the **Actions** tab → open the latest run → **Artifacts**.
- Tag a version (e.g. `v1.0.0`) and a **Release** with attached files is created automatically.

To start a build by hand: **Actions → Build DigiConnect → Run workflow**.

## Building locally
Requires **Qt ≥ 6.5** (Core, Gui, Multimedia, Network, Quick, QuickControls2, SerialPort). No other external dependencies.

```
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

## Credits & licence
DigiConnect is built on the **DroidStar** engine by Doug McLain (AD8DP) — https://github.com/nostar/DroidStar — and is released under the **GNU General Public License v3** (see `LICENSE`). All original DroidStar copyright notices are retained in the source files. The DigiConnect name, branding and default server configuration are by SA7SVR / HELLAS Zone Net.
