"""G.711 (ITU-T G.711, RFC 3551): mu-law (PCMU) and A-law (PCMA) with numpy, 8000 samples per second, 16-bit linear on the program side."""
import numpy as np

_BIAS, _CLIP = 0x84, 32635


def _ulaw_decode_table() -> np.ndarray:
    t = np.zeros(256, np.int16)
    for i in range(256):
        u = ~i & 0xFF; sign = u & 0x80; exp = (u >> 4) & 7; man = u & 0x0F
        s = ((man << 3) + _BIAS) << exp; s -= _BIAS
        t[i] = -s if sign else s
    return t


def _alaw_decode_table() -> np.ndarray:
    t = np.zeros(256, np.int16)
    for i in range(256):
        a = i ^ 0x55; sign = a & 0x80; exp = (a >> 4) & 7; man = a & 0x0F
        s = (man << 4) + 8 if exp == 0 else ((man << 4) + 0x108) << (exp - 1)
        t[i] = s if sign else -s
    return t


ULAW_DEC, ALAW_DEC = _ulaw_decode_table(), _alaw_decode_table()


def _segment(v: np.ndarray, ends) -> np.ndarray:
    seg = np.full(v.shape, 8, np.int32)
    for k in range(7, -1, -1): seg = np.where(v <= ends[k], k, seg)
    return seg


_ULAW_END = [0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF]
_ALAW_END = [0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF]


def ulaw_encode(pcm: np.ndarray) -> bytes:
    """ITU-T G.711 mu-law: the 16-bit sample is cut to 14 bits (>> 2), biased by 33, and coded as segment + 4-bit step."""
    x = np.asarray(pcm, np.int32) >> 2
    mask = np.where(x < 0, 0x7F, 0xFF); x = np.minimum(np.abs(x), 8159) + 33
    seg = _segment(x, _ULAW_END)
    u = np.where(seg >= 8, 0x7F ^ mask, ((seg << 4) | ((x >> (seg + 1)) & 0x0F)) ^ mask)
    return u.astype(np.uint8).tobytes()


def alaw_encode(pcm: np.ndarray) -> bytes:
    """ITU-T G.711 A-law: the 16-bit sample is cut to 13 bits (>> 3), coded as segment + 4-bit step, every other bit inverted (0x55)."""
    x = np.asarray(pcm, np.int32) >> 3
    mask = np.where(x >= 0, 0xD5, 0x55); x = np.where(x < 0, -x - 1, x)
    seg = _segment(x, _ALAW_END)
    a = np.where(seg >= 8, 0x7F ^ mask, ((seg << 4) | np.where(seg < 2, (x >> 1) & 0x0F, (x >> np.maximum(seg, 1)) & 0x0F)) ^ mask)
    return a.astype(np.uint8).tobytes()


def decode(payload: bytes, pt: int) -> np.ndarray:
    a = np.frombuffer(payload, np.uint8)
    return (ULAW_DEC if pt == 0 else ALAW_DEC)[a]


def encode(pcm: np.ndarray, pt: int) -> bytes:
    return ulaw_encode(pcm) if pt == 0 else alaw_encode(pcm)
