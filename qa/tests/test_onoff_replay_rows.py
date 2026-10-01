"""Tests for qa/rr-study/sub-feas/onoff_replay_rows.py (the offline flag-OFF/ON replay's pre-registered rows).

HK-026 / HK-021 (k): an instrument must be shown to give BOTH answers. Every row below is exercised on a synthetic input that
makes it PASS and on one that makes it FAIL; the verdict is shown to give D1 when there is an effect and D2 when there is none.
All data is synthetic and numeric (NFR-021 / HK-037): stamps and counts, no message text, no callsign.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

import pytest

SUBFEAS = Path(__file__).resolve().parent.parent / "rr-study" / "sub-feas"
sys.path.insert(0, str(SUBFEAS))
import onoff_replay_rows as r  # noqa: E402


# ---- estimand ---------------------------------------------------------------------------------------------------
def test_net_pp_known_value():
    # sum(M_on - M_off) = (4-2) + (6-3) = 5 ; sum(W) = 20  =>  25 pp
    assert r.net_pp([10, 10], [2, 3], [4, 6]) == pytest.approx(25.0)


def test_net_pp_zero_when_arms_equal_and_negative_when_on_is_worse():
    assert r.net_pp([10, 10], [3, 3], [3, 3]) == 0.0
    assert r.net_pp([10, 10], [3, 3], [2, 3]) == pytest.approx(-5.0)


# ---- block bootstrap --------------------------------------------------------------------------------------------
def test_bootstrap_is_deterministic_for_the_registered_seed_and_changes_with_another():
    # 20 blocks of different composition, so different seeds give different resamples (a handful of blocks would not)
    W = [10 + (i % 7) for i in range(800)]
    Moff = [3 + (i % 3) for i in range(800)]
    Mon = [m + ((i // 40) % 4 if i % 5 else 0) for i, m in enumerate(Moff)]
    a = r.block_bootstrap_ci(W, Moff, Mon, block=40, B=2000, seed=r.SEED)
    b = r.block_bootstrap_ci(W, Moff, Mon, block=40, B=2000, seed=r.SEED)
    c = r.block_bootstrap_ci(W, Moff, Mon, block=40, B=2000, seed=r.SEED + 1)
    assert a == b
    assert (a[0], a[1]) != (c[0], c[1])


def test_last_partial_block_is_kept_as_its_own_block():
    # 100 cycles, block 40 => blocks of 40, 40, 20 => 3 blocks (a dropped remainder would give 2)
    *_ , nb = r.block_bootstrap_ci([10] * 100, [1] * 100, [2] * 100, block=40, B=100)
    assert nb == 3
    *_ , nb = r.block_bootstrap_ci([10] * 80, [1] * 80, [2] * 80, block=40, B=100)
    assert nb == 2


def test_bootstrap_resamples_numerator_and_denominator_together():
    # every cycle: d = 1, W = 10  => every resample ratio is exactly 10 pp, whatever the blocks drawn
    lo, hi, _ = r.block_bootstrap_ci([10] * 120, [0] * 120, [1] * 120, block=40, B=500)
    assert lo == pytest.approx(10.0) and hi == pytest.approx(10.0)
    # unequal block sizes make a ratio of independently resampled sums differ from the ratio of a resampled block:
    lo2, hi2, _ = r.block_bootstrap_ci([10] * 100, [0] * 100, [1] * 100, block=40, B=500)   # 40,40,20-cycle blocks
    assert lo2 == pytest.approx(10.0) and hi2 == pytest.approx(10.0)


def test_acf_of_a_perfectly_alternating_series_is_negative_at_lag_1_and_positive_at_lag_2():
    d = [1, -1] * 50
    a = r.acf(d, lags=(1, 2))
    assert a[1] < -0.9 and a[2] > 0.9


# ---- verdict: both branches (HK-021 (k)) -----------------------------------------------------------------------
@pytest.mark.parametrize("lo,hi,expected", [
    (1.0, 5.0, "D1"),     # boundary: CI_lo == 1.0 is REPLICATED (the bar is >=)
    (2.0, 9.0, "D1"),
    (-1.0, 0.99, "D2"),   # CI_hi < 1.0
    (-1.0, 1.0, "D3"),    # boundary: CI_hi == 1.0 is NOT < 1.0
    (0.5, 6.0, "D3"),
])
def test_verdict_rows_are_exclusive_and_hit_their_boundaries(lo, hi, expected):
    assert r.verdict_row(lo, hi) == expected


def test_verdict_gives_D1_with_an_effect_and_D2_without_one_on_the_same_instrument():
    n = 400
    W = [20] * n
    Moff = [8] * n
    on_effect = [10] * n         # +2 per cycle over 20 WSJT-X decodes = +10 pp
    on_none = [8] * n            # nothing extra corroborated: NET ~ 0
    lo, hi, _ = r.block_bootstrap_ci(W, Moff, on_effect, block=40, B=1000)
    assert r.verdict_row(lo, hi) == "D1"
    lo, hi, _ = r.block_bootstrap_ci(W, Moff, on_none, block=40, B=1000)
    assert r.verdict_row(lo, hi) == "D2"


# ---- Wilson and the FP watch -------------------------------------------------------------------------------------
def test_wilson_known_values():
    lo, hi = r.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = r.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert all(x != x for x in r.wilson(0, 0))   # NaN when there is nothing to estimate


def _bands(**kw):
    out = {b: (0, 0) for b in r.BANDS}
    out.update(kw)
    return out


def test_fp_watch_flags_a_band_only_when_batch2_lo_exceeds_batch1_hi():
    b1 = _bands(D=(1000, 990))    # 10 not corroborated of 1000: ~1 %
    b2 = _bands(D=(100, 50))      # 50 of 100 not corroborated: ~50 %  => FLAG
    assert r.fp_watch(b1, b2)["D"]["FLAG"] is True
    b2_same = _bands(D=(100, 99))  # ~1 % too: no flag
    assert r.fp_watch(b1, b2_same)["D"]["FLAG"] is False
    # a band with no batch-2 decodes cannot flag, and neither can one with no batch-1 decodes
    assert r.fp_watch(b1, _bands())["D"]["FLAG"] is False
    assert r.fp_watch(_bands(), b2)["D"]["FLAG"] is False


# ---- validity rows: each fires and does not fire ------------------------------------------------------------------
def _pins(arms=("OFF", "ON", "ONREP"), sha=None):
    sha = sha or r.DLL_PIN
    return [{"arm": a, "when": w, "libft8_sha256": sha, "pinned": r.DLL_PIN} for a in arms for w in ("start", "end")]


def test_v1_dll_pin():
    ok, _ = r.row_v1(_pins())
    assert ok
    bad = _pins()
    bad[3]["libft8_sha256"] = "0" * 64
    ok, d = r.row_v1(bad)
    assert not ok and d["failed_or_missing"]
    ok, d = r.row_v1(_pins(arms=("OFF", "ON")))      # a missing arm is a failure, not a pass
    assert not ok and any("ONREP" in x for x in d["failed_or_missing"])


def _rb(enabled, when="start", threads="8", nhard=40):
    return {"when": when, "subtractionEnabled": enabled, "threadsConfigured": threads, "threadsResolved": threads,
            "cores": 16, "nhard": nhard}


def test_v2_flags_and_selection():
    good = {"OFF": [_rb(False, "start"), _rb(False, "end")], "ON": [_rb(True, "start"), _rb(True, "end")],
            "ONREP": [_rb(True, "start"), _rb(True, "end")]}
    assert r.row_v2(good, r.SELECTION_SHA256, ("OFF", "ON", "ONREP"))[0]
    wrong_flag = dict(good, OFF=[_rb(True, "start"), _rb(False, "end")])
    assert not r.row_v2(wrong_flag, r.SELECTION_SHA256, ("OFF", "ON", "ONREP"))[0]
    on_off = dict(good, ON=[_rb(False, "start"), _rb(True, "end")])
    assert not r.row_v2(on_off, r.SELECTION_SHA256, ("OFF", "ON", "ONREP"))[0]
    no_end = dict(good, ON=[_rb(True, "start")])
    assert not r.row_v2(no_end, r.SELECTION_SHA256, ("OFF", "ON", "ONREP"))[0]
    wrong_threads = dict(good, ON=[_rb(True, "start", threads="14"), _rb(True, "end", threads="14")])
    assert not r.row_v2(wrong_threads, r.SELECTION_SHA256, ("OFF", "ON", "ONREP"))[0]
    assert not r.row_v2(good, "0" * 64, ("OFF", "ON", "ONREP"))[0]


def test_v3_exceptions_restarts_contained():
    rows = {"OFF": [{"exception": ""}], "ON": [{"exception": ""}]}
    assert r.row_v3(rows, {}, {})[0]
    assert not r.row_v3({"OFF": [{"exception": "AccessViolationException"}], "ON": [{"exception": ""}]}, {}, {})[0]
    assert not r.row_v3(rows, {"ON": 1}, {})[0]
    assert not r.row_v3(rows, {}, {"ON": 1})[0]


def test_v4_batch1_equals_off_multiset_N_of_N():
    c = collections.Counter
    off = {"s1": c({("1500", "0.1", "-5"): 1, ("1600", "0.2", "-9"): 1}), "s2": c()}
    on_same = {"s1": c({("1600", "0.2", "-9"): 1, ("1500", "0.1", "-5"): 1}), "s2": c()}   # order-free multiset
    ok, d = r.row_v4(off, on_same, ["s1", "s2"])
    assert ok and d["equal"] == 2
    on_diff = {"s1": c({("1500", "0.1", "-5"): 1}), "s2": c()}
    ok, d = r.row_v4(off, on_diff, ["s1", "s2"])
    assert not ok and d["equal"] == 1


@pytest.mark.parametrize("abandoned,included,expected", [(0, 4298, True), (214, 4298, True), (215, 4298, False), (5, 100, True), (6, 100, False)])
def test_v5_abandon_at_most_five_percent(abandoned, included, expected):
    assert r.row_v5(abandoned, included)[0] is expected


def test_v6_repeat_union_identical_on_exactly_160_of_160():
    c = collections.Counter
    stamps = [f"260930_19{i // 60:02d}{i % 60:02d}" for i in range(160)]
    on = {s: c({("1500", "0.1", "-5"): 1, ("1700", "0.3", "-18"): 1}) for s in stamps}
    rep = {s: c(v) for s, v in on.items()}
    assert r.row_v6(on, rep, stamps)[0]
    rep_bad = dict(rep)
    rep_bad[stamps[7]] = c({("1500", "0.1", "-5"): 1})            # one cycle differs: 159/160 fails
    ok, d = r.row_v6(on, rep_bad, stamps)
    assert not ok and d["equal"] == 159 and d["mismatching"] == [stamps[7]]
    assert not r.row_v6(on, rep, stamps[:159])[0]                  # fewer than 160 cycles is not V6


# ---- parsing -----------------------------------------------------------------------------------------------------
def test_parse_log_counts_abandon_contained_and_reads_the_readback_lines(tmp_path):
    log = tmp_path / "log_ON.log"
    log.write_text("\n".join([
        "# harness label=x run=r stratum=ALL mode=two1 threads=8 shim=20260056",
        "# readback start subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard=40 kMinScorePass2=10 osdCorrThreshold=0.10 shim=20260056",
        "2026-10-01T20:00:00.0000000Z [Information] Sub-feas residual pass: residualDecodes=5 elapsedMs=8627 deadlineAbandoned=False containedException=False fittedSignals=28",
        "2026-10-01T20:00:10.0000000Z [Information] Sub-feas residual pass: residualDecodes=0 elapsedMs=13001 deadlineAbandoned=True containedException=False fittedSignals=30",
        "2026-10-01T20:00:20.0000000Z [Warning] WARN-TEMPLATE Sub-feas residual pass failed exc=InvalidOperationException",
        "# readback end subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard=40 kMinScorePass2=10 osdCorrThreshold=0.10 shim=20260056",
    ]) + "\n")
    p = r.parse_log(str(log))
    assert p["passes"] == 2 and p["abandoned"] == 1 and p["contained"] == 1
    assert [x["when"] for x in p["readback"]] == ["start", "end"] and p["readback"][0]["subtractionEnabled"] is True


def test_parse_log_does_not_count_the_warmup_cycle_before_the_start_readback(tmp_path):
    log = tmp_path / "log_ON.log"
    log.write_text("\n".join([
        "# harness label=x",
        "2026 [Information] Sub-feas residual pass: residualDecodes=2 elapsedMs=9000 deadlineAbandoned=True containedException=False fittedSignals=30",   # warm-up
        "# readback start subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard=40",
        "2026 [Information] Sub-feas residual pass: residualDecodes=3 elapsedMs=5000 deadlineAbandoned=False containedException=False fittedSignals=12",
        "# readback end subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard=40",
    ]) + "\n")
    p = r.parse_log(str(log))
    assert p["passes"] == 1 and p["abandoned"] == 0       # the warm-up's abandoned pass is not an included cycle


# ---- end to end on a synthetic night -----------------------------------------------------------------------------
def _write_arm(out, arm, stamps, W, M_by_stamp, b1_by_stamp, b2_by_stamp, abandoned_lines=0):
    (out / f"testb_{arm}.csv").write_text("run,stamp,kind,band,n,corroborated\n" + "".join(
        f"x,{s},ws,ALL,{W},{M_by_stamp[s]}\n"
        f"x,{s},b1,B,{b1_by_stamp[s]},{b1_by_stamp[s]}\nx,{s},b2,B,{b2_by_stamp[s]},{b2_by_stamp[s]}\n" for s in stamps))
    (out / f"outcomes_{arm}.csv").write_text("".join(
        f"{s},b1,{i},{1500 + i},0.1,-5\n" for s in stamps for i in range(b1_by_stamp[s])) + "".join(
        f"{s},b2,{i},{1900 + i},0.2,-17\n" for s in stamps for i in range(b2_by_stamp[s])))
    (out / f"run_{arm}.csv").write_text("run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n\n" + "".join(
        f"r,ALL,{s},{i},{'OFF' if arm == 'OFF' else 'ON'},100.0,{b1_by_stamp[s] + b2_by_stamp[s]},,,{b1_by_stamp[s]},{b2_by_stamp[s]}\n"
        for i, s in enumerate(stamps)))
    en = arm != "OFF"
    (out / f"log_{arm}.log").write_text(
        f"# readback start subtractionEnabled={en} threadsConfigured=8 threadsResolved=8 cores=16 nhard=40\n" +
        "".join("2026 [Information] Sub-feas residual pass: residualDecodes=1 elapsedMs=5000 deadlineAbandoned=False containedException=False fittedSignals=9\n" for _ in range(3)) +
        "".join("2026 [Information] Sub-feas residual pass: residualDecodes=0 elapsedMs=13000 deadlineAbandoned=True containedException=False fittedSignals=9\n" for _ in range(abandoned_lines)) +
        f"# readback end subtractionEnabled={en} threadsConfigured=8 threadsResolved=8 cores=16 nhard=40\n")


@pytest.fixture
def night(tmp_path, monkeypatch):
    n = 200
    stamps = [f"260930_{20 + i // 240:02d}{(i // 4) % 60:02d}{(i % 4) * 15:02d}" for i in range(n)]
    sel = {"run": "R", "runs": {"R": {"warmup": "260930_195945", "ALL": stamps, "V6": stamps[:160]}}}
    sel_path = tmp_path / "selection.json"
    sel_path.write_text(json.dumps(sel, indent=1, sort_keys=True) + "\n")
    # the pin is over LF-normalised bytes (git's autocrlf, and this very fixture on Windows, change line endings)
    monkeypatch.setattr(r, "SELECTION_SHA256", hashlib.sha256(sel_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest())
    out = tmp_path / "out"
    out.mkdir()
    W = 10
    off_b1 = {s: 3 for s in stamps}
    zero = {s: 0 for s in stamps}
    _write_arm(out, "OFF", stamps, W, {s: 3 for s in stamps}, off_b1, zero)
    _write_arm(out, "ON", stamps, W, {s: 5 for s in stamps}, off_b1, {s: 2 for s in stamps})
    _write_arm(out, "ONREP", stamps[:160], W, {s: 5 for s in stamps[:160]}, {s: 3 for s in stamps[:160]}, {s: 2 for s in stamps[:160]})
    (out / "pins.jsonl").write_text("".join(json.dumps(p) + "\n" for p in _pins()))
    return {"out": out, "sel": sel_path, "stamps": stamps}


def test_end_to_end_effect_gives_D1_and_all_valid(night, tmp_path):
    res = r.analyse(str(night["out"]), str(tmp_path / "res"), selection_path=str(night["sel"]))
    assert res["failing_rows"] == [], res["failing_rows"]
    assert res["estimand"]["NET_pp"] == pytest.approx(20.0)      # (5-3) per cycle over 10 WSJT-X decodes
    assert res["verdict"] == "D1"
    assert (tmp_path / "res" / "rows.json").exists()
    assert (night["out"] / "per_cycle.csv").exists()


def test_end_to_end_no_effect_gives_D2(night, tmp_path):
    # make the ON arm identical to the OFF arm in matched counts and extras
    stamps = night["stamps"]
    _write_arm(night["out"], "ON", stamps, 10, {s: 3 for s in stamps}, {s: 3 for s in stamps}, {s: 0 for s in stamps})
    _write_arm(night["out"], "ONREP", stamps[:160], 10, {s: 3 for s in stamps[:160]}, {s: 3 for s in stamps[:160]}, {s: 0 for s in stamps[:160]})
    res = r.analyse(str(night["out"]), selection_path=str(night["sel"]))
    assert res["failing_rows"] == []
    assert res["verdict"] == "D2"


@pytest.mark.parametrize("break_what,row", [("v4", "V4"), ("v6", "V6"), ("pin", "V1"), ("v5", "V5")])
def test_end_to_end_any_validity_failure_withholds_the_verdict(night, break_what, row):
    out, stamps = night["out"], night["stamps"]
    if break_what == "v4":    # an ON batch-1 that differs from OFF on one cycle
        _write_arm(out, "ON", stamps, 10, {s: 5 for s in stamps}, {**{s: 3 for s in stamps}, stamps[10]: 2}, {s: 2 for s in stamps})
    elif break_what == "v6":  # the repeat finds a different union on one of the 160 cycles
        _write_arm(out, "ONREP", stamps[:160], 10, {s: 5 for s in stamps[:160]}, {s: 3 for s in stamps[:160]},
                   {**{s: 2 for s in stamps[:160]}, stamps[3]: 1})
    elif break_what == "pin":
        pins = _pins()
        pins[5]["libft8_sha256"] = "f" * 64
        (out / "pins.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pins))
    elif break_what == "v5":  # 6 % of 200 included cycles abandoned (12 lines)
        _write_arm(out, "ON", stamps, 10, {s: 5 for s in stamps}, {s: 3 for s in stamps}, {s: 2 for s in stamps}, abandoned_lines=12)
    res = r.analyse(str(out), selection_path=str(night["sel"]))
    assert row in res["failing_rows"]
    assert res["verdict"] == "NO VERDICT" and row in res["verdict_withheld_because"]
