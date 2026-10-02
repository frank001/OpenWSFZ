#!/usr/bin/env python3
"""GAP-LOCATE Amendment 4 sec.1: the RR73-equivalence comparator.

Spec: qa/rr-study/2026-09-27-1440-architect-to-qa-gap-locate-amendment-4-rr73-comparator-go.md
(arch/gap-locate e5a4e023). Replaces _forced_success's bit-equality success test, for K' and M
alike. Reuses pack77_fields.py (QA, commit 1efa40c4) verbatim for the field split.

X = encode(REF text)[:77], Y = recovered payload[:77] (both 77-element 0/1 lists, MSB-first).
v_star: the (ir, igrid4) pair on-air RR73 tokens actually pack as, established by ROW 0f.
"""
from __future__ import annotations

import pack77_fields as PF

RR73_STD = (0, PF.MAXGRID4 + 3)  # (0, 32403) -- the vendored encoder's own RR73 sentinel


def payload_match(X: list, Y: list, ref_text: str, v_star: tuple) -> bool:
    if Y == X:
        return True
    toks = ref_text.split()
    if not toks or toks[-1] != "RR73":
        return False
    fx, fy = PF.std_fields(X), PF.std_fields(Y)
    return (
        fx.i3 == 1 and fy.i3 == 1
        and fx.call1 == fy.call1
        and fx.call2 == fy.call2
        and (fx.ir, fx.igrid4) == RR73_STD
        and (fy.ir, fy.igrid4) == v_star
    )
