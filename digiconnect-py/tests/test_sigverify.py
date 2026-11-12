"""The pure-Python Ed25519 verifier against the official RFC 8032 test vectors (no PHP needed)."""
import base64
from app import sigverify

V = [  # (public key, message, signature) — RFC 8032 section 7.1, tests 1-3
    ("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("fc51cd8e6218a0a38da47d6e8cd6ca2ec8f7d57c0e4b6e1f1b3f2a1d3f5c28f1", "af82", "00" * 64),   # a wrong signature must be refused
]
b64 = lambda h: base64.b64encode(bytes.fromhex(h)).decode()


def test_rfc8032_vectors():
    for pk, m, sig in V[:2]: assert sigverify.verify(b64(pk), bytes.fromhex(m), b64(sig))


def test_wrong_inputs_are_refused():
    pk, m, sig = V[0]
    assert not sigverify.verify(b64(pk), b"x", b64(sig))                                   # other message
    bad = bytearray(bytes.fromhex(sig)); bad[10] ^= 1
    assert not sigverify.verify(b64(pk), b"", base64.b64encode(bytes(bad)).decode())       # damaged signature
    assert not sigverify.verify(b64(V[1][0]), b"", b64(sig))                               # other key
    for junk in ("", "!!!", "AAAA", b64("00" * 31)): assert not sigverify.verify(junk, b"", b64(sig)) and not sigverify.verify(b64(pk), b"", junk)
    assert not sigverify.verify(b64(*[V[2][0]]), bytes.fromhex(V[2][1]), b64(V[2][2]))
