"""Where recordings are kept. The default is DigiConnect/Recordings in the user's folder; the settings (rec_dir) can change it."""
from pathlib import Path


def recordings_dir(store) -> Path:
    d = (store.settings.get("rec_dir") or "").strip() or str(Path.home() / "DigiConnect" / "Recordings")
    p = Path(d); p.mkdir(parents=True, exist_ok=True); return p
