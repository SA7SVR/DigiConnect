"""Ed25519 signature check (RFC 8032) in pure Python — so the program can verify the licence answer of the server with only the public key
and without any extra package. Only verification is implemented (the private key never leaves the server)."""
import base64, hashlib

_p = 2**255 - 19
_q = 2**252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _inv(x: int) -> int: return pow(x, _p - 2, _p)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_p + 3) // 8, _p)
    if (x * x - xx) % _p != 0: x = x * _I % _p
    return _p - x if x % 2 != 0 else x


_By = 4 * _inv(5) % _p
_B = (_xrecover(_By), _By, 1, _xrecover(_By) * _By % _p)
_ZERO = (0, 1, 1, 0)


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p; B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p; D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s: int, P):
    Q = _ZERO
    while s > 0:
        if s & 1: Q = _add(Q, P)
        P = _add(P, P); s >>= 1
    return Q


def _eq(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _decode(s: bytes):
    if len(s) != 32: return None
    y = int.from_bytes(s, "little"); sign = y >> 255; y &= (1 << 255) - 1
    if y >= _p: return None
    x = _xrecover(y)
    if x == 0 and sign: return None
    if x & 1 != sign: x = _p - x
    P = (x, y, 1, x * y % _p)
    if (-P[0] * P[0] + P[1] * P[1] - 1 - _d * P[0] * P[0] * P[1] * P[1]) % _p != 0: return None
    return P


def verify(public_b64: str, message: bytes, sig_b64: str) -> bool:
    """True only when `sig_b64` is a valid Ed25519 signature of `message` made with the private key of `public_b64`."""
    try:
        pk = base64.b64decode(public_b64, validate=True); sig = base64.b64decode(sig_b64, validate=True)
        if len(pk) != 32 or len(sig) != 64: return False
        A = _decode(pk); R = _decode(sig[:32]); S = int.from_bytes(sig[32:], "little")
        if A is None or R is None or S >= _q: return False
        h = int.from_bytes(hashlib.sha512(sig[:32] + pk + message).digest(), "little") % _q
        return _eq(_mul(S, _B), _add(R, _mul(h, A)))
    except Exception:
        return False
