"""Tests for qa/rr-study/nhard-rep (NHARD-REP's pre-registered rows, selection, noise and the orchestrator's wiring).

HK-026 / HK-021 (k): an instrument must be shown to give BOTH answers. Every row below is exercised on a synthetic input that
makes it PASS and on one that makes it FAIL; the verdict is shown to give N-LEVER when there is an effect, N-CLOSED when there is
none, N-OPEN between, and NO VERDICT when a validity row fails. The frozen constants are asserted, not remembered.
All data is synthetic and numeric (NFR-021 / HK-037): stamps and counts, no message text, no callsign.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

NH = Path(__file__).resolve().parent.parent / "rr-study" / "nhard-rep"
sys.path.insert(0, str(NH))
import nhard_rep_rows as r  # noqa: E402
import nhard_rep_select as sel  # noqa: E402

SELECTION = Path(__file__).resolve().parent.parent / "rr-study" / "results" / "2026-10-06-nhard-rep" / "selection.json"


# ---- frozen constants: asserted in code, not recalled in prose --------------------------------------------------------------
def test_frozen_spec_constants():
    assert r.BAR_N == 0.5                      # ratified by the Captain 2026-10-06 ~14:34Z, FROZEN
    assert r.SEED == 20261006 and r.B_RESAMPLES == 10_000
    assert r.BLOCK_REGISTERED == 8 and r.BLOCKS_REPORTED == (4, 16) and r.ACF_LAGS == (1, 2, 8)   # Amendment 1
    assert r.V2_MIN_EXCESS == 3 and r.V2_NOISE_CYCLES == 200                                      # Amendment 1
    assert r.V6_CYCLES == 200 and r.V6_HALF_WINDOW == 0.25                                        # Amendment 1 / section 5
    assert r.V5_MAX_ABANDON == 0.05 and r.THREADS == "8"
    assert r.ARM_NHARD == {"V2N40": 40, "V2N60": 60, "N40": 40, "N60": 60, "AA": 40}
    assert r.DLL_PIN == "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365"       # shim 20260058


def test_frozen_selection_json_matches_its_pin_and_the_amendment_1_rule():
    data = SELECTION.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(data).hexdigest() == r.SELECTION_SHA256
    s = json.loads(data)
    run = s["runs"][s["run"]]
    full = run["FULL"]
    assert full == sorted(full) and s["run"] == "20261004_1634"
    assert run["SAMPLE"] == [x for i, x in enumerate(full) if i % 10 == 0]          # by POSITION, not stamp
    assert run["SAMPLE_B"] == [x for i, x in enumerate(full) if i % 10 == 5]
    assert run["AA"] == run["SAMPLE"][:200] and len(run["AA"]) == 200
    assert run["warmup"] not in full and run["warmup"] < full[0]                    # the first (edge) stamp
    assert s["excluded"]["window_edge"][1] not in full                              # and the last
    assert s["counts"]["included_full_list"] + s["counts"]["excluded_r0_failed"] + 2 == s["counts"]["wav_files"]
    assert len(s["runs"]["NOISE"]["ALL"]) == 200 and len(s["noise"]["wav_sha256"]) == 201


# ---- estimand / verdict ----------------------------------------------------------------------------------------------
def test_net_pp_known_value():
    assert r.net_pp([10, 10], [2, 3], [4, 6]) == pytest.approx(25.0)    # (2+3)/20


@pytest.mark.parametrize("lo,hi,row", [
    (0.5, 1.2, "N-LEVER"),       # CI_lo == BAR_N fires LEVER (>=)
    (0.8, 1.5, "N-LEVER"),
    (-0.2, 0.499, "N-CLOSED"),   # CI_hi just under the bar
    (-0.2, 0.5, "N-OPEN"),       # CI_hi == BAR_N is NOT closed (strict <)
    (0.1, 0.9, "N-OPEN"),
])
def test_verdict_rows_are_exclusive_and_the_boundaries_are_right(lo, hi, row):
    assert r.verdict_row(lo, hi) == row


def test_bootstrap_block_is_8_and_keeps_the_last_partial_block():
    W = [30] * 20
    M40 = [10] * 20
    M60 = [10] * 20
    _lo, _hi, nb = r.ci(W, M40, M60)
    assert nb == 3    # 8 + 8 + 4


def test_ci_is_degenerate_for_identical_arms_and_positive_for_a_real_gain():
    W = [30] * 160
    lo, hi, _ = r.ci(W, [10] * 160, [10] * 160)
    assert lo == hi == 0.0
    lo, hi, _ = r.ci(W, [10] * 160, [11] * 160)
    assert lo == pytest.approx(100 * 160 / (30 * 160)) == pytest.approx(hi)


# ---- clustering report -----------------------------------------------------------------------------------------------
def test_cluster_report_flags_a_gain_carried_by_few_blocks():
    d = [0] * 80
    for i in (0, 1, 8, 9, 16, 17, 24, 25, 32, 33):    # five blocks carry everything
        d[i] = 1
    c = r.cluster_report(d)
    assert c["sum_d"] == 10 and c["distinct_cycles_nonzero"] == 10
    assert c["top5_share_of_positive_sum"] == 1.0 and c["flag_gt_half"] is True
    assert c["largest_abs_block_sum"] == 2 and c["n_blocks"] == 10


def test_cluster_report_does_not_flag_a_diffuse_gain_and_has_no_share_without_a_positive_sum():
    d = [1 if i % 4 == 0 else 0 for i in range(160)]  # one per half-block: 20 blocks of 2
    c = r.cluster_report(d)
    assert c["top5_share_of_positive_sum"] == pytest.approx(10 / 40) and c["flag_gt_half"] is False
    c0 = r.cluster_report([0] * 16)
    assert c0["top5_share_of_positive_sum"] is None and c0["flag_gt_half"] is False
    cneg = r.cluster_report([-1] * 16)
    assert cneg["top5_share_of_positive_sum"] is None


# ---- V1 --------------------------------------------------------------------------------------------------------------
def _pins(good=True):
    return [{"arm": a, "when": w, "libft8_sha256": r.DLL_PIN if good else "0" * 64, "pinned": r.DLL_PIN}
            for a in r.ARMS for w in ("start", "end")]


def test_v1_pass_and_fail_on_mismatch_and_on_a_missing_record():
    assert r.row_v1(_pins())[0] is True
    assert r.row_v1(_pins(False))[0] is False
    assert r.row_v1(_pins()[:-1])[0] is False      # an arm's end record missing


# ---- V2 --------------------------------------------------------------------------------------------------------------
def _noise_rows(total, n=200, exc=""):
    rows = [{"decodes": 0, "exception": ""} for _ in range(n)]
    for i in range(min(total, n)):
        rows[i]["decodes"] = 1
    if exc:
        rows[0]["exception"] = exc
    return rows


def test_v2_passes_at_plus_3_and_fails_at_plus_2():
    assert r.row_v2(_noise_rows(1), _noise_rows(4))[0] is True      # 4 >= 1 + 3
    ok, d = r.row_v2(_noise_rows(1), _noise_rows(3))
    assert ok is False and d["n_false_60"] == 3 and d["n_false_40"] == 1


def test_v2_fails_when_an_arm_did_not_run_or_threw_never_reads_as_zero_false():
    assert r.row_v2([], _noise_rows(10))[0] is False
    assert r.row_v2(_noise_rows(0), _noise_rows(10, n=199))[0] is False
    assert r.row_v2(_noise_rows(0), _noise_rows(10, exc="AccessViolationException"))[0] is False
    assert r.row_v2([{"decodes": -1, "exception": ""}] * 200, _noise_rows(10))[0] is False


def test_v2_is_not_decorative_a_quiet_build_fails_and_a_noisy_build_passes():
    assert r.row_v2(_noise_rows(0), _noise_rows(0))[0] is False
    assert r.row_v2(_noise_rows(1), _noise_rows(21))[0] is True


# ---- V4 --------------------------------------------------------------------------------------------------------------
def _rb(arm, **kw):
    base = {"subtractionEnabled": True, "threadsConfigured": "8", "threadsResolved": "8", "cores": 16, "nhard": r.ARM_NHARD[arm]}
    base.update(kw)
    return [dict(base, when="start"), dict(base, when="end")]


def _readbacks(**over):
    rb = {a: _rb(a) for a in r.ARMS}
    rb.update(over)
    return rb


def test_v4_pass_and_each_failure_mode():
    assert r.row_v4(_readbacks(), r.SELECTION_SHA256)[0] is True
    assert r.row_v4(_readbacks(), "0" * 64)[0] is False                                  # selection changed
    assert r.row_v4(_readbacks(N60=_rb("N60", nhard=40)), r.SELECTION_SHA256)[0] is False   # N60 ran at 40
    assert r.row_v4(_readbacks(N40=_rb("N40", nhard=60)), r.SELECTION_SHA256)[0] is False
    assert r.row_v4(_readbacks(AA=_rb("AA", subtractionEnabled=False)), r.SELECTION_SHA256)[0] is False
    assert r.row_v4(_readbacks(N40=_rb("N40", threadsConfigured="4")), r.SELECTION_SHA256)[0] is False
    assert r.row_v4(_readbacks(N40=_rb("N40")[:1]), r.SELECTION_SHA256)[0] is False      # no END read-back
    rb = _readbacks()
    del rb["V2N60"]
    assert r.row_v4(rb, r.SELECTION_SHA256)[0] is False


# ---- V5 --------------------------------------------------------------------------------------------------------------
def _ab(stamps, abandoned=()):
    return {s: {"ran": True, "abandoned": s in abandoned, "contained": False} for s in stamps}


def test_v5_passes_at_5_percent_fails_above_and_fails_on_a_missing_abandon_record():
    stamps = [f"261004_{i:06d}" for i in range(100)]
    ok = _ab(stamps, set(stamps[:5]))
    assert r.row_v5({"N40": ok, "N60": ok}, stamps)[0] is True
    bad = _ab(stamps, set(stamps[:6]))
    assert r.row_v5({"N40": ok, "N60": bad}, stamps)[0] is False       # EACH corroborating arm is held to the bar
    assert r.row_v5({"N40": ok, "N60": {}}, stamps)[0] is False        # an absent file is not 'nothing abandoned'


# ---- V6 --------------------------------------------------------------------------------------------------------------
def _v6_inputs(n=200, w=30, m=10):
    st = [f"261004_{i:06d}" for i in range(n)]
    return [w] * n, [m] * n, [m] * n, st


def test_v6_passes_on_identical_runs():
    W, M40, MAA, st = _v6_inputs()
    ok, d = r.row_v6(W, M40, MAA, st, _ab(st), _ab(st))
    assert ok is True and d["unexplained"] == 0 and d["NET_AA_pp"] == 0.0


def test_v6_an_explained_difference_passes_and_an_unexplained_one_fails():
    W, M40, MAA, st = _v6_inputs()
    MAA[3] += 1
    # abandoned in exactly one run => explained; the CI (+1/6000 = 0.017 pp) stays inside the window
    ok, d = r.row_v6(W, M40, MAA, st, _ab(st), _ab(st, {st[3]}))
    assert ok is True and d["explained"] == 1 and d["unexplained"] == 0
    ok, d = r.row_v6(W, M40, MAA, st, _ab(st), _ab(st))                      # neither abandoned
    assert ok is False and d["unexplained_stamps"] == [st[3]]
    ok, d = r.row_v6(W, M40, MAA, st, _ab(st, {st[3]}), _ab(st, {st[3]}))    # BOTH abandoned
    assert ok is False
    ok, d = r.row_v6(W, M40, MAA, st, {}, {})                                # no abandon record at all
    assert ok is False


def test_v6_fails_when_the_ci_leaves_the_window_even_if_every_difference_is_explained():
    W, M40, MAA, st = _v6_inputs()
    ab40, abAA = _ab(st), _ab(st, set(st))
    for i in range(0, 200, 2):               # +100 decodes over sum W 6000 = +1.67 pp, far outside +-0.25
        MAA[i] += 1
    ok, d = r.row_v6(W, M40, MAA, st, ab40, abAA)
    assert d["unexplained"] == 0 and d["ci_inside_window"] is False and ok is False


def test_v6_window_is_strict_and_wrong_size_fails():
    W, M40, MAA, st = _v6_inputs(n=199)
    assert r.row_v6(W, M40, MAA, st, _ab(st), _ab(st))[0] is False      # needs exactly 200 cycles


# ---- selection / noise generator -------------------------------------------------------------------------------------
def test_noise_is_deterministic_has_rms_0_20_and_is_distinct_per_index():
    a, b, c = sel.render_noise_pcm(1), sel.render_noise_pcm(1), sel.render_noise_pcm(2)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert len(a) == 180_000
    rms = float(np.sqrt(np.mean((a.astype(np.float64) / 32768.0) ** 2)))
    assert rms == pytest.approx(0.20, abs=1e-3)
    assert sel.NOISE_LABEL == "NHARD-REP-PC" and sel.NOISE_SCORED == 200 and sel.AA_CYCLES == 200 and sel.SAMPLE_STEP == 10


def test_noise_stamps_are_201_distinct_15s_apart_stamps():
    ns = sel.noise_stamps()
    assert len(ns) == 201 and len(set(ns)) == 201 and ns == sorted(ns)


# ---- matched-index loader --------------------------------------------------------------------------------------------
def test_load_matched_parses_empty_and_multiple(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("stamp,wsjtx_idx\n261004_163415,\n261004_163430,0;3;7\n", encoding="utf-8")
    m = r.load_matched(str(p))
    assert m["261004_163415"] == frozenset() and m["261004_163430"] == frozenset({0, 3, 7})
    assert r.load_matched(str(tmp_path / "absent.csv")) == {}


# ---- end to end: synthetic run folder through analyse() --------------------------------------------------------------------
def _write_arm_files(d, arm, stamps, W, M, n_extra_unconf=0, abandoned=(), matched_sets=None):
    tb = ["run,stamp,kind,band,n,corroborated"]
    mt = ["stamp,wsjtx_idx"]
    ab = ["stamp,ran,abandoned,contained"]
    rr = ["run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n"]
    for i, s in enumerate(stamps):
        m = M[i]
        for kind in ("b1", "b2"):
            for band in "ABCD":
                n = c = 0
                if band == "B":
                    n = (m + n_extra_unconf) if kind == "b1" else 0
                    c = m if kind == "b1" else 0
                tb.append(f"x,{s},{kind},{band},{n},{c}")
        tb.append(f"x,{s},ws,ALL,{W[i]},{m}")
        idx = sorted((matched_sets or {}).get(s, set(range(m))))
        mt.append(f"{s},{';'.join(str(x) for x in idx)}")
        ab.append(f"{s},1,{int(s in abandoned)},0")
        rr.append(f"x,S,{s},{i},ON,100.0,{m + n_extra_unconf},,50.0,{m + n_extra_unconf},0")
    (d / f"testb_{arm}.csv").write_text("\n".join(tb) + "\n")
    (d / f"matched_{arm}.csv").write_text("\n".join(mt) + "\n")
    (d / f"abandon_{arm}.csv").write_text("\n".join(ab) + "\n")
    (d / f"run_{arm}.csv").write_text("\n".join(rr) + "\n")


def _write_noise(d, arm, total):
    rr = ["run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n"]
    for i in range(200):
        n = 1 if i < total else 0
        rr.append(f"x,S,261006_{i:06d},{i},ON,10.0,{n},,5.0,{n},0")
    (d / f"run_{arm}.csv").write_text("\n".join(rr) + "\n")


def _write_logs_and_pins(d):
    pins = []
    for a in r.ARMS:
        (d / f"log_{a}.log").write_text(
            "\n".join(f"# readback {w} subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard={r.ARM_NHARD[a]}"
                      for w in ("start", "end")) + "\n")
        for w in ("start", "end"):
            pins.append(json.dumps({"arm": a, "when": w, "libft8_sha256": r.DLL_PIN, "pinned": r.DLL_PIN}))
    (d / "pins.jsonl").write_text("\n".join(pins) + "\n")


def _synthetic(tmp_path, gain_every=0, noise60=21, aa_gain=0, gain_block_mod=0):
    s = json.loads(SELECTION.read_bytes())
    stamps = s["runs"][s["run"]]["SAMPLE"]
    aa = s["runs"][s["run"]]["AA"]
    W = [30] * len(stamps)
    M40 = [10] * len(stamps)
    M60 = [11 if gain_every and i % gain_every == 0 else 10 for i in range(len(stamps))]
    if gain_block_mod:   # a CLUSTERED gain: +1 on every cycle of every gain_block_mod-th 8-cycle block (a wide interval)
        M60 = [11 if (i // 8) % gain_block_mod == 0 else 10 for i in range(len(stamps))]
    _write_arm_files(tmp_path, "N40", stamps, W, M40)
    _write_arm_files(tmp_path, "N60", stamps, W, M60, n_extra_unconf=2)
    MAA = [10 + (1 if aa_gain else 0) * (i % aa_gain == 0) if aa_gain else 10 for i in range(len(aa))]
    _write_arm_files(tmp_path, "AA", aa, W[:len(aa)], MAA)
    _write_noise(tmp_path, "V2N40", 1)
    _write_noise(tmp_path, "V2N60", noise60)
    _write_logs_and_pins(tmp_path)
    return stamps


def test_end_to_end_no_effect_gives_n_closed(tmp_path):
    _synthetic(tmp_path)
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "N-CLOSED"
    assert res["estimand"]["NET_pp"] == 0.0 and res["descriptive"]["K_minus_G"] == 0
    assert res["descriptive"]["not_confirmed_per_cycle"]["60"] == pytest.approx(res["descriptive"]["not_confirmed_per_cycle"]["40"] + 2)
    assert res["descriptive"]["exchange_rate_extra_confirmed_per_extra_not_confirmed"] == 0.0


def test_end_to_end_a_real_gain_gives_n_lever_with_k_and_g(tmp_path):
    stamps = _synthetic(tmp_path, gain_every=2)         # +1 confirmed on every 2nd cycle: ~ +1.67 pp
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "N-LEVER"
    assert res["descriptive"]["K_minus_G"] == len(range(0, len(stamps), 2)) and res["descriptive"]["G_confirmed_at_40_absent_at_60"] == 0
    assert res["cluster"]["flag_gt_half"] is False
    assert (tmp_path / "per_cycle.csv").read_text().splitlines()[0].startswith("stamp,W,n40_b1,n40_b2,n60_b1,n60_b2,M40,M60")


def test_end_to_end_a_clustered_gain_near_the_bar_gives_n_open(tmp_path):
    _synthetic(tmp_path, gain_block_mod=6)               # ~ +0.55 pp point estimate carried by few blocks: CI straddles 0.5
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "N-OPEN"
    lo, hi = res["estimand"]["ci95"]
    assert lo < r.BAR_N <= hi


def test_end_to_end_a_diffuse_gain_below_the_bar_gives_n_closed(tmp_path):
    _synthetic(tmp_path, gain_every=9)                   # ~ +0.37 pp, evenly spread: a tight CI wholly under 0.5
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "N-CLOSED"


def test_end_to_end_v2_failure_withholds_the_verdict_and_names_the_row(tmp_path):
    _synthetic(tmp_path, gain_every=2, noise60=1)       # the cap "did not apply": no excess false decodes
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["verdict"] == "NO VERDICT" and "V2" in res["verdict_withheld_because"]


def test_end_to_end_v6_failure_withholds_the_verdict(tmp_path):
    _synthetic(tmp_path, aa_gain=2)                      # an A/A that disagrees with itself, with no abandon to explain it
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["verdict"] == "NO VERDICT" and "V6" in res["verdict_withheld_because"]


def test_end_to_end_inconsistent_matched_sets_withhold_the_verdict(tmp_path):
    stamps = _synthetic(tmp_path)
    # N60 claims M = 10 but its matched-index file holds 9 indices for one cycle: the instrument contradicts itself
    p = tmp_path / "matched_N60.csv"
    lines = p.read_text().splitlines()
    lines[1] = f"{stamps[0]},0;1;2;3;4;5;6;7;8"
    p.write_text("\n".join(lines) + "\n")
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["verdict"] == "NO VERDICT" and "matched_index_sets_present_and_size_equal_M" in res["verdict_withheld_because"]


def test_end_to_end_a_missing_arm_withholds_the_verdict(tmp_path):
    _synthetic(tmp_path)
    (tmp_path / "pins.jsonl").write_text("")
    res = r.analyse(str(tmp_path), selection_path=str(SELECTION))
    assert res["verdict"] == "NO VERDICT" and "V1" in res["verdict_withheld_because"]


def test_orchestrator_arms_match_the_rows_module():
    import nhard_rep_run as run   # noqa: F401  (import asserts ARMS == ROWS.ARMS and each arm's nhard)
    assert [a[0] for a in run.ARMS] == list(r.ARMS)
    assert run.SELECTION_SHA256 == r.SELECTION_SHA256 and run.DLL == r.DLL_PIN
