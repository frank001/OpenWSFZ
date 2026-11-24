#!/usr/bin/env python3
"""TA-RES library (spec arch/accept-gate cae3015c + Amendment 1 section 8 `ef0b6e51`; QA (k) review d330b1e6).  QA tooling: no src/ or native/ change.  Pure functions; the self-test drives them.
THE SCORE R: the unchanged instrument (cf_fbid.locate_and_score, blob ecc4c5e7), only the PCM changes: the row's SOURCE BUFFER instead of the original.  Position: WSJT-X's, the frozen calibration (0.48 s).
SOURCE BUFFER per row: batch 1 -> O; batch 2 -> R2; batch 4 -> by provenance (tr_prov: residual run -> R3 or R2 as the capture's `level` says, original run -> O, third run -> the residual buffer);
batch 5 -> the late round's own decode buffer (file X3 when the capture holds 4 DecodeAll calls, else the 3rd call, which the harness labels R3).
THE DECISION (A1, first match wins): 1 VOID (V-REPRO, V-N or A-KEEP incl. T_iso fails)  2 CREDULOUS (A-GHOST fails, or V-N2 holds and A-RESIDUE fails)  3 UNGUARDED (V-N2 fails and A-SEE passes)
4 REPAIRED (A-SEE)  5 NOT-REPAIRED."""
from __future__ import annotations

SEED = 20261113
B_BOOT = 2000
T_UNMASKED = 0.276
BAR = 0.80                    # cf_uprime.MIN_PRESENT_RATE
BAR_GHOST = 0.05              # A-GHOST margin and A-RESIDUE bar (registered; no data behind A-RESIDUE's, challenged by the pilot if above 0.02)
CHALLENGE = 0.02
V_REPRO = 0.98                # GAP-RESIDUAL 0e's class-agreement bar
V_N_TBUR = 100
V_N2 = 60                     # rule of three: 3 / n <= 0.05 needs n >= 60
K_NULL = 20
CALIB_S = 0.48                # TA-CHECK's frozen start-minus-dt
assert (SEED, B_BOOT, T_UNMASKED, BAR, BAR_GHOST, V_REPRO, V_N_TBUR, V_N2, K_NULL) == (20261113, 2000, 0.276, 0.80, 0.05, 0.98, 100, 60, 20)


def source_file(batch: int, prov_label, level: str, calls: int):
    """which captured file a row is scored on: 'O' | 'R2' | 'R3' | 'X3' | None (unresolved).  batch 4's provenance label comes from tr_prov (R3 / R2 / O); batch 5: X3 with 4 calls, else the 3rd call (file R3)."""
    if batch == 1:
        return "O"
    if batch == 2:
        return "R2"
    if batch == 4:
        return prov_label if prov_label in ("O", "R2", "R3") else None
    if batch == 5:
        return "X3" if calls == 4 else ("R3" if calls == 3 else None)
    return None


def subtracted_before(neigh_batch, reencodable: bool, source: str) -> bool:
    """A1.3: a neighbour is subtracted before the source buffer iff we decoded it in batch b, its native is re-encodable, and b <= 1 for R2, R3, X3; b <= 2 for R3, X3; b <= 4 for X3; never for O."""
    if not reencodable or neigh_batch is None or source == "O":
        return False
    limit = {"R2": 1, "R3": 2, "X3": 4}.get(source)
    return limit is not None and neigh_batch <= limit


def reencodable(text: str) -> bool:
    """SubtractionPass.IsReencodable: no '<' and at least 3 tokens."""
    return "<" not in text and len(text.split()) >= 3


def decide(r: dict) -> str:
    """r: v_repro_ok, n_Tbur, ci_B1, ci_B1m, ci_Tiso ([lo, hi]), ci_ghost_diff ([lo, hi]), n_resid, ci_resid ([lo, hi] or None when n_resid is 0), ci_Tbur."""
    if (not r["v_repro_ok"]) or r["n_Tbur"] < V_N_TBUR or r["ci_B1"][0] < BAR or r["ci_B1m"][0] < BAR or r["ci_Tiso"][0] < BAR:
        return "VOID"
    n2_ok = r["n_resid"] >= V_N2
    if r["ci_ghost_diff"][1] > BAR_GHOST or (n2_ok and r["ci_resid"][1] > BAR_GHOST):
        return "CREDULOUS"
    see = r["ci_Tbur"][0] >= BAR
    if (not n2_ok) and see:
        return "UNGUARDED"
    if see:
        return "REPAIRED"
    return "NOT-REPAIRED"
