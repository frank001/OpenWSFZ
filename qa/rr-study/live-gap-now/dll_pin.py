#!/usr/bin/env python3
"""LIVE-GAP-NOW leg definitions and pinned-decoder loader.

Spec: qa/rr-study/2026-09-12-1721-architect-to-qa-spec-live-gap-now-current-binary-live-recovery.md
      section 2 (Legs) and ROW 0a/0b.

Reuses (HK-018, spec's own "reused, not rebuilt" table):
  qa/cycleframer-alignment-replay/p23_common.py: Decoder (ctypes, SHA-asserted),
  read_wav(), normalise_rms().

Each leg's DLL is a distinct-filename copy extracted from its git blob (§2's
"Extract the L08 blob and pin both DLLs" step), never the tracked native tree --
no rebuild, no HK-011 Developer session.
"""
from __future__ import annotations

import ctypes
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))

import p23_common  # noqa: E402

BIN_DIR = os.path.join(REPO_ROOT, "artefacts", "live-gap-now", "bin")

# leg -> (dll filename, sha256, shim version, (k, corr, nhard))
LEGS = {
    "L08": (
        "libft8_L08_20260033.dll",
        "f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015",
        20260033,
        (10, 0.10, 60),
    ),
    "NOW": (
        "libft8_NOW_20260050.dll",
        "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c",
        20260050,
        (10, 0.10, 60),
    ),
    "NOW40": (
        "libft8_NOW_20260050.dll",  # same binary as NOW (§2 table)
        "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c",
        20260050,
        (10, 0.10, 40),
    ),
}


def load_leg(leg: str) -> "p23_common.Decoder":
    """Load ROW 0a-verified decoder for `leg`, with leg-specific decode params.

    Returns a p23_common.Decoder whose ft8_set_decode_params has been (re-)called
    with this leg's own (k, corr, nhard) -- p23_common's own module-level
    DECODE_PARAMS constant is (10, 0.10, 60) and is NOT what NOW40 needs, so we
    call ft8_set_decode_params again after construction (the shim's own contract:
    "values take effect on the next ft8_decode_all call", ft8_shim.h).
    """
    fname, sha256, shim, params = LEGS[leg]
    path = os.path.join(BIN_DIR, fname)
    dec = p23_common.Decoder(
        path=path,
        verify=True,
        expected_sha256=sha256,
        expected_shim_version=shim,
        check_version=True,
    )
    k, corr, nhard = params
    dec.dll.ft8_set_decode_params(k, ctypes.c_float(corr), nhard)
    return dec


def row0a(leg: str) -> dict:
    """ROW 0a: SHA-256 of the loaded file == pin, AND version_check() through the
    loaded handle == pin. Returns a dict recording both checks; raises on VOID."""
    fname, sha256, shim, _ = LEGS[leg]
    path = os.path.join(BIN_DIR, fname)
    got_sha = p23_common.dll_sha256(path)
    if got_sha != sha256:
        raise RuntimeError("ROW 0a VOID (%s): sha256 mismatch, got %s want %s" % (leg, got_sha, sha256))
    dec = load_leg(leg)  # raises internally on sha/version mismatch too (belt+braces)
    if dec.version != shim:
        raise RuntimeError("ROW 0a VOID (%s): version_check=%s want=%s" % (leg, dec.version, shim))
    return {"leg": leg, "sha256": got_sha, "shim": dec.version, "pass": True}


if __name__ == "__main__":
    for leg in LEGS:
        print(row0a(leg))
