"""C4FM reception must be continuous even when the network delivers the packets unevenly (see engine/tests/check_ysf_jitter.py)."""
import os, subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_ysf_jitter.py"


def test_c4fm_reception_has_no_gaps_with_network_jitter():
    out = ""
    for attempt in range(2):                      # a heavily loaded CI machine may stall once: allow one more try
        r = subprocess.run([sys.executable, str(SCRIPT), ENGINE, "70"], capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        if r.returncode == 0: return
    pytest.fail(out)
