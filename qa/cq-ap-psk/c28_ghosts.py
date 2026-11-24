"""CQ-AP-PSK: c28 -> callsign unpack and its round-trip proof against ft8_lib (via libft8.dll ft8_encode_message).
Constants are asserted in code (HK: inherited constants as assertions). No real callsigns are produced or stored."""
import ctypes, numpy as np

NTOKENS = 2063592
MAX22 = 4194304
N_STD = 37 * 36 * 10 * 27 * 27 * 27
N28_LO = NTOKENS + MAX22
N28_HI = 2**28 - 1
assert N_STD == 262177560 and N28_LO == 6257896 and N28_LO + N_STD == 2**28 and N28_HI - N28_LO + 1 == N_STD
A1 = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"   # 37
A2 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"    # 36
A3 = "0123456789"                              # 10
A4 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"             # 27
assert (len(A1), len(A2), len(A3), len(A4)) == (37, 36, 10, 27)
GRAY = (0, 1, 3, 2, 5, 6, 4, 7)                # kFT8_Gray_map, constants.c:13
GRAY_INV = {t: b for b, t in enumerate(GRAY)}
COSTAS_SPANS = (range(0, 7), range(36, 43), range(72, 79))

def unpack_std(n28: int) -> str:
    """Inverse of pack_basecall for a standard-range c28 (message.c:616 / :715). Returns the raw 6-char field."""
    assert N28_LO <= n28 <= N28_HI
    n = n28 - N28_LO
    n, i6 = divmod(n, 27); n, i5 = divmod(n, 27); n, i4 = divmod(n, 27)
    n, i3 = divmod(n, 10); n, i2 = divmod(n, 36); i1 = n
    assert i1 < 37
    return A1[i1] + A2[i2] + A3[i3] + A4[i4] + A4[i5] + A4[i6]

def draw_n28(rng: "np.random.Generator", count: int):
    return rng.integers(N28_LO, N28_HI + 1, size=count, dtype=np.int64)

def load_dll(path):
    d = ctypes.CDLL(path)
    d.ft8_encode_message.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    d.ft8_encode_message.restype = ctypes.c_int
    return d

def encode_c28(dll, text: str):
    """ft8_encode_message -> 79 tones -> 77 payload bits; returns (n28_of_second_call, ip) or None (cannot be packed)."""
    buf = ctypes.create_string_buffer(79)
    rc = dll.ft8_encode_message(text.encode("ascii"), buf, 79)
    if rc != 79: return None
    tones = list(buf.raw)
    bits = []
    for i, t in enumerate(tones):
        if any(i in r for r in COSTAS_SPANS): continue
        b = GRAY_INV[t]
        bits += [(b >> 2) & 1, (b >> 1) & 1, b & 1]
    pay = bits[:77]                              # systematic code: first 77 of the 174 bits are the payload
    n28 = int("".join(map(str, pay[29:57])), 2)
    return n28, pay[57]

def roundtrip(dll, n28s):
    """For each drawn n28: unpack, trim, encode 'CQ <call> AA00' with ft8_lib, read c28 back. Returns (ok, unpackable, total)."""
    ok = unpackable = 0
    bad = []
    for n in n28s:
        call = unpack_std(int(n)).strip()
        r = encode_c28(dll, f"CQ {call} AA00") if call and " " not in call else None
        if r is None: continue
        unpackable += 1
        if r[0] == int(n) and r[1] == 0: ok += 1
        else: bad.append(int(n))
    return ok, unpackable, len(n28s), bad
