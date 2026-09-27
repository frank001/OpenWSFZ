#!/usr/bin/env python3
"""GAP-LOCATE: _forced_success, reused VERBATIM from f-nbr-a/row0.py (HK-018, spec sec.0
names this exact function as the reused instrument).

Copied rather than `from row0 import _forced_success` for two mechanical reasons, both
disclosed:
  1. f-nbr-a/row0.py's own import of `dll_common`/`scene_render` relies on Python's
     "script's own directory is sys.path[0]" auto-insertion when run directly; imported
     as a library from elsewhere, its `import dll_common as DC` would resolve against
     whatever `dll_common.py` happens to be first on sys.path, which is fragile.
  2. This arm's own row0.py (ROW 0 checks) would collide on the module name `row0` with
     f-nbr-a's.
The function body below is byte-for-byte the same algorithm as f-nbr-a/row0.py:172-186;
only the constants module is renamed (`DC` -> `gl_dll_pin`, this arm's own D4-pinned
copy, whose extraction_time_offset_s/K_LDPC_ITERATIONS/OSD_DEPTH/FT8_PAYLOAD_BITS values
are identical to f-nbr-a's -- they are shim-level constants, not tied to one binary).
"""
from __future__ import annotations

import gl_dll_pin as DC


def _forced_success(dec, pcm, freq_hz: float, true_message: str, true_dt_s: float = 0.0) -> dict:
    time_offset_s = DC.extraction_time_offset_s(true_dt_s)
    rc, llr = dec.extract_at(pcm, freq_hz, time_offset_s)
    if rc != 0:
        return {"harness_fault": True, "rc": rc}
    res = dec.ldpc_decode_llrs(llr, max_iters=DC.K_LDPC_ITERATIONS, osd_depth=DC.OSD_DEPTH)
    if res["a91"] is None:
        return {"harness_fault": False, "success": False, "crc_ok": res["crc_ok"],
                "path": res["path"], "ldpc_errors": res["ldpc_errors"]}
    true_bits = dec.true_codeword(true_message)
    recovered = DC.a91_to_bits(res["a91"], DC.FT8_PAYLOAD_BITS)
    expected = true_bits[:DC.FT8_PAYLOAD_BITS]
    success = (res["crc_ok"] == 1) and (recovered == expected)
    return {"harness_fault": False, "success": success, "crc_ok": res["crc_ok"],
            "path": res["path"], "ldpc_errors": res["ldpc_errors"]}
