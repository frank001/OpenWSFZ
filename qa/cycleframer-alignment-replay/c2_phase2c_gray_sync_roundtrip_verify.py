#!/usr/bin/env python3
"""D-001 C.2 Phase 2c, Part B step 1 -- Gray/sync extraction round-trip verification.

(dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md Sec.3 item 1.)

The Architect flagged this unverified (2026-07-26-1830-architect-c2-phase2a-ruling.md
Sec.6): ft8_encode_message returns 79 tone indices; stripping the 21 sync/Costas symbols
and Gray-decoding the remaining 58*3=174 bits SHOULD recover the true 174-bit LDPC
codeword, but this had never been confirmed end to end. This script confirms it,
entirely offline, with NO new native code (matching the Architect's own expectation that
the reference side needs none) -- it re-derives ft8_lib's own Gray map and Costas/sync
symbol layout from the vendored upstream source (C:\\Temp\\ft8_lib_headers\\ft8), which
this machine already has checked out for native builds (see native/ft8_lib_build's
rebuild_shim.bat), and verifies the recovered codeword two independent ways:

  1. CRC-14 check: bits[77:91] of the recovered codeword (the transmitted CRC) must
     equal ftx_compute_crc() re-run over bits[0:77] (payload) zero-extended to 82 bits --
     the exact algorithm ftx_add_crc uses when encoding, reimplemented here from
     C:\\Temp\\ft8_lib_headers\\ft8\\crc.c (not from memory).
  2. LDPC syndrome check: for every one of the 83 parity-check rows in kFTX_LDPC_Nm
     (parsed directly out of C:\\Temp\\ft8_lib_headers\\ft8\\constants.c at runtime --
     not hand-transcribed, to eliminate transcription risk), XOR-ing the codeword bits
     at that row's 1-origin indices must equal 0. A genuine LDPC(174,91) codeword
     satisfies all 83 checks by construction; a corrupted bit-extraction pipeline would
     satisfy them only by chance (~2^-83).

Passing BOTH checks, for multiple distinct messages, is airtight evidence the recovered
174-bit array equals the true codeword -- without reimplementing LDPC encode174 (the
generator-matrix multiply) at all.

NFR-021: only Q-prefix synthetic callsigns used as test messages (ITU-unallocated).
ASCII-only console output per HK-009.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
VENDOR_CONSTANTS_C = r"C:\Temp\ft8_lib_headers\ft8\constants.c"

EXPECTED_SHIM_VERSION = 20260035

FT8_NN = 79          # total channel symbols
FT8_ND = 58          # data symbols
FTX_LDPC_N = 174
FTX_LDPC_K = 91
FTX_LDPC_M = 83
FT8_CRC_POLYNOMIAL = 0x2757
FT8_CRC_WIDTH = 14

# Sync/Costas symbol index ranges (message structure S7 D29 S7 D29 S7 -- constants.h).
SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]


def is_sync_index(i: int) -> bool:
    return any(lo <= i < hi for lo, hi in SYNC_RANGES)


def load_gray_map() -> list[int]:
    """Parse kFT8_Gray_map directly from the vendored constants.c (not transcribed by
    hand) -- eliminates any transcription-error risk in the one table this whole
    verification depends on."""
    with open(VENDOR_CONSTANTS_C, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    m = re.search(r"kFT8_Gray_map\[8\]\s*=\s*\{([^}]*)\}", text)
    if not m:
        raise RuntimeError("kFT8_Gray_map not found in vendored constants.c")
    values = [int(x.strip()) for x in m.group(1).split(",")]
    if len(values) != 8:
        raise RuntimeError(f"kFT8_Gray_map: expected 8 entries, got {len(values)}")
    return values


def load_ldpc_nm() -> list[list[int]]:
    """Parse kFTX_LDPC_Nm[83][7] directly from the vendored constants.c at runtime."""
    with open(VENDOR_CONSTANTS_C, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    m = re.search(r"kFTX_LDPC_Nm\[FTX_LDPC_N\]\[3\]", text)  # sanity anchor, not used directly
    m2 = re.search(r"kFTX_LDPC_Nm\[FTX_LDPC_M\]\[7\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m2:
        raise RuntimeError("kFTX_LDPC_Nm not found in vendored constants.c")
    body = m2.group(1)
    rows = re.findall(r"\{([^}]*)\}", body)
    parsed = [[int(x.strip()) for x in row.split(",")] for row in rows]
    if len(parsed) != FTX_LDPC_M:
        raise RuntimeError(f"kFTX_LDPC_Nm: expected {FTX_LDPC_M} rows, got {len(parsed)}")
    return parsed


def ftx_compute_crc(message_bytes: bytes, num_bits: int) -> int:
    """Direct port of ftx_compute_crc from C:\\Temp\\ft8_lib_headers\\ft8\\crc.c."""
    topbit = 1 << (FT8_CRC_WIDTH - 1)
    remainder = 0
    idx_byte = 0
    for idx_bit in range(num_bits):
        if idx_bit % 8 == 0:
            remainder ^= (message_bytes[idx_byte] << (FT8_CRC_WIDTH - 8))
            idx_byte += 1
        if remainder & topbit:
            remainder = ((remainder << 1) ^ FT8_CRC_POLYNOMIAL) & 0xFFFF
        else:
            remainder = (remainder << 1) & 0xFFFF
    return remainder & ((topbit << 1) - 1)


def bits_to_bytes(bits: list[int]) -> bytes:
    """MSB-first bit-list -> byte array, zero-padded to a whole number of bytes."""
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i // 8] |= 0x80 >> (i % 8)
    return bytes(out)


def recover_codeword(tones: list[int], inv_gray: list[int]) -> list[int]:
    """Strip the 21 sync/Costas symbols, Gray-decode the 58 remaining data symbols
    (3 bits each, MSB-first) -> 174-bit codeword, in the SAME order ft8_lib's own
    ft8_extract_likelihood (patched/ft8/decode.c) and encode.c's ft8_encode both use
    (data-symbol index k = 0..57, bit_idx = 3*k)."""
    data_tones = [t for i, t in enumerate(tones) if not is_sync_index(i)]
    assert len(data_tones) == FT8_ND, f"expected {FT8_ND} data tones, got {len(data_tones)}"
    bits: list[int] = []
    for tone in data_tones:
        bits3 = inv_gray[tone]  # 0..7, MSB-first 3-bit value (matches encode.c's bits3)
        bits.append((bits3 >> 2) & 1)
        bits.append((bits3 >> 1) & 1)
        bits.append(bits3 & 1)
    assert len(bits) == FTX_LDPC_N
    return bits


def verify_message(encode_message, message: str, gray_map: list[int], inv_gray: list[int],
                    ldpc_nm: list[list[int]]) -> bool:
    tones_buf = (ctypes.c_uint8 * FT8_NN)()
    rc = encode_message(message.encode("ascii"), tones_buf, FT8_NN)
    if rc != FT8_NN:
        print(f"  [FAIL] ft8_encode_message('{message}') returned {rc}, expected {FT8_NN}")
        return False
    tones = list(tones_buf)

    codeword = recover_codeword(tones, inv_gray)

    # -- Check 1: CRC-14 --
    a91_bits = codeword[0:91]
    extracted_crc = 0
    for b in a91_bits[77:91]:
        extracted_crc = (extracted_crc << 1) | b

    payload_82 = a91_bits[0:77] + [0] * 5  # zero-extend 77 -> 82 bits, per ftx_add_crc
    payload_bytes = bits_to_bytes(payload_82)
    computed_crc = ftx_compute_crc(payload_bytes, 82)

    crc_ok = (extracted_crc == computed_crc)

    # -- Check 2: LDPC syndrome (all 83 parity checks must XOR to 0) --
    syndrome_ok = True
    bad_rows = 0
    for row in ldpc_nm:
        acc = 0
        for one_indexed in row:
            if one_indexed == 0:
                continue  # 0 is padding, not a real 1-origin index
            acc ^= codeword[one_indexed - 1]
        if acc != 0:
            syndrome_ok = False
            bad_rows += 1

    status = "PASS" if (crc_ok and syndrome_ok) else "FAIL"
    print(f"  [{status}] '{message}': CRC {'OK' if crc_ok else 'MISMATCH'} "
          f"(extracted={extracted_crc:04x} computed={computed_crc:04x}); "
          f"LDPC syndrome {'ALL-ZERO (83/83)' if syndrome_ok else f'{83 - bad_rows}/83 zero'}")
    return crc_ok and syndrome_ok


def main() -> None:
    print(f"Loading DLL: {DLL_PATH}")
    dll = ctypes.CDLL(os.path.abspath(DLL_PATH))

    dll.ft8_lib_version_check.restype = ctypes.c_int
    version = dll.ft8_lib_version_check()
    print(f"ft8_lib_version_check() = {version} (expected {EXPECTED_SHIM_VERSION})")
    if version != EXPECTED_SHIM_VERSION:
        print("[WARN] shim version mismatch -- rebuild libft8.dll before trusting this result.")

    dll.ft8_encode_message.restype = ctypes.c_int
    dll.ft8_encode_message.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]

    gray_map = load_gray_map()
    print(f"kFT8_Gray_map (from vendored constants.c) = {gray_map}")
    inv_gray = [0] * 8
    for i, v in enumerate(gray_map):
        inv_gray[v] = i
    print(f"inverse Gray map (tone -> bits3)           = {inv_gray}")

    ldpc_nm = load_ldpc_nm()
    print(f"kFTX_LDPC_Nm (from vendored constants.c): {len(ldpc_nm)} rows (expected {FTX_LDPC_M})\n")

    # NFR-021: Q-prefix synthetic callsigns only (ITU-unallocated).
    test_messages = [
        "CQ Q1TST JO33",
        "Q1TST Q2FZW JO33",
        "Q2FZW Q1TST -12",
        "Q1TST Q2FZW R-08",
        "Q2FZW Q1TST RR73",
        "Q1TST Q2FZW 73",
    ]

    print("Round-trip verification (encode -> strip sync -> Gray-decode -> CRC + LDPC syndrome):")
    results = [verify_message(dll.ft8_encode_message, m, gray_map, inv_gray, ldpc_nm)
               for m in test_messages]

    print()
    if all(results):
        print(f"[VERDICT] Gray/sync extraction round-trips CORRECTLY for all {len(results)} "
              f"test messages (CRC-14 match AND all 83 LDPC parity checks satisfied, every "
              f"message). Safe to use for the BER measurement's true-codeword recovery.")
    else:
        n_fail = sum(1 for r in results if not r)
        print(f"[VERDICT] {n_fail}/{len(results)} messages FAILED round-trip verification. "
              f"DO NOT use this path for the BER measurement -- fall back to the native "
              f"codeword export from inside ft8_encode_message (dev-task Sec.3 item 1's "
              f"named fallback) instead.")
        sys.exit(1)


if __name__ == "__main__":
    main()
