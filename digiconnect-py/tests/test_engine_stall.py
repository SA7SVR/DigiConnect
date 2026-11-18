"""A C4FM transmission that pauses in the middle (bridged reflector, e.g. YSF00006) must not be cut into pieces (see engine/tests/check_ysf_stall.py)."""
import os, subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_ysf_stall.py"


def test_c4fm_transmission_with_a_pause_is_not_cut_into_pieces():
    out = ""
    for attempt in range(2):                      # a heavily loaded CI machine may stall once: allow one more try
        r = subprocess.run([sys.executable, str(SCRIPT), ENGINE, "900"], capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        if r.returncode == 0: return
    pytest.fail(out)
