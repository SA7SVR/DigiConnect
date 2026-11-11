#!/usr/bin/env python3
"""Builds the update package that is uploaded in the DigiConnect panel (Releases).

    python3 tools/build_dcpkg.py 2.0.1 [--min-shell 2.0.0] [--out dir]

It writes DigiConnect-<version>.dcpkg: the whole app/ folder + assets/ + LICENSES/ (the same file for Windows, macOS and Linux).
The version is also written into app/version.py inside the package."""
import argparse, base64, gzip, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("version"); ap.add_argument("--min-shell", default="2.0.0"); ap.add_argument("--out", default=str(ROOT / "dist_pkg"))
    a = ap.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", a.version): sys.exit("version must look like 2.0.1")
    files = {}
    for top in ("app", "assets", "LICENSES"):
        for p in sorted((ROOT / top).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"):
                data = p.read_bytes()
                if p.as_posix().endswith("app/version.py"): data = f'"""Version numbers."""\nAPP_VERSION = "{a.version}"\n'.encode()
                files[p.relative_to(ROOT).as_posix()] = base64.b64encode(data).decode()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    blob = gzip.compress(json.dumps({"app": "digiconnect-py", "format": 2, "version": a.version, "minShell": a.min_shell, "files": files}).encode(), 9)
    f = out / f"DigiConnect-{a.version}.dcpkg"; f.write_bytes(blob)
    print(f"wrote {f} ({len(files)} files, {len(blob) // 1024} KB)")


if __name__ == "__main__":
    main()
