#!/usr/bin/env python3
"""OSD-FA-A base ROW 0b/0c (base spec Sec.3) -- the two preconditions gating Parts A/B.

ROW 0a is asserted in-run at every leg's own decoder construction (dll_pin.load_decoder,
verify=True) -- not repeated here as a separate step.
ROW 0d (whole-arm determinism) is checked per-leg as each part runs (matching this
session's own established convention for Part D -- two independent processes, diffed),
not as a single upfront pass.
ROW 0f (diagnostic, population reconciliation of the OLD 56,202/64,417 figures) is
SKIPPED, disclosed: both figures were computed on the base spec's ORIGINAL corpus
(artefacts/20260803_live_run_1713/), which Amendment 1 Sec.3 replaced with
FP-FLOOR-LIVE-2 for Part D. Reconciling two numbers about a corpus this arm no longer
reads is moot, and 0f is DIAGNOSTIC only (never gates) -- Amendment 1 does not ask for
0f to be re-targeted at the new corpus, so this is not run.

Instrument: dll_pin.load_decoder() (current-binary pin, Amendment 1 Sec.2.1),
scene_render's render_scene/load_s8hn_signals (f-nbr-a, reused verbatim -- HK-018).

NFR-021: not engaged -- Q-prefix synthetic scenes only, no live data touched here.
"""
from __future__ import annotations

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
import scene_render as SR  # noqa: E402

# Production defaults (base spec Sec.5.1 / decode.c), used as the "restore" leg of 0b.
DEFAULT_PARAMS = (10, 0.10, 60)

# A clean, high-SNR, well-separated scene for ROW 0c -- base spec Sec.3 row 0c:
# "all stations >=+5dB, no near neighbours". S8HN itself (the Part A/B/C scene) has
# stations as low as -15dB and two exact-frequency collisions (G/H both 1500Hz), so it
# cannot serve as 0c's own fixture -- a dedicated scene is required, not reused.
# Q-prefixed throughout (NFR-021), 600Hz spacing (>> any FT8 bandwidth), dt=0.0.
CLEAN_SIGNALS = [
    {"station": "P", "message_text": "CQ Q2AAA FN20", "freq_hz": 400, "snr_db": 8.0, "dt_s": 0.0},
    {"station": "Q", "message_text": "CQ Q2BBB FN30", "freq_hz": 1000, "snr_db": 8.0, "dt_s": 0.0},
    {"station": "R", "message_text": "CQ Q2CCC FN40", "freq_hz": 1600, "snr_db": 8.0, "dt_s": 0.0},
    {"station": "S", "message_text": "CQ Q2DDD FN50", "freq_hz": 2200, "snr_db": 8.0, "dt_s": 0.0},
]
CLEAN_SEED = 20260911911  # fixed, disclosed -- not swept, one render is the fixture


def bind_decode_params(dll) -> None:
    dll.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
    dll.ft8_set_decode_params.restype = None


S8HN_ROW0B_TRIAL = 1  # disclosed: trial_index=0 (S8HN's own stations, all strong/clean)
# produces ZERO OSD-path decodes -- checked before committing to a fixture (S8HN's 11
# baseline decodes at trial 0 are ALL path=0/BP). nhard=0 vs 60 is untestable against an
# all-BP fixture (nhard only gates the OSD path, decode.c fact 3), so the bar
# ("OSD-path accepts fall to zero") would pass VACUOUSLY, not meaningfully. Trial 1 is
# the first of 60 scanned that produces >=1 genuine OSD-path decode.


