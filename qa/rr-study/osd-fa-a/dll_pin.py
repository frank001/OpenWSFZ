#!/usr/bin/env python3
"""OSD-FA-A: pinned DLL loader, current binary (Amendment 1 sec.2.1).

Amendment 1 sec.2.1 is explicit: `dll_common.load_decoder()` hard-codes the OLD
`20260046` pin and takes no pin arguments -- do NOT edit that module (a closed arm's
instrument). Construct `LdpcDecodeLLRs` directly with the new pin instead. Everything
else non-pin-specific (the +0.16s waterfall-origin offset, LDPC iteration/OSD-depth
constants, the payload-bit helper) is reused verbatim from `dll_common.py` (HK-018) --
imported here, not copied.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r2-coherent-llr-instrument"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))

from ldpc_decode_ctypes import LdpcDecodeLLRs, FTX_LDPC_N, FTX_LDPC_K, FT8_PAYLOAD_BITS, a91_to_bits  # noqa: E402,F401
import dll_common as DC  # noqa: E402

# Re-exported, unchanged from dll_common (not pin-specific):
extraction_time_offset_s = DC.extraction_time_offset_s
SYMBOL_PERIOD_S = DC.SYMBOL_PERIOD_S
K_LDPC_ITERATIONS = DC.K_LDPC_ITERATIONS
OSD_DEPTH = DC.OSD_DEPTH

# New pin (Amendment 1 sec.2.1) -- the current main binary, same one Part 0's S1/S2 used,
# re-hashed there this session: matches exactly.
PINNED_DLL_SHA256 = "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c"
PINNED_SHIM_VERSION = 20260050
DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")


def load_decoder(verify: bool = True) -> LdpcDecodeLLRs:
    return LdpcDecodeLLRs(
        DLL_PATH, verify=verify,
        expected_sha256=PINNED_DLL_SHA256,
        expected_shim_version=PINNED_SHIM_VERSION,
        check_version=True,
    )
