#!/usr/bin/env python3
"""NHARD40-DEFAULT `NT` -- near-threshold single-station oracle safety leg.

Spec: qa/rr-study/2026-09-12-0912-architect-to-qa-spec-nhard40-default-preregistration.md
Sec.3, PO-cleared 2026-09-12 09:15Z (BAR_S=0.05 frozen before any NT datum; Q2=M2).
This is the ONE new measurement in that arm -- G1 (E1-1) and G3 (E3-N) carry unchanged
(spec Sec.0: the native binary does not change, 6b2e16a6...4f85c, shim 20260050).

Scene (spec Sec.3.1): ONE Q-prefixed station per cycle, rotating over 4 (message, freq)
pairs by (within-rung) trial_index mod 4. `compute_seed('NHARD40-NT', rung_index,
trial_index)` maps rung_index onto harness.common.compute_seed's own "part_index" slot
and trial_index onto its "trial_index" slot (0..249 per rung, restarting at 0 for each
new rung) -- so message rotation and the seed share the SAME within-rung counter by
construction, not coincidence. dt_s = 0.0 (S8HN's own convention).

Ladder (spec Sec.3.1): nominal -26.0..-16.0 dB in 0.5 dB steps (21 rungs) x 250 trials
= 5,250 cycles. NOMINAL RENDERER UNITS -- never cite as on-air dB.

Input contract (spec Sec.3.1, the one thing that differs from Parts A/B/E2):
normalise_rms(render_scene(seed), 0.20) -- the production contract (Ft8Decoder.cs
NormalisePcm, verified in the E1 acceptance ruling Sec.2), applied here to the RAW
render_scene float64 array rather than an int16 WAV buffer. normalise_rms is
scale-invariant to the caller's own choice of intermediate units (E1's own docstring:
pcm * target/rms(pcm) does not care what "pcm"'s native units were) -- so this is the
SAME contract as part_d.read_wav_normalised / p23_common's, not a new one; only the
source array differs (a live scene render here, a WAV file there). Parts A/B/E2 decode
the renderer's own level directly and are unaffected by this; only NT uses it.

Legs per cycle (spec Sec.3.2): nhard 60 (control) / 40 (treatment) / 0 (ceiling,
positive control -- rejects every OSD accept per base ROW 0b: osd 1 -> 0). IDENTICAL
pcm for all three. Settings scheme: ONE PROCESS, ONE THREAD, switching between complete
decode_all() calls -- never mid-decode. Same scheme E1/E2 used, ruled safe by the E1
acceptance ruling Sec.3 (no decode ever in flight when the setter runs; matches
production's own hot-apply, Program.cs:867). STATED HERE per spec Sec.3.2's instruction.

Genuine (spec Sec.3.3/3.4): payload in truth (part_a.is_true -- payload, not text) AND
|freq_hz - injected freq| <= 4.0 Hz (part_b.FREQ_TOL_HZ, the Part B/E2 pairing
convention). A decode present but failing either test counts as false for the
per-cycle false-decode count (Sec.3.7 descriptive).

ROW 0a (SHA pin) is enforced by dll_pin.load_decoder(verify=True) itself, not a
separate step here (matches row0_bc.py's own convention).

ROW 0b (bracket, spec Sec.3.5): checked at the fixed nominal endpoints -26.0 dB and
-16.0 dB. If p60(-26.0) > 0.05 (low side fails) or p60(-16.0) < 0.95 (high side fails),
extend on the failing side ONLY, 60-leg first, in 0.5 dB steps, at most 6 extra rungs,
stopping as soon as a new rung on that side satisfies its own bound; the newly added
rungs (only) are then also decoded on the 40/0 legs. Still failing after 6 extra rungs
on a side => VOID (this script raises SystemExit and writes what it has for the
Architect to read the failure from, per HK-022 "for every ROW 0 ask what it could not
detect" -- a VOID here means the renderer's nominal SNR scale is not where expected,
spec Sec.3.5's own warning).

ROW 0d (power, spec Sec.3.5): computed by part_nt_analysis.py from band B (which needs
ROW 0 b's final rung set) -- if G_B < 300, THIS script (invoked again with --topup) adds
one block of 250 trials to every band-B rung (continuing that rung's own trial counter,
so seeds never repeat), up to 2 blocks, before the analysis script re-reads and re-gates.

Persists per-rung, per-cycle arrays (genuine 0/1 and false-decode count, all three legs)
-- not aggregate scalars only -- so ROW 0c (part_nt_replay.py, a second process) can
diff a sampled subset element-wise, and so this run itself is fully reproducible from
its own JSON.

NFR-021: Q-prefix synthetic messages only (study-messages.json MSG-01/02/04/05).

Usage:
    python part_nt.py <out_json>                  # phase 1 + auto ROW 0b extension
    python part_nt.py <out_json> --topup <rung,rung,...>   # add one 250-trial block
                                                             to the named rungs (dB,
                                                             e.g. "-24.0,-23.5")
"""
from __future__ import annotations

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
from part_a import is_true  # noqa: E402
from part_b import FREQ_TOL_HZ  # noqa: E402
from harness.common import compute_seed  # noqa: E402