def row0b(log) -> bool:
    """Set nhard=0, re-run one fixture, confirm OSD-PATH accepts fall to zero (not
    total decode count -- nhard only gates the OSD path, decode.c fact 3; a BP-path
    decode is unaffected by nhard and must NOT be expected to disappear); restore
    defaults, confirm the original count returns. Path is read via the diagnostic probe
    at each decode's own REPORTED (freq,dt) -- no +0.16 offset (Part D3 ruling Sec.4:
    the offset applies only when extracting at a synthetic TRUE dt)."""
    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    signals = SR.load_s8hn_signals()
    pcm = SR.render_scene(signals, SR.trial_seed(S8HN_ROW0B_TRIAL, 0))

    def decode_and_count_osd(params):
        dec.dll.ft8_set_decode_params(*params)
        decodes = dec.decode_all(pcm)
        n = 0 if decodes is None else len(decodes)
        n_osd = 0
        for d in (decodes or []):
            rc, llr = dec.extract_at(pcm, d["freq_hz"], d["dt"])
            if rc != 0:
                continue
            res = dec.ldpc_decode_llrs(llr, max_iters=P.K_LDPC_ITERATIONS, osd_depth=P.OSD_DEPTH)
            if res["path"] == 1:
                n_osd += 1
        return n, n_osd

    n_baseline, osd_baseline = decode_and_count_osd(DEFAULT_PARAMS)
    n_zeroed, osd_zeroed = decode_and_count_osd((10, 0.10, 0))
    n_restored, osd_restored = decode_and_count_osd(DEFAULT_PARAMS)

    log(f"ROW 0b: baseline n={n_baseline} osd={osd_baseline}  "
        f"nhard=0: n={n_zeroed} osd={osd_zeroed}  "
        f"restored: n={n_restored} osd={osd_restored}")
    passed = (osd_baseline > 0) and (osd_zeroed == 0) and (n_restored == n_baseline) and (osd_restored == osd_baseline)
    log(f"ROW 0b: {'PASS' if passed else 'FAIL'}"
        + ("" if osd_baseline > 0 else " (fixture has no OSD-path decodes -- untestable)"))
    return passed


def row0c(log) -> bool:
    """Clean high-SNR render: every emitted decode's payload must be in truth."""
    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    dec.dll.ft8_set_decode_params(*DEFAULT_PARAMS)

    # 3.1 mitigation: derive the truth set from the scenario data ON DISK, independent
    # of the labeller, and assert its count/Q-prefix property BEFORE labelling
    # (base spec Sec.3.1 -- a shared-truth-list error must not pass silently).
    truth_texts = [s["message_text"] for s in CLEAN_SIGNALS]
    assert len(truth_texts) == 4, len(truth_texts)
    # Q-prefix check on the callsign token itself (index 1 for "CQ <call> <grid>"
    # messages -- all four signals use that shape here):
    for t in truth_texts:
        toks = t.split()
        assert toks[0] == "CQ" and toks[1].startswith("Q"), t
    log(f"ROW 0c: truth set derived from scenario data: {len(truth_texts)} messages, "
        f"all CQ/Q-prefixed (asserted independently of the labeller)")

    truth_bits = {t: dec.true_codeword(t) for t in truth_texts}

    pcm = SR.render_scene(CLEAN_SIGNALS, CLEAN_SEED)
    decodes = dec.decode_all(pcm)
    n = 0 if decodes is None else len(decodes)
    n_false = 0
    for d in (decodes or []):
        msg = d["message"]
        if msg not in truth_bits:
            # Match on PAYLOAD, not displayed text (base Sec.5.1) -- re-encode and
            # compare bits rather than a bare string membership test, so a decode
            # whose text differs cosmetically (e.g. a resolved-vs-unresolved hash
            # rendering) is not misclassified as false.
            tb = dec.true_codeword(msg)
            in_truth = tb is not None and any(tb == v for v in truth_bits.values())
        else:
            in_truth = True
        if not in_truth:
            n_false += 1
    log(f"ROW 0c: {n} decodes emitted, {n_false} not in truth (n_false must == 0)")
    passed = (n_false == 0)
    log(f"ROW 0c: {'PASS' if passed else 'FAIL'}")
    return passed


def main() -> int:
    def _log(msg):
        print(msg)
    ok_b = row0b(_log)
    ok_c = row0c(_log)
    print(f"\nROW 0b: {'PASS' if ok_b else 'FAIL'}   ROW 0c: {'PASS' if ok_c else 'FAIL'}")
    return 0 if (ok_b and ok_c) else 1


if __name__ == "__main__":
    sys.exit(main())
