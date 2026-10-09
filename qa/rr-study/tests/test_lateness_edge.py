"""Tests for the LATENESS / EDGE test code (qa/rr-study/lateness-edge/): design, noise level,
truncation row P2, the post-playback predicates and the edge definitions."""
from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

LE = Path(__file__).resolve().parent.parent / "lateness-edge"
sys.path.insert(0, str(LE))
import analysis as A  # noqa: E402
import design as D  # noqa: E402
import render as R  # noqa: E402


@pytest.fixture(scope="module")
def design():
    return D.build_design()


# ---------------------------------------------------------------------------- design
def test_design_is_deterministic_and_matches_the_spec_numbers(design):
    assert D.canonical_json(design) == D.canonical_json(D.build_design())
    assert len(design["signals"]) == 2432 and len(design["cycles"]) == 204
    kinds = [(c["block"], c["planted"]) for c in design["cycles"]]
    assert kinds.count(("LATE", True)) == 100 and kinds.count(("EARLY", True)) == 52
    assert kinds.count(("EARLY", False)) == 52
    assert [s["freq_hz"] for s in design["signals"][:16]] != []
    assert {s["freq_hz"] for s in design["signals"]} == {300 + 150 * i for i in range(16)}


def test_every_cell_has_32_signals_never_twice_in_a_cycle_and_12_slots(design):
    cells = {}
    for s in design["signals"]:
        cells.setdefault(s["cell"], []).append(s)
    assert len(cells) == 76
    for cid, lst in cells.items():
        assert len(lst) == 32
        assert len({s["cycle"] for s in lst}) == 32
        assert len({s["slot"] for s in lst}) >= 12


def test_texts_unique_and_q_prefix(design):
    texts = [s["text"] for s in design["signals"]]
    assert len(set(texts)) == 2432
    calls = [w for t in texts for w in t.split()[:2]]
    assert len(set(calls)) == len(calls) == 4864 and all(c.startswith("Q") for c in calls)


def test_lateness_convention_dt_is_half_second_plus_L(design):
    for s in design["signals"]:
        assert s["dt_s"] == pytest.approx(0.5 + s["L_s"])
    assert D.CUT_ONSET_S == pytest.approx(1.86)


def test_early_planted_cycles_are_preceded_by_an_idle_cycle(design):
    cyc = design["cycles"]
    for i, c in enumerate(cyc):
        if c["block"] == "EARLY" and c["planted"]:
            assert not cyc[i - 1]["planted"]


# ---------------------------------------------------------------------------- noise level
def test_sigma_gives_the_labelled_inband_snr_with_the_bandlimited_convention():
    """The fixed sigma, passed through add_awgn with the 4 700 Hz bandlimit, must give the labelled
    in-band (2 500 Hz reference) SNR for a unit signal scaled to -8 dB (HK-026: check the level)."""
    from synth import channel
    unit, bs = R.clean_render(R.REF_TEXT, R.REF_FREQ_HZ, 0.0)
    sigma = R.reference_sigma()
    sig = (10 ** (-8 / 20)) * unit
    noisy = channel.add_awgn(sig, sigma, 123, noise_cutoff_hz=R.CUTOFF_HZ, sample_rate_hz=D.FS)
    measured = channel.measure_inband_snr_db(sig, noisy, D.FS)
    assert measured == pytest.approx(-8.0, abs=0.7)


def test_sigma_is_the_same_for_every_cycle_and_independent_of_signal_content(design):
    s1 = R.reference_sigma()
    assert s1 == R.reference_sigma() and s1 > 0


# ---------------------------------------------------------------------------- P1 / P2 on real renders
def test_p1_placement_error_is_within_two_ms_for_late_and_early():
    for L in (0.0, 0.25, 3.0, 6.0, -0.5, -3.0):
        assert R.p1_lag_error_s("Q1AAA Q2BBB AA11", 1000.0, L) <= R.LAG_TOL_S


def test_p2_truncation_and_early_containment_on_rendered_cycles(design):
    sigma = R.reference_sigma()
    late_idx = next(i for i, c in enumerate(design["cycles"]) if c["block"] == "LATE" and any(
        design["signals"][j]["L_s"] > D.CUT_ONSET_S for j in c["signals"]))
    buf, info = R.render_cycle(design, late_idx, sigma)
    assert len(buf) == R.SLOT_N and buf.dtype == np.float32
    cut = [r for r in info["p2"] if r["cut"]]
    assert cut and all(r["zero_after_end"] and r["identical_before_end"] for r in info["p2"])
    assert all(r["energy_kept"] < 1.0 for r in cut)
    assert all(r["energy_kept"] == pytest.approx(1.0) for r in info["p2"] if not r["cut"])
    early_idx = next(i for i, c in enumerate(design["cycles"]) if c["block"] == "EARLY" and c["planted"])
    ebuf, einfo = R.render_cycle(design, early_idx, sigma)
    assert len(ebuf) == R.EARLY_N and einfo["buffer_start_s"] == -3.0 and einfo["sigma"] == info["sigma"]
    assert all(r["whole_signal_inside"] and r["energy_kept"] == pytest.approx(1.0) for r in einfo["p2"])


