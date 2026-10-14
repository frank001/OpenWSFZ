"""Tests for coh-gain/cg_gate_features.py (Q-GATE feature extractor). SYNTHETIC signals only: no real row, no label, no outcome is touched (the spec is not ruled yet).

HK-026 / HK-021 (k): each feature is shown to give both answers: a right message matches, a different message does not; a strong signal reads high, noise low.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

CGD = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CGD))
import cg_common as CG  # noqa: E402
import cg_gate_features as GF  # noqa: E402
import cg_synth as SY  # noqa: E402
import fine_sync as FS  # noqa: E402

DLL = Path(__file__).resolve().parents[2] / "artefacts" / "rr_2026-10-06_coh_gain" / "bin" / "libft8_20260058.dll"
needs_dll = pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")


def test_decoded_tones_are_a_valid_ft8_tone_sequence_with_the_costas_array_in_place():
    import random
    r = random.Random(5)
    payload = [r.randint(0, 1) for _ in range(77)]
    tones = GF.decoded_tones(payload)
    assert len(tones) == 79 and all(0 <= t <= 7 for t in tones)
    for p, t in FS.SYNC_SYMBOLS.items():
        assert tones[p] == t                                           # the Costas symbols are the public array at 0-6, 36-42, 72-78
    assert GF.decoded_tones(payload) == tones and GF.decoded_tones([1 - b for b in payload]) != tones


@needs_dll
def test_decoded_tones_equal_the_vendored_encoders_tones_for_a_real_message():
    dec = CG.load_decoder(str(DLL))
    msg = "CQ Q1ABC FN42"
    assert GF.decoded_tones(dec.true_codeword(msg)[:77]) == CG.encode_tones(dec, msg)


@needs_dll
def test_tone_match_is_high_for_the_sent_message_and_near_chance_for_another_message():
    dec = CG.load_decoder(str(DLL))
    s = dict(json.loads((CGD / "synthetic_set.json").read_bytes())[3], snr_db=-8.0)
    pcm = SY.render_signal(s)
    est = FS.estimate(pcm, s["anchor_f"], s["anchor_t"])
    right = GF.tone_features(pcm, s["anchor_f"], s["anchor_t"], est, dec.true_codeword(s["message"])[:77])
    other_msg = "Q9ZZZ Q8YYY RR73"
    wrong = GF.tone_features(pcm, s["anchor_f"], s["anchor_t"], est, dec.true_codeword(other_msg)[:77])
    assert right["tone_match_fraction"] >= 0.9 and wrong["tone_match_fraction"] <= 0.3
    assert right["tone_energy_ratio"] > 3 * wrong["tone_energy_ratio"] and right["tone_energy_ratio"] > 0.5


@needs_dll
def test_f1_the_own_surface_ratio_saturates_with_strength_which_is_why_it_is_not_the_gates_strength_estimate():
    s = json.loads((CGD / "synthetic_set.json").read_bytes())[1]
    reads = {snr: GF.costas_snr_db(SY.render_signal(dict(s, snr_db=snr)), s["anchor_f"], s["anchor_t"]) for snr in (-12.0, 0.0, 10.0, 20.0)}
    assert reads[0.0] > reads[-12.0]
    assert abs(reads[20.0] - reads[0.0]) < 2.0          # flat above ~0 dB: a peak-to-sidelobe ratio, not a strength estimate there


@needs_dll
def test_f1b_noise_referenced_strength_keeps_rising_through_the_strong_range_and_reads_low_for_noise():
    s = json.loads((CGD / "synthetic_set.json").read_bytes())[1]
    snrs = (-20.0, -12.0, 0.0, 10.0, 20.0)
    reads = {snr: GF.costas_snr_noise_ref_db(SY.render_signal(dict(s, snr_db=snr)), s["anchor_f"], s["anchor_t"]) for snr in snrs}
    assert reads[20.0] > reads[10.0] > reads[0.0] > reads[-12.0] > reads[-20.0]
    assert reads[20.0] - reads[0.0] > 6.0                 # unlike F1, it still separates 0 dB from +20 dB
    rng = np.random.default_rng(1)
    noise = (rng.standard_normal(180_000) * 0.2).astype(np.float32)
    n = GF.costas_snr_noise_ref_db(noise, s["anchor_f"], s["anchor_t"])
    assert n < reads[-12.0] and GF.costas_snr_noise_ref_db(noise, s["anchor_f"], s["anchor_t"]) == n        # noise reads low and the feature is deterministic


@needs_dll
def test_the_features_use_no_truth_only_pcm_anchor_estimate_and_the_decoded_payload():
    import inspect
    for fn in (GF.costas_snr_db, GF.costas_snr_noise_ref_db, GF.tone_features, GF.decoded_tones):
        params = set(inspect.signature(fn).parameters)
        assert not ({"text", "truth", "label", "ws_snr", "live_hit"} & params), fn.__name__
