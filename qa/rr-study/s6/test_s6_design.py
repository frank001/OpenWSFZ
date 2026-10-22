"""Unit tests for s6_design (pure functions, synthetic candidates; no corpus, no sound). Run: python -m pytest s6/test_s6_design.py"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import s6_design as d  # noqa: E402


def synth_candidates(blocks_per_band=None, cycles=32):
    blocks_per_band = blocks_per_band or {"17m": 27, "20m": 66, "40m": 72, "80m": 27}
    out = {b: {} for b in d.BANDS}
    for band, n in blocks_per_band.items():
        for i in range(n):
            bid = "%s-b%02d" % (band, i)
            out[band][bid] = [{"block": bid, "run": "run-" + band, "band": band, "sun": "day", "route": "x",
                               "stamp": "261001_%06d" % (j * 15)} for j in range(cycles)]
    return out


def test_draw_is_deterministic_and_independent_of_dict_order():
    c = synth_candidates()
    a, _ = d.draw_order(c)
    rev = {b: dict(reversed(list(c[b].items()))) for b in c}
    b, _ = d.draw_order(rev)
    assert a == b


def test_tiers_are_nested_prefixes_and_band_balanced():
    order, _ = d.draw_order(synth_candidates())
    quick, std, ext = (order[:d.TIERS[t]] for t in ("quick", "standard", "extended"))
    assert std[:len(quick)] == quick and ext[:len(std)] == std
    for sel, per in ((quick, 6), (std, 15), (ext, 45)):
        for band in d.BANDS:
            assert sum(1 for x in sel if x["band"] == band) == per
    assert d.TIERS == {"quick": 24, "standard": 60, "extended": 180} and d.K_TRIALS == 3


def test_a_block_gives_a_second_cycle_only_after_every_block_of_its_band_gave_one():
    order, _ = d.draw_order(synth_candidates())
    for band, n in (("17m", 27), ("80m", 27)):
        seq = [x["block"] for x in order if x["band"] == band]
        assert len(set(seq[:n])) == n                   # the first n draws are n distinct blocks
        assert len(set(seq[:n + 1])) == n               # the (n+1)-th repeats one


def test_extended_tier_has_two_cycles_from_the_small_bands_blocks():
    order, _ = d.draw_order(synth_candidates())
    ext = order[:d.TIERS["extended"]]
    seq17 = [x["block"] for x in ext if x["band"] == "17m"]
    assert len(seq17) == 45 and len(set(seq17)) == 27   # 27 blocks, so 18 of them appear twice


def test_a_band_that_runs_out_is_reported_not_padded():
    c = synth_candidates({"17m": 1, "20m": 3, "40m": 3, "80m": 3}, cycles=2)
    order, stats = d.draw_order(c)
    assert len(order) == 2 + 6 + 6 + 6 and stats["17m"]["candidates"] == 2
    assert [x["band"] for x in order[:5]] == ["17m", "20m", "40m", "80m", "17m"]
    assert all(x["band"] != "17m" for x in order[8:])


def test_playback_level_equals_the_batterys():
    from harness import run_scenario
    assert d.PLAYBACK_PEAK_LEVEL == run_scenario._PLAYBACK_PEAK_LEVEL


def test_render_is_48k_float32_peak_normalised():
    rng = np.random.default_rng(1)
    s16 = (rng.standard_normal(d.CYCLE_SAMPLES) * 3000).astype(np.int16)
    x, gain, peak = d.render_48k(s16)
    assert x.dtype == np.float32 and x.size == d.CYCLE_SAMPLES * 4
    assert abs(float(np.max(np.abs(x))) - d.PLAYBACK_PEAK_LEVEL) < 1e-4
    assert abs(gain * peak - d.PLAYBACK_PEAK_LEVEL) < 1e-9


def test_silent_wav_gets_no_gain_not_a_division_by_zero():
    x, gain, peak = d.render_48k(np.zeros(d.CYCLE_SAMPLES, dtype=np.int16))
    assert gain == 0.0 and peak == 0.0 and not np.any(x)


def test_a_slot_of_any_other_length_stops_and_is_never_padded():
    import pytest
    for n in (d.CYCLE_SAMPLES - 1, d.CYCLE_SAMPLES + 1, 0, d.CYCLE_SAMPLES // 2):
        with pytest.raises(d.SlotLengthError):
            d.render_48k(np.zeros(n, dtype=np.int16))
    x, _, _ = d.render_48k(np.ones(d.CYCLE_SAMPLES, dtype=np.int16))
    assert x.size == d.SLOT_SAMPLES_48K == 720_000


def test_check_lengths_finds_a_short_or_wrong_format_wav(tmp_path):
    import wave
    def make(name, n, fs=12000):
        (tmp_path / "wsjt-x" / "r").mkdir(parents=True, exist_ok=True)
        with wave.open(str(tmp_path / "wsjt-x" / "r" / (name + ".wav")), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(fs); wf.writeframes(np.zeros(n, dtype=np.int16).tobytes())
    make("a", d.CYCLE_SAMPLES); make("b", d.CYCLE_SAMPLES - 5); make("c", d.CYCLE_SAMPLES, fs=11025)
    items = [{"id": k, "run": "r", "stamp": k} for k in "abcz"]
    probs = d.check_lengths(str(tmp_path), items)
    assert sorted(p.split()[-1] for p in probs) == ["b", "c", "z"] and len(probs) == 3