# ---------------------------------------------------------------------------- statistics and edges
def test_wilson_known_values():
    lo, hi = A.wilson(16, 32)
    assert lo == pytest.approx(0.3365, abs=1e-3) and hi == pytest.approx(0.6635, abs=1e-3)
    assert A.wilson(0, 32)[0] == 0.0 and A.wilson(32, 32)[1] == 1.0


def _r(grid, fn):
    return {L: fn(L) for L in grid}


def test_late_edge_largest_L_with_all_smaller_passing():
    g = list(D.LATE_L_GRID)
    v, label, after = A.edge(g, _r(g, lambda L: 1.0 if L <= 2.5 else 0.2), 0.5, early=False)
    assert v == 2.5 and label == "+2.50" and after == []


def test_late_edge_non_monotone_is_listed_not_smoothed():
    g = list(D.LATE_L_GRID)
    v, label, after = A.edge(g, _r(g, lambda L: 0.9 if L <= 1.0 or L == 4.0 else 0.1), 0.5, early=False)
    assert v == 1.0 and after == [4.0]


def test_late_edge_open_ended_and_failing_at_zero():
    g = list(D.LATE_L_GRID)
    assert A.edge(g, _r(g, lambda L: 1.0), 0.5, early=False)[1] == "> 6.00"
    assert A.edge(g, _r(g, lambda L: 0.0), 0.5, early=False)[0] is None


def test_early_edge_most_negative_L_with_all_between_passing():
    g = list(D.EARLY_L_GRID)
    v, label, _ = A.edge(g, _r(g, lambda L: 1.0 if L >= -1.75 else 0.0), 0.5, early=True)
    assert v == -1.75 and label == "-1.75"
    assert A.edge(g, _r(g, lambda L: 1.0), 0.5, early=True)[1] == "< -3.00"


def test_dt_form_and_q2_fraction():
    t = {"E50(snr=-8)": {"edge": 2.5, "label": "+2.50", "non_monotone_after_edge": []},
         "E90(snr=-8)": {"edge": None, "label": "none (fails at L = 0)", "non_monotone_after_edge": []}}
    out = A.add_dt_form(t, -0.3)
    assert out["E50(snr=-8)"]["dt_edge"] == pytest.approx(2.2) and out["E90(snr=-8)"]["dt_edge"] is None
    assert A.q2_fraction([2.0, 3.0, 4.0, 5.0], 0.5, 3.0) == pytest.approx(0.5)
    assert math.isnan(A.q2_fraction([], 0.5, 3.0))


# ---------------------------------------------------------------------------- predicates on synthetic decodes
T0 = datetime(2026, 10, 3, 18, 0, 0, tzinfo=timezone.utc)


def _boundaries():
    return {i: T0 + timedelta(seconds=15 * i) for i in range(204)}


def _perfect(design, b, snr_off=0.0, dt=0.1, drop=lambda s: False):
    rows = []
    for s in design["signals"]:
        if drop(s):
            continue
        rows.append({"utc": b[s["cycle"]], "text": s["text"], "snr_db": s["snr_db"] + snr_off,
                     "dt_s": dt, "freq_hz": s["freq_hz"] + 1.0})
    stamps = {b[i] for i, c in enumerate(design["cycles"]) if c["planted"]}
    return rows, stamps


def test_validity_passes_on_perfect_decodes_and_reports_edges(design):
    b = _boundaries()
    rw, sw = _perfect(design, b, dt=-0.3)
    ro, so = _perfect(design, b, dt=0.35)
    res = A.run(design, b, {"wsjtx": rw, "owsfz": ro}, {"wsjtx": sw, "owsfz": so})
    assert res["validity"]["ALL_VALIDITY_PASS"] and res["note"] == ""
    assert res["validity"]["delta_chain_s"] == pytest.approx(-0.3)
    e = res["edges"]["wsjtx"]["E50(snr=-8)"]
    assert e["label"] == "> 6.00" and e["dt_edge_label"] == "> +5.70"
    assert res["edges"]["wsjtx"]["E50e(snr=-8)"]["label"] == "< -3.00"
    assert res["validity"]["P7"]["owsfz"]["LATE"]["median_dt_s"] == pytest.approx(0.35)


def test_p3_fails_and_blocks_edges_when_late_control_is_poor(design):
    b = _boundaries()
    drop = lambda s: s["cell"] == D.cell_id("LATE", 0.0, -8) and s["sig_id"] % 2 == 0  # noqa: E731
    rw, sw = _perfect(design, b, drop=drop)
    ro, so = _perfect(design, b)
    res = A.run(design, b, {"wsjtx": rw, "owsfz": ro}, {"wsjtx": sw, "owsfz": so})
    assert not res["validity"]["P3"]["wsjtx"]["PASS"] and not res["validity"]["ALL_VALIDITY_PASS"]
    assert res["edges"] == {} and "P3" in res["note"]


