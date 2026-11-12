"""The engine places a correct AllStarLink call (token in the caller name, allstar-public, MD5) - see engine/tests/check_iax_allstar.py."""
import subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_iax_allstar.py"


def test_allstar_call_against_fake_node():
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=90)
    assert r.returncode == 0, r.stdout + r.stderr