SCENARIO_ID = "NHARD40-NT"
PROD_TARGET_RMS = 0.20  # Ft8Decoder.cs:52 -- same constant as part_d.PROD_TARGET_RMS

TRIALS_PER_BLOCK = 250
NOMINAL_LO_DB = -26.0
NOMINAL_HI_DB = -16.0
STEP_DB = 0.5
MAX_EXTEND_RUNGS = 6
MAX_TOPUP_BLOCKS = 2
BAR_LOW = 0.05   # spec Sec.3.5 ROW 0b
BAR_HIGH = 0.95  # spec Sec.3.5 ROW 0b

# spec Sec.3.1 rotation table (trial_index mod 4)
MESSAGES = [
    ("MSG-01", "CQ Q1ABC FN42", 700.0),
    ("MSG-02", "Q4XYZ Q1ABC -07", 1300.0),
    ("MSG-04", "Q1ABC Q4XYZ FN42", 1900.0),
    ("MSG-05", "Q5DEF Q1ABC +03", 2500.0),
]

LEGS = (("60", (10, 0.10, 60)), ("40", (10, 0.10, 40)), ("0", (10, 0.10, 0)))


def rung_index(db: float) -> int:
    """Integer key for a rung's dB value, exact under 0.5 dB steps (avoids float-key
    dict hazards). 0 at -26.0, +20 at -16.0 (the nominal range); negative/>=21 for
    extension rungs below/above it."""
    return round((db - NOMINAL_LO_DB) / STEP_DB)


def rung_db(idx: int) -> float:
    return NOMINAL_LO_DB + idx * STEP_DB


def normalise_rms(pcm: np.ndarray, target: float = PROD_TARGET_RMS) -> np.ndarray:
    """pcm * target/rms(pcm) -- identical formula to part_d.read_wav_normalised,
    applied to a raw render_scene float64 array instead of an int16 WAV buffer
    (scale-invariant; see module docstring)."""
    src_rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if src_rms < 1e-6:
        return pcm
    return (pcm * (target / src_rms)).astype(np.float64)


def build_truth(dec):
    """Truth set for the 4 rotated messages, Q-prefix asserted independently of the
    labeller (base spec Sec.3.1's own mitigation, reused -- HK-018)."""
    texts = [m[1] for m in MESSAGES]
    for t in texts:
        toks = t.split()
        assert len(toks) == 3, t
        for tok in toks:
            if tok == "CQ":
                continue
            core = tok[1:] if tok and tok[0] in "R+-" else tok
            if core.lstrip("+-").isdigit():
                continue
            if len(tok) == 4 and tok[:2].isalpha() and tok[2:].isdigit():
                continue
            assert tok.startswith("Q"), (t, tok)
    bits = {t: dec.true_codeword(t) for t in texts}
    for t, b in bits.items():
        assert b is not None, t
    return texts, bits


def run_trial(dec, truth_texts, truth_bits, db: float, ridx: int, trial: int, legs):
    """Render+decode one cycle on the requested legs. Returns {leg_name: (genuine_bool,
    n_decodes, n_false)}."""
    msg_id, msg_text, freq_hz = MESSAGES[trial % 4]
    seed = compute_seed(SCENARIO_ID, ridx, trial)
    signal = [{"station": "N", "message_text": msg_text, "freq_hz": freq_hz,
               "snr_db": db, "dt_s": 0.0}]
    raw = SR.render_scene(signal, seed)
    pcm = normalise_rms(raw, PROD_TARGET_RMS)

    out = {}
    for leg_name, params in legs:
        dec.dll.ft8_set_decode_params(*params)
        decodes = dec.decode_all(pcm) or []
        n_genuine = 0
        n_false = 0
        for d in decodes:
            ok = (is_true(d["message"], truth_texts, truth_bits, dec)
                  and abs(d["freq_hz"] - freq_hz) <= FREQ_TOL_HZ)
            if ok:
                n_genuine += 1
            else:
                n_false += 1
        out[leg_name] = {"genuine": n_genuine > 0, "n_decodes": len(decodes), "n_false": n_false}
    return out, msg_id


