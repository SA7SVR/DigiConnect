"""HTTPS helper: uses the certifi CA bundle when present (a packaged program on macOS has no system certificate store)."""
import ssl, urllib.request


def context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def get(url: str, timeout: int = 15, limit: int = 8 * 1024 * 1024, ua: str = "DigiConnect (HELLAS Zone)", progress=None) -> bytes:
    """Downloads url. progress(done_bytes, total_bytes_or_0) is called while the data arrives (optional)."""
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout, context=context()) as r:
        if progress is None: data = r.read(limit + 1)
        else:
            try: total = int(r.headers.get("Content-Length") or 0)
            except ValueError: total = 0
            buf = bytearray()
            while True:
                chunk = r.read(64 * 1024)
                if not chunk: break
                buf += chunk
                if len(buf) > limit: break
                progress(len(buf), total)
            data = bytes(buf)
    if len(data) > limit: raise ValueError("file too large")
    return data
