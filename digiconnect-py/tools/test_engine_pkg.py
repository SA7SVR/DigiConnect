#!/usr/bin/env python3
"""Installs an engine package (.dceng) the way a user's program does - into an empty updates folder - and checks that the installed engine starts
and answers {"cmd":"hello"}. The build pipeline runs this on the very file that goes into the release package.

    python3 tools/test_engine_pkg.py DigiConnect-engine-2.4.0-linux-x64.dceng
Exit code 0 = good."""
import sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    from app import engine_update as E
    f = Path(sys.argv[1]); blob = f.read_bytes(); meta = E.read_meta(blob)
    with tempfile.TemporaryDirectory() as t:
        cur = E.install(blob, Path(t), expect_version=str(meta["version"]))          # size/meta/system checks, signature on macOS, and the real test start
        assert E.current(Path(t)) is not None or str(meta["version"]) == E.builtin_version() or not __import__("bootstrap").newer(str(meta["version"]), E.builtin_version())
        print(f"OK {f.name}: engine {cur['version']} installed and answered hello ({cur['path']})")


if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"FAILED: {type(e).__name__}: {e}"); sys.exit(1)
