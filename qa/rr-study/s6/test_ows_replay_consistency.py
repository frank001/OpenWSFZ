"""Unit tests for ows_replay_consistency.py on a TOY set (synthetic Q-prefix calls only; NFR-021)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import ows_replay_consistency as R  # noqa: E402
import s6_stats as S  # noqa: E402


def row(text, freq=1000.0, snr=-10.0, batch=1):
    return (freq, snr, R.norm_text(text), batch)


def toy_plan(n_wavs=3, trials=3):
    plan, i = [], 0
    for w in range(n_wavs):
        for t in range(trials):
            plan.append({"index": i, "wav_id": "wav%d" % w, "trial": t, "stamp_o": "261016_%06d" % (i * 15), "stamp_w": "261015_%06d" % (i * 15), "band": "20m"})
            i += 1
    return plan


def test_keyed_matches_analyser_and_tags_batches():
    rows = [row("CQ QA1AAA AA00", 1500, -5, 1), row("CQ QA1AAA AA00", 900, -12, 2), row("<...> QA2BBB", 700, -8, 1), row("QA3CCC QA4DDD RR73", 400, -20, 2)]
    keys, batch, hashed = R.keyed(rows)
    ref, ref_h = R.A.key_rows([(f, s, t) for f, s, t, _ in rows])
    assert keys == ref and hashed == ref_h == 1
    assert batch[("CQ QA1AAA AA00", 0)] == 2 and batch[("CQ QA1AAA AA00", 1)] == 1          # rank by frequency: 900 Hz first
    assert batch[("QA3CCC QA4DDD RR73", 0)] == 2


def test_own_cons_equals_the_analysers_pool():
    trials = {0: {("a", 0): -5, ("b", 0): -9}, 1: {("a", 0): -5}, 2: {("a", 0): -6, ("b", 0): -10, ("c", 0): -15}}
    wavs = ["w1", "w2"]
    by_wav = {"w1": trials, "w2": {0: {("x", 0): 1}, 1: {("x", 0): 1}, 2: {("x", 0): 1}}}
    own, all_ = R.tally_arrays(by_wav, wavs)
    tallies = [S.wav_tally({k: {"w": v, "o": v} for k, v in by_wav[w].items()}) for w in wavs]
    assert abs(R.own_cons(own, all_, np.arange(2)) - S.pool(tallies)["consistency_own_owsfz"]) < 1e-12
    assert own.tolist() == [3, 1] and all_.tolist() == [1, 1]                                  # a decoded 3/3; b, c partly; x 3/3


def test_identity_and_abandoned_exclusion():
    plan = toy_plan(1, 3)
    same = {0: [row("QA1AAA QA2BBB")], 1: [row("QA3CCC QA4DDD")], 2: []}
    flip = dict(same)
    flip[1] = [row("QA3CCC QA4DDD"), row("QA5EEE QA6FFF")]
    res = R.identity([same, same, flip], plan, [set(), set(), set()])
    assert res["identical_full"] == 2 and res["share_full"] == 2 / 3 and res["plays_excluded_abandoned"] == 0
    res = R.identity([same, same, flip], plan, [set(), set(), {1}])
    assert res["plays_excluded_abandoned"] == 1 and res["identical_kept"] == 2 and res["share_kept"] == 1.0 and res["share_full"] == 2 / 3
    assert R.identity([same, same, same], plan, [set()] * 3)["share_kept"] == 1.0


def test_repeat_consistency_deterministic_is_one_and_flip_costs_it():
    plan = toy_plan(2, 3)
    wavs = ["wav0", "wav1"]
    base = {p["index"]: [row("QA1AAA QA2BBB")] for p in plan}
    own, all_ = R.repeat_consistency([base, base, base], plan, wavs, [set()] * 3)
    assert R.mean_over_trials(own, all_, np.arange(2)) == 1.0
    flip = dict(base)
    flip[0] = [row("QA1AAA QA2BBB"), row("QA9ZZZ QA8YYY")]          # play 0 (wav0, trial 0): one extra signal in one repeat only
    own, all_ = R.repeat_consistency([base, base, flip], plan, wavs, [set()] * 3)
    # trial 0: wav0 has 2 signals decoded at least once, 1 in every repeat; wav1 1 and 1 -> 2/3; trials 1 and 2 stay 1.0
    assert abs(R.mean_over_trials(own, all_, np.arange(2)) - (2 / 3 + 1 + 1) / 3) < 1e-12
    own, all_ = R.repeat_consistency([base, base, flip], plan, wavs, [set(), set(), {0}])      # the abandoned play drops out of its cell
    assert R.mean_over_trials(own, all_, np.arange(2)) == 1.0


def test_snr_bins_edges():
    assert R.snr_bin(-18) == 0 and R.snr_bin(-17) == 1 and R.snr_bin(-10) == 1 and R.snr_bin(-9) == 2 and R.snr_bin(10) == 2 and R.snr_bin(-25) == 0
    # floor(x + 0.5) is round-half-up: -18.4 -> -18 (bin 0); -17.6 -> -18 (bin 0); -10.4 -> -10 (bin 1); -9.6 -> -10 (bin 1); -9.4 -> -9 (bin 2); -17.4 -> -17 (bin 1)
    assert [R.snr_bin(x) for x in (-18.4, -17.6, -10.4, -9.6, -9.4, -17.4)] == [0, 0, 1, 1, 2, 1]


def test_bootstrap_pairing_and_excludes_zero():
    own = np.array([4.0, 5.0, 6.0, 5.0])
    all_ = np.array([3.0, 5.0, 3.0, 4.0])
    ci = R.boot(lambda i: R.own_cons(own, all_, i) - R.own_cons(own, all_, i), 4, n_boot=50)
    assert ci["point"] == 0.0 and ci["lo"] == 0.0 and ci["hi"] == 0.0 and not R.excludes_zero(ci)
    assert R.excludes_zero({"lo": 0.1, "hi": 0.3}) and R.excludes_zero({"lo": 0.1, "hi": 0.3}, +1) and not R.excludes_zero({"lo": 0.1, "hi": 0.3}, -1)
    assert R.excludes_zero({"lo": -0.3, "hi": -0.1}, -1) and not R.excludes_zero({"lo": -0.1, "hi": 0.1})
    assert not R.excludes_zero({"lo": float("nan"), "hi": float("nan")})


def test_common_set_binned_by_wsjtx_snr():
    w = {"wav0": {0: {("a", 0): -5, ("b", 0): -12}, 1: {("a", 0): -5}, 2: {("a", 0): -5, ("b", 0): -12}}}
    c = {"wav0": {0: {("a", 0): -4, ("b", 0): -12, ("z", 0): -20}, 1: {("a", 0): -4, ("b", 0): -12}, 2: {("a", 0): -4, ("b", 0): -12}}}
    cs = R.common_set(w, c, ["wav0"])
    # common = a, b (z only WSJT-X). a: strong bin (-4); b: -12 mid bin. OpenWSFZ all-3: a yes, b no. WSJT-X all-3: a yes, b yes.
    assert cs[0, 2].tolist() == [1, 1, 1] and cs[0, 1].tolist() == [1, 0, 1] and cs[0, 0].tolist() == [0, 0, 0]


def test_make_lists_mapping_and_v2(tmp_path):
    sweep, audio = tmp_path / "sweep", tmp_path / "audio"
    (sweep / "s6").mkdir(parents=True)
    (audio / "owsfz" / "wav").mkdir(parents=True)
    (audio / "wsjt-x" / "wav").mkdir(parents=True)
    rows = []
    for i in (2, 0, 1):                                              # out of order on purpose: lists follow the pass-O slot order
        rows.append({"kind": "play", "play_index": i, "trial": i % 3, "wav_id": "wav%d" % (i // 3), "band": "20m", "slot_stamp": "261015_00%02d00" % i,
                     "slot_stamp_o": "261016_00%02d00" % i})
        (audio / "owsfz" / "wav" / ("261016_00%02d00.wav" % i)).write_bytes(b"x")
        (audio / "wsjt-x" / "wav" / ("261015_00%02d00.wav" % i)).write_bytes(b"x")
    (sweep / "s6" / "s6_playlog.jsonl").write_text("\n".join(json.dumps(r) for r in [{"kind": "warmup", "slot_stamp": "x"}] + rows) + "\n")
    out = tmp_path / "out"
    r = R.make_lists(str(sweep), str(audio), str(out))
    assert r["plays"] == 3 and r["missing_archive"] == 0 and r["v2"] == "FAIL"                  # 3 plays is not 180: V2 bar is per sweep
    r = R.make_lists(str(sweep), str(audio), str(out), pilot=3)
    assert r["v2"] == "PASS"
    lines = (out / "archive_o.tsv").read_text().splitlines()
    assert [x.split("\t")[0] for x in lines] == ["0", "1", "2"] and lines[0].endswith("261016_000000")
    assert (out / "savewav_w.tsv").read_text().splitlines()[0].endswith("261015_000000")
    (audio / "owsfz" / "wav" / "261016_000100.wav").unlink()
    assert R.make_lists(str(sweep), str(audio), str(out), pilot=3)["missing_archive"] == 1


def test_read_decodes_roundtrip(tmp_path):
    p = tmp_path / "x.decodes.tsv"
    p.write_text("index\tbatch\tsnr\tdt\tfreq_hz\ttext\n0\t1\t-5\t0.1\t1500\tcq qa1aaa  aa00\n0\t2\t-20\t0.2\t900\tQA3CCC QA4DDD RR73\n3\t1\t0\t0.0\t100\t<...> QA1AAA\n")
    d = R.read_decodes(str(p))
    assert sorted(d) == [0, 3] and d[0][0] == (1500.0, -5.0, "CQ QA1AAA AA00", 1) and d[0][1][3] == 2
