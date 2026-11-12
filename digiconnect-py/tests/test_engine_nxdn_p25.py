"""NXDN / P25: 'connected' only after the reflector answers; an error when nothing answers; received voice is reported - see engine/tests/check_nxdn_p25.py."""
import subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_nxdn_p25.py"


def test_nxdn_and_p25_against_fake_reflectors():
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
