"""D-Star (REF): the transmitted header carries our callsign, CQCQCQ, reflector+module; the end packet is sent - see engine/tests/check_dstar_ref.py."""
import subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_dstar_ref.py"


def test_dstar_ref_transmit_header_against_fake_reflector():
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