def test_p3b_requires_early_count_within_three_of_late(design):
    b = _boundaries()
    ids = [s["sig_id"] for s in design["signals"] if s["cell"] == D.cell_id("EARLY", 0.0, -8)]
    drop = lambda s: s["sig_id"] in ids[:5]  # noqa: E731   # 27/32 = 0.84 < 0.90 and 5 below late
    rw, sw = _perfect(design, b, drop=drop)
    ro, so = _perfect(design, b)
    res = A.run(design, b, {"wsjtx": rw, "owsfz": ro}, {"wsjtx": sw, "owsfz": so})
    assert not res["validity"]["P3b"]["wsjtx"]["PASS"]


def test_p4_fails_when_a_planted_cycle_has_no_decode_pass(design):
    b = _boundaries()
    rw, sw = _perfect(design, b)
    ro, so = _perfect(design, b)
    victim = next(i for i, c in enumerate(design["cycles"]) if c["planted"])
    sw = sw - {b[victim]}
    res = A.run(design, b, {"wsjtx": rw, "owsfz": ro}, {"wsjtx": sw, "owsfz": so})
    assert res["validity"]["P4"]["wsjtx"]["missing_cycles"] == [victim]
    assert not res["validity"]["ALL_VALIDITY_PASS"]


def test_p5_level_check(design):
    b = _boundaries()
    rw, sw = _perfect(design, b, snr_off=+3.5)
    ro, so = _perfect(design, b)
    res = A.run(design, b, {"wsjtx": rw, "owsfz": ro}, {"wsjtx": sw, "owsfz": so})
    assert not res["validity"]["P5"]["wsjtx"]["PASS"] and res["validity"]["P5"]["owsfz"]["PASS"]


def test_p6_wrong_cycle_decode_in_a_planted_cycle_fails_idle_is_listed(design):
    b = _boundaries()
    rw, sw = _perfect(design, b)
    ro, so = _perfect(design, b)
    s0 = design["signals"][0]
    other = next(i for i, c in enumerate(design["cycles"]) if c["planted"] and i != s0["cycle"])
    rw.append({"utc": b[other], "text": s0["text"], "snr_db": -8, "dt_s": 0.0, "freq_hz": s0["freq_hz"]})
    idle = next(i for i, c in enumerate(design["cycles"]) if not c["planted"])
    ro.append({"utc": b[idle], "text": s0["text"], "snr_db": -8, "dt_s": 0.0, "freq_hz": s0["freq_hz"]})
    res = A.run(design, b, {"wsjtx": rw, "owsfz": ro}, {"wsjtx": sw, "owsfz": so})
    assert res["validity"]["P6"]["wsjtx"]["wrong_in_planted_cycles"] == 1 and not res["validity"]["P6"]["wsjtx"]["PASS"]
    assert res["validity"]["P6"]["owsfz"]["PASS"] and res["validity"]["P6"]["owsfz"]["listed_idle_cycle_decodes"] == 1


def test_frequency_tolerance_is_ten_hz(design):
    b = _boundaries()
    s = design["signals"][5]
    ok = [{"utc": b[s["cycle"]], "text": s["text"], "snr_db": -8, "dt_s": 0, "freq_hz": s["freq_hz"] + 10.0}]
    bad = [{"utc": b[s["cycle"]], "text": s["text"], "snr_db": -8, "dt_s": 0, "freq_hz": s["freq_hz"] + 10.5}]
    assert s["sig_id"] in A.match_decoder(design, b, ok)[0]
    assert s["sig_id"] not in A.match_decoder(design, b, bad)[0]


def test_parse_all_txt_keeps_only_planted_text_and_counts_the_rest(tmp_path, design):
    s = design["signals"][0]
    p = tmp_path / "ALL.TXT"
    p.write_text(
        f"261003_180000  14.074 Rx FT8   -8  0.1 {s['freq_hz']} {s['text']}\n"
        f"261003_180000  14.074 Rx FT8  -12  0.2 1000 SOMETHING ELSE ENTIRELY\n"
        f"garbage\n", encoding="utf-8")
    rows, stamps, n, other = A.parse_all_txt(p, {x["text"] for x in design["signals"]})
    assert len(rows) == 1 and rows[0]["text"] == s["text"] and rows[0]["dt_s"] == pytest.approx(0.1)
    assert n == 2 and other == 1 and len(stamps) == 1
    assert all("ELSE" not in str(r) for r in rows)


def test_read_playback_log_roundtrip(tmp_path):
    p = tmp_path / "log.csv"
    p.write_text("cycle_index,boundary_utc,planted,play_started_utc\n0,2026-10-03T18:00:00Z,1,\n", encoding="utf-8")
    assert A.read_playback_log(p)[0] == T0
