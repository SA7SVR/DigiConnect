"""The engine logs in to BrandMeister with the Rewind (Open DMR Terminal) protocol: challenge/SHA-256, talkgroup subscription, voice both ways - see engine/tests/check_dmr_rewind.py."""
import subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_dmr_rewind.py"


def test_rewind_login_and_voice_against_fake_brandmeister():
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