def p60_of(rung_rec: dict) -> float:
    trials = rung_rec["trials"]
    if not trials:
        return float("nan")
    n = len(trials)
    k = sum(1 for t in trials if t["60"]["genuine"])
    return k / n


def run_block(dec, truth_texts, truth_bits, rungs_data: dict, ridx: int, db: float,
              start_trial: int, n_trials: int, legs, log):
    rec = rungs_data.setdefault(ridx, {"db": db, "trials": []})
    assert rec["db"] == db, (rec["db"], db)
    t0 = time.perf_counter()
    for t in range(start_trial, start_trial + n_trials):
        leg_out, msg_id = run_trial(dec, truth_texts, truth_bits, db, ridx, t, legs)
        row = {"trial": t, "msg_id": msg_id}
        row.update(leg_out)
        rec["trials"].append(row)
    log(f"  rung idx={ridx} db={db:+.1f} trials {start_trial}..{start_trial + n_trials - 1} "
        f"legs={[l for l, _ in legs]} ({time.perf_counter() - t0:.0f}s)")


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    def log(msg):
        print(msg, flush=True)

    dec = P.load_decoder(verify=True)  # ROW 0a: raises on SHA/version mismatch
    bind_decode_params(dec.dll)
    truth_texts, truth_bits = build_truth(dec)
    log(f"shim={dec.version}")

    t_start = time.perf_counter()

    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as f:
            state = json.load(f)
        rungs_data = {int(k): v for k, v in state["rungs"].items()}
        log(f"resuming from existing {out_json}: {len(rungs_data)} rungs present")
    else:
        rungs_data = {}
        state = {"scenario_id": SCENARIO_ID, "nominal_lo_db": NOMINAL_LO_DB,
                 "nominal_hi_db": NOMINAL_HI_DB, "step_db": STEP_DB,
                 "trials_per_block": TRIALS_PER_BLOCK, "messages": MESSAGES,
                 "extension": {"low_added": 0, "high_added": 0, "void": False},
                 "topup_blocks": {}, "wall_s_total": 0.0}
    # wall_s_total baseline from any PRIOR process (resume case); this process's own
    # elapsed time is added on top, ONCE per save (not re-added -- save() overwrites,
    # it does not accumulate onto its own last value, which double/triple-counts).
    wall_s_baseline = state.get("wall_s_total", 0.0)

    def save():
        state["rungs"] = {str(k): v for k, v in rungs_data.items()}
        state["wall_s_total"] = wall_s_baseline + (time.perf_counter() - t_start)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, out_json)

    # --- --topup mode: add one 250-trial block to named rungs (band-B top-up, ROW 0d) ---
    if len(sys.argv) > 2 and sys.argv[2] == "--topup":
        rung_dbs = [float(x) for x in sys.argv[3].split(",")]
        for db in rung_dbs:
            ridx = rung_index(db)
            rec = rungs_data.get(ridx)
            if rec is None:
                raise SystemExit(f"--topup: rung {db} has no phase-1 data yet")
            n_blocks_done = state["topup_blocks"].get(str(ridx), 0)
            if n_blocks_done >= MAX_TOPUP_BLOCKS:
                log(f"rung {db}: MAX_TOPUP_BLOCKS already reached, skipping")
                continue
            start = len(rec["trials"])
            run_block(dec, truth_texts, truth_bits, rungs_data, ridx, db, start,
                       TRIALS_PER_BLOCK, LEGS, log)
            state["topup_blocks"][str(ridx)] = n_blocks_done + 1
            save()
        log(f"DONE (topup) -> {out_json}")
        return 0

    # --- Phase 1: nominal ladder, all 21 rungs, all 3 legs ---
    log(f"PHASE 1: nominal ladder {NOMINAL_LO_DB}..{NOMINAL_HI_DB} dB, step {STEP_DB}, "
        f"{TRIALS_PER_BLOCK} trials/rung, 3 legs")
    n_nominal = round((NOMINAL_HI_DB - NOMINAL_LO_DB) / STEP_DB) + 1
    for i in range(n_nominal):
        db = rung_db(i)
        if i in rungs_data and len(rungs_data[i]["trials"]) >= TRIALS_PER_BLOCK:
            log(f"  rung idx={i} db={db:+.1f} already complete, skipping")
            continue
        run_block(dec, truth_texts, truth_bits, rungs_data, i, db, 0, TRIALS_PER_BLOCK, LEGS, log)
        save()

    # --- ROW 0b: bracket check at the fixed nominal endpoints, extend on failure ---
    p60_lo = p60_of(rungs_data[0])
    p60_hi = p60_of(rungs_data[n_nominal - 1])
    log(f"ROW 0b: p60({NOMINAL_LO_DB})={p60_lo:.4f} (need <= {BAR_LOW}), "
        f"p60({NOMINAL_HI_DB})={p60_hi:.4f} (need >= {BAR_HIGH})")

    low_ok = p60_lo <= BAR_LOW
    high_ok = p60_hi >= BAR_HIGH

    if not low_ok:
        log("ROW 0b: low side fails -- extending downward (60-leg first)")
        for step in range(1, MAX_EXTEND_RUNGS + 1):
            ridx = -step
            db = rung_db(ridx)
            run_block(dec, truth_texts, truth_bits, rungs_data, ridx, db, 0,
                       TRIALS_PER_BLOCK, (("60", (10, 0.10, 60)),), log)
            save()
            p = p60_of(rungs_data[ridx])
            log(f"  extension low idx={ridx} db={db:+.1f} p60={p:.4f}")
            if p <= BAR_LOW:
                low_ok = True
                state["extension"]["low_added"] = step
                # 40/0-leg backfill for every rung added here is done in one pass
                # below (the "any extension rung that was added" loop), not per-step.
                break
        if not low_ok:
            state["extension"]["low_added"] = MAX_EXTEND_RUNGS

    if not high_ok:
        log("ROW 0b: high side fails -- extending upward (60-leg first)")
        for step in range(1, MAX_EXTEND_RUNGS + 1):
            ridx = n_nominal - 1 + step
            db = rung_db(ridx)
            run_block(dec, truth_texts, truth_bits, rungs_data, ridx, db, 0,
                       TRIALS_PER_BLOCK, (("60", (10, 0.10, 60)),), log)
            save()
            p = p60_of(rungs_data[ridx])
            log(f"  extension high idx={ridx} db={db:+.1f} p60={p:.4f}")
            if p >= BAR_HIGH:
                high_ok = True
                state["extension"]["high_added"] = step
                break
        if not high_ok:
            state["extension"]["high_added"] = MAX_EXTEND_RUNGS

    # Any extension rung that was added (60-leg only above) must now get its 40/0 legs
    # too, so the analysis script can use it in Band B / K_B / C_B like any other rung.
    for ridx, rec in list(rungs_data.items()):
        if ridx < 0 or ridx >= n_nominal:
            trials = rec["trials"]
            if trials and "40" not in trials[0]:
                db = rec["db"]
                start = len(trials)
                # re-run this rung's own trial indices 0..start-1 on the missing legs,
                # appending 40/0 into the SAME trial rows (not new rows) -- rebuild in
                # place so per-cycle arrays stay one row per (rung, trial).
                fresh = {}
                run_block(dec, truth_texts, truth_bits, fresh, ridx, db, 0, start,
                           (("40", (10, 0.10, 40)), ("0", (10, 0.10, 0))), log)
                for row_old, row_new in zip(trials, fresh[ridx]["trials"]):
                    row_old["40"] = row_new["40"]
                    row_old["0"] = row_new["0"]
                save()

    state["extension"]["void"] = not (low_ok and high_ok)
    if state["extension"]["void"]:
        save()
        log("ROW 0b: VOID -- bracket not achieved within MAX_EXTEND_RUNGS on the "
            "failing side(s). Escalate: the renderer's nominal SNR scale is not where "
            "expected (spec Sec.3.5).")
        return 1

    save()
    log(f"ROW 0b: PASS (low_ok={low_ok} high_ok={high_ok})")
    log(f"DONE phase 1 (+ any extension) -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
