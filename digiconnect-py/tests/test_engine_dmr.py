"""The engine logs in to a DMR master the Homebrew/MMDVM way and says at which step a master refused it - see engine/tests/check_dmr_login.py."""
import subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_dmr_login.py"


def test_dmr_login_against_fake_master():
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
