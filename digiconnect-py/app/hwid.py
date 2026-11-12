"""A stable, anonymous identifier of this computer, used to bind a licence to one computer.
Only a salted hash leaves the computer (never the raw machine id, name or MAC address)."""
import hashlib, subprocess, sys, uuid, pathlib

_cache = None


def _raw() -> str:
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        if sys.platform == "darwin":
            out = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                if "IOPlatformUUID" in line: return line.split('"')[-2]
        for f in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            p = pathlib.Path(f)
            if p.is_file() and p.read_text().strip(): return p.read_text().strip()
    except Exception:
        pass
    return "node-%012x" % uuid.getnode()                         # last resort: the network card address (stable on most computers)


def get() -> str:
    """32 hex characters."""
    global _cache
    if _cache is None: _cache = hashlib.sha256(("digiconnect-hw-v1|" + _raw()).encode()).hexdigest()[:32]
    return _cache
