"""Ed25519 SIGNING (RFC 8032) for tests only — the program itself can only verify. Lets the update tests play the HELLAS Zone server."""
import base64, hashlib
from app import sigverify as S


def _enc(P):
    zi = S._inv(P[2]); x, y = P[0] * zi % S._p, P[1] * zi % S._p
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def keypair(seed: bytes = b"\x07" * 32):
    h = hashlib.sha512(seed).digest(); a = int.from_bytes(h[:32], "little"); a &= (1 << 254) - 8; a |= 1 << 254
    return seed, base64.b64encode(_enc(S._mul(a, S._B))).decode()


def sign(seed: bytes, msg: bytes) -> str:
    h = hashlib.sha512(seed).digest(); a = int.from_bytes(h[:32], "little"); a &= (1 << 254) - 8; a |= 1 << 254
    A = _enc(S._mul(a, S._B)); r = int.from_bytes(hashlib.sha512(h[32:] + msg).digest(), "little") % S._q
    R = _enc(S._mul(r, S._B)); k = int.from_bytes(hashlib.sha512(R + A + msg).digest(), "little") % S._q
    return base64.b64encode(R + ((r + k * a) % S._q).to_bytes(32, "little")).decode()


def signed_update(man: dict, nonce: str, seed: bytes) -> dict:
    """The manifest as the server sends it: plus the signed offer for this request."""
    up = json.dumps({"v": 1, "version": man["version"], "sha256": man["sha256"], "size": man["size"], "min_shell": man.get("min_shell", ""), "n": nonce, "now": 0})
    return dict(man, upd=up, upd_sig=sign(seed, up.encode()))


import json  # noqa: E402
