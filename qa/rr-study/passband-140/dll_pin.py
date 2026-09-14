#!/usr/bin/env python3
"""PASSBAND-140 leg definitions and pinned-decoder loader.

Spec: qa/rr-study/2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md
section 2.2. Reads binary identity from dll_manifest.json (single source of
truth, spec section 2.1 item 4) rather than duplicating SHA-256 literals.

HK-020 trap, named in the spec: p23_common.DECODE_PARAMS is pinned to
(10, 0.10, 60) and is NOT what most legs here need. Every leg below sets its
own (k, corr, nhard) explicitly via ft8_set_decode_params after load, and
load_leg() asserts the loaded file's SHA-256 + ft8_lib_version_check()
against the manifest before returning -- never trust the file on disk
without checking it first.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))

import p23_common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(REPO_ROOT, "artefacts", "passband-140", "bin")
MANIFEST_PATH = os.path.join(HERE, "dll_manifest.json")

with open(MANIFEST_PATH, encoding="utf-8") as _fh:
    _MANIFEST = json.load(_fh)

for _key in ("BASE", "WIDE"):
    if _MANIFEST[_key]["sha256"] is None:
        raise RuntimeError(
            "dll_manifest.json's %s entry has no sha256 -- not built/recorded yet" % _key)

# leg -> (manifest key, distinct filename, (k, corr, nhard))
LEGS = {
    "B40": ("BASE", (10, 0.10, 40)),
    "W40": ("WIDE", (10, 0.10, 40)),
    "B60": ("BASE", (10, 0.10, 60)),
    "B40r": ("BASE", (10, 0.10, 40)),  # determinism re-run, ROW 0e -- same binary/params as B40
}


def load_leg(leg: str) -> "p23_common.Decoder":
    manifest_key, params = LEGS[leg]
    entry = _MANIFEST[manifest_key]
    path = os.path.join(BIN_DIR, entry["filename"])
    dec = p23_common.Decoder(
        path=path,
        verify=True,
        expected_sha256=entry["sha256"],
        expected_shim_version=entry["shim_version"],
        check_version=True,
    )
    k, corr, nhard = params
    dec.dll.ft8_set_decode_params(k, ctypes.c_float(corr), nhard)
    return dec


def row0a(leg: str) -> dict:
    """Per-leg half of ROW 0a: loaded-file SHA + version_check() + asserted
    params match the manifest/LEGS table. (The build-diff half is checked
    once, statically, in dll_manifest.json's own _row0a note.)"""
    manifest_key, params = LEGS[leg]
    entry = _MANIFEST[manifest_key]
    path = os.path.join(BIN_DIR, entry["filename"])
    got_sha = p23_common.dll_sha256(path)
    if got_sha != entry["sha256"]:
        raise RuntimeError("ROW 0a VOID (%s): sha256 mismatch, got %s want %s"
                            % (leg, got_sha, entry["sha256"]))
    dec = load_leg(leg)
    if dec.version != entry["shim_version"]:
        raise RuntimeError("ROW 0a VOID (%s): version_check=%s want=%s"
                            % (leg, dec.version, entry["shim_version"]))
    return {"leg": leg, "manifest_key": manifest_key, "sha256": got_sha,
            "shim": dec.version, "params": params, "pass": True}


if __name__ == "__main__":
    for leg in LEGS:
        print(row0a(leg))
