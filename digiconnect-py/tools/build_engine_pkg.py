#!/usr/bin/env python3
"""Builds the engine package that is uploaded in the DigiConnect panel (Releases > Engine packages).

    python3 tools/build_engine_pkg.py <engine folder> <version> <windows|macos|linux> <x64|arm64> [--out dir]

<engine folder> is the engine exactly as the installer has it: Windows engine_dist/ (dcengine.exe + Qt DLLs), Linux engine_dist/ (bin/dcengine, lib/ ...),
macOS a folder that holds dcengine.app. It writes DigiConnect-engine-<version>-<os>-<arch>.dceng. The program installs it only after it checked size and
hash against the signed offer, the package's own engine.json, the macOS signature and a real test start.
Only needed when engine/ changed (bootstrap.ENGINE_VERSION is then raised); nothing else needs an engine package."""
import argparse, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("folder"); ap.add_argument("version"); ap.add_argument("os", choices=["windows", "macos", "linux"])
    ap.add_argument("arch", choices=["x64", "arm64"]); ap.add_argument("--out", default=str(ROOT / "dist_pkg"))
    a = ap.parse_args()
    if not re.fullmatch(r"\d+(\.\d+)*", a.version): sys.exit("version must look like 2.4.0")
    src = Path(a.folder)
    if not src.is_dir(): sys.exit(f"not a folder: {src}")
    from app import engine_update
    f = engine_update.build_package(src, a.version, a.os, a.arch, Path(a.out))
    print(f"wrote {f} ({f.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
