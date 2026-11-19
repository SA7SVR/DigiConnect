"""The engine logs in to BrandMeister with the Rewind (Open DMR Terminal) protocol: challenge/SHA-256, talkgroup subscription, voice both ways - see engine/tests/check_dmr_rewind.py."""
import subprocess, sys, pathlib, pytest
from app.engine_client import find_engine

ENGINE = find_engine()
pytestmark = pytest.mark.skipif(not ENGINE, reason="dcengine not built (set DC_ENGINE)")
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "engine" / "tests" / "check_dmr_rewind.py"


def test_rewind_login_and_voice_against_fake_brandmeister():
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="MALLOC_PERTURB_ is glibc")
@pytest.mark.parametrize("fill", ["167", "85"])
def test_rewind_header_does_not_depend_on_uninitialised_memory(fill):
    """Fresh heap memory is filled with a non-zero byte (glibc MALLOC_PERTURB_), like any platform may hand it out: the first transmit used an
    uninitialised group/private-call flag (byte 0 of the voice header was 0xA7 on the macOS Intel CI runner, 2.3.11)."""
    import os
    env = dict(os.environ, MALLOC_PERTURB_=fill)
    r = subprocess.run([sys.executable, str(SCRIPT), ENGINE], capture_output=True, text=True, timeout=180, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
