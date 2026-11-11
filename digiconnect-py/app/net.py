"""HTTPS helper: uses the certifi CA bundle when present (a packaged program on macOS has no system certificate store)."""
import ssl, urllib.request


def context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def get(url: str, timeout: int = 15, limit: int = 8 * 1024 * 1024, ua: str = "DigiConnect (HELLAS Zone)") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout, context=context()) as r:
        data = r.read(limit + 1)
    if len(data) > limit: raise ValueError("file too large")
    return data
