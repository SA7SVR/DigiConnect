#!/usr/bin/env python3
"""SHA-256 over the engine's source files (engine/ without its tests). A test compares it with tests/engine_src.sha256:
when engine code changes, ENGINE_VERSION in bootstrap.py must be raised (and engine packages built), then this file is updated:

    python3 tools/engine_src_hash.py --write
"""
import hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "tests" / "engine_src.sha256"


def compute() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "engine").rglob("*")):
        rel = p.relative_to(ROOT / "engine").as_posix()
        if not p.is_file() or rel.startswith("tests/") or "/." in "/" + rel: continue
        h.update(rel.encode() + b"\0"); h.update(p.read_bytes().replace(b"\r\n", b"\n")); h.update(b"\0")
    return h.hexdigest()


if __name__ == "__main__":
    d = compute()
    if "--write" in sys.argv: RECORD.write_text(d + "\n"); print("written", d)
    else: print(d)
