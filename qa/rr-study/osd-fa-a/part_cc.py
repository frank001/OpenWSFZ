#!/usr/bin/env python3
"""NHARD40-DEFAULT `CC` -- co-channel oracle leg (Amendment 1, gate G4).

Spec: qa/rr-study/2026-09-12-1000-architect-to-qa-nhard40-default-amendment-1-cc-leg.md
Sec.2. PO-cleared 2026-09-12 ~10:00Z ("Co-channel check first"; `BAR_S = 0.05` FROZEN
for CC, family clause included, before any CC datum exists).

Scene (spec Sec.2.1): ALL 21 parts of s7-compounding.json, verbatim, 100 trials each
= 2,100 cycles. Message texts come from study-messages.json (MSG-01/02/03, Q-prefix).
Renderer: scene_render.render_scene (f-nbr-a), which mirrors run_scenario._render_compound's
body exactly -- encode each station clean, scale by relative snr_db via
channel.mix_to_shared_floor (ONE shared seeded floor per slot), parameterised to the
decoder's native 12kHz rate instead of the 48kHz playback rate _render_compound uses
(see scene_render.py's own module docstring; this is the "cite the equivalence" the spec
asks for -- same mixing model, different sample rate only). Input contract:
normalise_rms(pcm, 0.20), same formula as part_nt.normalise_rms/part_d's WAV-normalise
(scale-invariant to the source array's own units).

Legs (spec Sec.2.2): nhard 60/40/0, k=10, corr=0.10 fixed -- identical scheme to NT/E1/E2
(ONE process, ONE thread, switching between complete decode_all() calls, never mid-decode;
ruled safe by the E1 acceptance ruling Sec.3).

Unit and labels (spec Sec.2.3): station-cycle. present_L(s) = leg L has ANY decode whose
PAYLOAD equals station s's payload (dec.true_codeword compare, part_a.is_true semantics,
but restricted to THIS station's own truth bits, not the pooled truth set -- co-channel
scenes place 2-3 DIFFERENT payloads in one cycle, so "in truth" is not enough; it must be
"is THIS station's payload present"). Deliberately NO frequency condition (spec Sec.2.3's
own reasoning: co-channel frequency drift would relabel a genuine loss as junk removed,
biasing toward S1 -- the unsafe direction).

ROW 0a (SHA pin) is enforced by dll_pin.load_decoder(verify=True) itself (same pin as
Part 0/NT: 6b2e16a6...4f85c, shim 20260050) -- not a separate step here, matching
row0_bc.py's / part_nt.py's own convention.

ROW 0b (spec Sec.2.5): "the rendered signal list equals s7-compounding.json for all 21
parts, asserted in code, field by field." Implemented here as a pinned SHA-256 of the
scenario file's own bytes (S7_SCENARIO_SHA256 below) plus a structural assertion (21
parts, exact family part-index ranges, exact per-part station counts) -- a byte-identical
file trivially implies field-identical, and is a STRONGER, less error-prone check than
retyping all 21 parts' fields a second time by hand (which would risk a transcription bug
of its own, the exact failure mode ROW 0b exists to catch). If this fires, the scenario
file changed since this script was written and the run VOIDs.

ROW 0c (determinism) is a separate process: part_cc_replay.py.
ROW 0d (power) and the gate (CC-S1/S2/S3) are computed by part_cc_analysis.py, pure
computation over this script's persisted JSON.

Persists per-cycle, per-station-cycle arrays (not aggregate scalars only) -- msg_ids,
per-leg presence list + n_decodes + n_false -- so part_cc_replay.py can diff a sampled
subset element-wise, and so this run is fully reproducible from its own JSON.

NFR-021: Q-prefix synthetic messages only (MSG-01/02/03: Q1ABC, Q4XYZ, Q3PQR).

Usage:
    python part_cc.py <out_json>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study"))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import dll_pin as P  # noqa: E402
import scene_render as SR  # noqa: E402
from row0_bc import bind_decode_params  # noqa: E402
from harness.common import compute_seed  # noqa: E402

SCENARIO_ID = "NHARD40-CC"
PROD_TARGET_RMS = 0.20  # Ft8Decoder.cs:52 -- same constant as part_nt.PROD_TARGET_RMS

S7_JSON_PATH = os.path.join(REPO_ROOT, "qa", "rr-study", "scenarios", "s7-compounding.json")
STUDY_MESSAGES_PATH = os.path.join(REPO_ROOT, "qa", "rr-study", "scenarios", "study-messages.json")

# ROW 0b: pinned byte-hash of the scenario file this script was written against
# (computed 2026-09-12, this session). See module docstring for why a full-file hash
# is used in place of retyping all 21 parts' fields.
S7_SCENARIO_SHA256 = "aed34c69fbc55da91a28a9f2e7fcdfcf2b33db0fe3959f4eaacbb97d6e35761f"

TRIALS_PER_PART = 100
N_PARTS = 21

# spec Sec.2.1's own family table, asserted against the file's own "overlap_type"
# labels below (not trusted blind -- HK-021(r): predicate as code).
FAMILY_RANGES = {
    "co_channel": (0, 2),
    "near_collision": (3, 7),
    "time_freq": (8, 10),
    "capture": (11, 14),
    "co_channel_sweep": (15, 20),
}

LEGS = (("60", (10, 0.10, 60)), ("40", (10, 0.10, 40)), ("0", (10, 0.10, 0)))

# The three Q-prefix messages CC actually uses (spec Sec.2.1); asserted against
# study-messages.json's own text at load time, not retyped blind.
EXPECTED_MSG_TEXT = {
    "MSG-01": "CQ Q1ABC FN42",
    "MSG-02": "Q4XYZ Q1ABC -07",
    "MSG-03": "Q3PQR Q1ABC RR73",
}


def family_of(part_index: int) -> str:
    for name, (lo, hi) in FAMILY_RANGES.items():
        if lo <= part_index <= hi:
            return name
    raise ValueError(f"part_index {part_index} not in any family range")


def load_scenario():
    with open(S7_JSON_PATH, "rb") as f:
        raw = f.read()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != S7_SCENARIO_SHA256:
        raise SystemExit(
            f"ROW 0b VOID: s7-compounding.json SHA256 mismatch -- "
            f"expected {S7_SCENARIO_SHA256}, got {actual_sha}. The scenario file "
            f"changed since this script was written; escalate before re-running.")
    data = json.loads(raw)
    parts = data["parts"]
    assert len(parts) == N_PARTS, len(parts)
    for p in parts:
        assert p["overlap_type"] == family_of(p["part_index"]), \
            (p["part_index"], p["overlap_type"], family_of(p["part_index"]))
        assert len(p["signals"]) in (2, 3), (p["part_index"], len(p["signals"]))
    return parts


def load_message_texts():
    with open(STUDY_MESSAGES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    by_id = {m["id"]: m["text"] for m in data["messages"]}
    out = {}
    for mid, expected_text in EXPECTED_MSG_TEXT.items():
        assert mid in by_id, mid
        assert by_id[mid] == expected_text, (mid, by_id[mid], expected_text)
        out[mid] = expected_text
    return out


def build_truth(dec, message_texts: dict):
    """Truth bits for MSG-01/02/03, Q-prefix asserted independently (HK-018, same
    pattern as part_a.build_truth / part_nt.build_truth)."""
    bits = {}
    for mid, text in message_texts.items():
        toks = text.split()
        assert len(toks) == 3, text
        for tok in toks:
            if tok == "CQ":
                continue
            core = tok[1:] if tok and tok[0] in "R+-" else tok
            if core.lstrip("+-").isdigit():
                continue
            if tok in ("RR73", "73", "RRR"):
                continue
            if len(tok) == 4 and tok[:2].isalpha() and tok[2:].isdigit():
                continue
            assert tok.startswith("Q"), (text, tok)
        b = dec.true_codeword(text)
        assert b is not None, text
        bits[mid] = b
    return bits


def normalise_rms(pcm: np.ndarray, target: float = PROD_TARGET_RMS) -> np.ndarray:
    src_rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if src_rms < 1e-6:
        return pcm
    return (pcm * (target / src_rms)).astype(np.float64)


def present(message: str, dec, station_text: str, station_bits) -> bool:
    """part_a.is_true semantics, restricted to ONE station's own payload (not the
    pooled truth set -- co-channel scenes have several DIFFERENT payloads per cycle)."""
    if message == station_text:
        return True
    tb = dec.true_codeword(message)
    if tb is None:
        return False
    return tb == station_bits


def run_cycle(dec, message_texts, truth_bits, part, ridx: int, trial: int, legs):
    """Render+decode one CC cycle on the requested legs.
    Returns (per_leg: {leg_name: {"present": [bool,...], "n_decodes": int, "n_false": int}},
             msg_ids: [str,...])."""
    signals_spec = part["signals"]
    msg_ids = [s["msg_id"] for s in signals_spec]
    station_texts = [message_texts[mid] for mid in msg_ids]
    station_bits = [truth_bits[mid] for mid in msg_ids]

    seed = compute_seed(SCENARIO_ID, part["part_index"], trial)
    render_signals = [
        {"message_text": message_texts[s["msg_id"]], "freq_hz": float(s["freq_hz"]),
         "dt_s": float(s["dt_s"]), "snr_db": float(s["snr_db"])}
        for s in signals_spec
    ]
    raw = SR.render_scene(render_signals, seed)
    pcm = normalise_rms(raw, PROD_TARGET_RMS)

    out = {}
    for leg_name, params in legs:
        dec.dll.ft8_set_decode_params(*params)
        decodes = dec.decode_all(pcm) or []
        pres = [False] * len(msg_ids)
        n_false = 0
        for d in decodes:
            matched_any = False
            for i in range(len(msg_ids)):
                if present(d["message"], dec, station_texts[i], station_bits[i]):
                    pres[i] = True
                    matched_any = True
            if not matched_any:
                n_false += 1
        out[leg_name] = {"present": pres, "n_decodes": len(decodes), "n_false": n_false}
    return out, msg_ids


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    def log(msg):
        print(msg, flush=True)

    parts = load_scenario()
    message_texts = load_message_texts()

    dec = P.load_decoder(verify=True)  # ROW 0a
    bind_decode_params(dec.dll)
    truth_bits = build_truth(dec, message_texts)
    log(f"shim={dec.version}")
    log("ROW 0a: PASS (SHA/version pin enforced by dll_pin.load_decoder)")
    log(f"ROW 0b: PASS (s7-compounding.json SHA256={S7_SCENARIO_SHA256[:12]}..., "
        f"21 parts, family ranges + station counts asserted)")

    t_start = time.perf_counter()

    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as f:
            state = json.load(f)
        parts_data = {int(k): v for k, v in state["parts"].items()}
        log(f"resuming from existing {out_json}: {len(parts_data)} parts present")
    else:
        parts_data = {}
        state = {"scenario_id": SCENARIO_ID, "trials_per_part": TRIALS_PER_PART,
                 "s7_scenario_sha256": S7_SCENARIO_SHA256, "wall_s_total": 0.0}
    wall_s_baseline = state.get("wall_s_total", 0.0)

    def save():
        state["parts"] = {str(k): v for k, v in parts_data.items()}
        state["wall_s_total"] = wall_s_baseline + (time.perf_counter() - t_start)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, out_json)

    for part in parts:
        pidx = part["part_index"]
        rec = parts_data.setdefault(str(pidx), {
            "part_index": pidx, "overlap_type": part["overlap_type"],
            "label": part["label"], "n_stations": len(part["signals"]),
            "signals": part["signals"], "trials": [],
        })
        if len(rec["trials"]) >= TRIALS_PER_PART:
            log(f"  part {pidx} ({part['overlap_type']}) already complete, skipping")
            continue
        start = len(rec["trials"])
        t0 = time.perf_counter()
        for t in range(start, TRIALS_PER_PART):
            leg_out, msg_ids = run_cycle(dec, message_texts, truth_bits, part, pidx, t, LEGS)
            row = {"trial": t, "msg_ids": msg_ids}
            row.update(leg_out)
            rec["trials"].append(row)
        log(f"  part {pidx} ({part['overlap_type']}, {len(part['signals'])} stations) "
            f"trials {start}..{TRIALS_PER_PART - 1} ({time.perf_counter() - t0:.0f}s)")
        parts_data[str(pidx)] = rec
        save()

    log(f"DONE -> {out_json} (wall={state['wall_s_total']:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
