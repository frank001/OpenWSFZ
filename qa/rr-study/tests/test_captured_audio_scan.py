"""Pure-function tests for the #194 captured-audio scan (rulings A1, A2, A3', A7, A10, A11 and the
BOTH / one-sided classification). Synthetic arrays only: no WAV from any run, no decoder, no I/O."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

SCAN = Path(__file__).resolve().parent.parent / "captured-audio-scan"
sys.path.insert(0, str(SCAN))
import scan_apply as ap  # noqa: E402
import scan_core as sc  # noqa: E402
import scan_freeze as fz  # noqa: E402
import scan_run as sr  # noqa: E402

N = sc.SLOT_N


@pytest.fixture(scope="module")
def ref():
    rng = np.random.default_rng(7)
    r = rng.standard_normal(N) * 0.2
    r = np.convolve(r, np.ones(3) / 3, mode="same")           # band-limit a little, like a real slot
    n_fade = int(sc.FADE_S * sc.FS)
    r[-n_fade:] *= np.linspace(1, 0, n_fade)
    return r


def capture(ref, lag=4000, gain=1.0, noise=0.002, seed=3):
    """x[m] = gain * ref[m + lag]: the capture starts `lag` samples into the reference (tau = -lag)."""
    rng = np.random.default_rng(seed)
    x = np.zeros(N)
    x[:N - lag] = gain * ref[lag:]
    x += rng.standard_normal(N) * noise
    return np.clip(np.round(x * 32768), -32768, 32767).astype("<i2")


# ---------------------------------------------------------------- A3' reference-only ambiguity
def test_a3prime_a_steady_tone_reference_is_ambiguous_and_noise_is_not(ref):
    t = np.arange(N) / sc.FS
    assert sc.ref_is_ambiguous(0.5 * np.sin(2 * np.pi * 1500 * t)) is True
    assert sc.ref_is_ambiguous(ref) is False


def test_a3prime_ambiguity_does_not_depend_on_the_capture(ref):
    clean = sc.measure(capture(ref), ref)
    noisy = sc.measure(capture(ref, noise=0.2, seed=9), ref)
    assert clean["lag_ambiguous"] is False and noisy["lag_ambiguous"] is False


def test_clean_capture_recovers_lag_gain_and_has_no_flags(ref):
    m = sc.measure(capture(ref, lag=4000, gain=0.7), ref)
    assert m["tau_ms"] == pytest.approx(-4000 / sc.FS * 1000, abs=0.2)
    assert m["g_db"] == pytest.approx(20 * math.log10(0.7), abs=0.15)
    assert m["lag_lost"] == 0.0 and m["zero_run_ms"] < 1 and m["clip_n"] == 0
    assert abs(m["drift_ppm"]) < 5


# ---------------------------------------------------------------- A2 end-touching zero runs
def test_a2_tail_zero_pad_is_excluded_from_zero_run_and_reported_separately(ref):
    x = capture(ref)
    x[-7200:] = 0                                    # WSJT-X writes 14.4 s then 600 ms of zeros
    m = sc.measure(x, ref)
    assert m["tail_zero_ms"] == pytest.approx(600.0, abs=0.1) and m["zero_run_ms"] < 1.0      # the 600 ms pad is not counted


def test_a2_head_zeros_are_reported_and_a_midslot_dropout_is_a_zero_run(ref):
    x = capture(ref)
    x[:600] = 0
    x[60000:60120] = 0                               # 10 ms inside the support
    m = sc.measure(x, ref)
    assert m["head_zero_ms"] == pytest.approx(50.0, abs=0.1)
    assert m["zero_run_ms"] == pytest.approx(10.0, abs=0.2)


def test_a2_fixed_tail_and_head_rules():
    assert fz.fixed_flag("wsjtx", "tail_zero_ms", 600.0) is False
    assert fz.fixed_flag("wsjtx", "tail_zero_ms", 604.9) is False
    assert fz.fixed_flag("wsjtx", "tail_zero_ms", 605.5) is True
    assert fz.fixed_flag("wsjtx", "tail_zero_ms", 0.0) is True            # a missing pad is also a change
    assert fz.fixed_flag("owsfz", "tail_zero_ms", 5.0) is False
    assert fz.fixed_flag("owsfz", "tail_zero_ms", 5.5) is True
    assert fz.fixed_flag("owsfz", "head_zero_ms", 6.0) is True
    assert fz.fixed_flag("wsjtx", "head_zero_ms", 4.0) is False


# ---------------------------------------------------------------- A10 lag_lost
def test_a10_a_smeared_capture_sets_lag_lost_while_drift_is_still_measured(ref):
    from scipy.interpolate import CubicSpline
    x = capture(ref).astype("float64")
    t = np.arange(N)
    warped = CubicSpline(t, x)(np.clip(t * (1 + 80e-6), 0, N - 1))      # 80 ppm: ~11 samples across the slot
    m = sc.measure(np.clip(np.round(warped), -32768, 32767).astype("<i2"), ref)
    assert m["lag_ambiguous"] is False and m["lag_lost"] == 1.0
    assert m["drift_ppm"] == m["drift_ppm"] and abs(m["drift_ppm"]) > 20


def test_a10_lag_lost_is_not_applicable_on_an_ambiguous_reference():
    t = np.arange(N) / sc.FS
    tone = 0.5 * np.sin(2 * np.pi * 1500 * t)
    x = np.clip(np.round(np.roll(tone, 100) * 32768), -32768, 32767).astype("<i2")
    m = sc.measure(x, tone)
    assert m["lag_ambiguous"] is True and m["lag_lost"] != m["lag_lost"] and m["tau_ms"] != m["tau_ms"]


# ---------------------------------------------------------------- thresholds, floors, clip, A11 centre
def test_threshold_rule_median_plus_six_robust_sigmas_with_floor():
    vals = [0.0] * 50 + [0.1, -0.1] * 5
    row = sc.threshold_row(vals, "up", 0.5)
    assert row["T"] == 0.5 and row["floor_applied"] is True
    big = sc.threshold_row([1, 2, 3, 4, 5, 6, 7], "up", None)
    assert big["T"] == pytest.approx(4 + 6 * 1.4826 * 2)


def test_a6_clip_flags_at_one_sample():
    row = sc.threshold_row([0] * 40, "up", sc.RULES["clip_n"][1])
    assert sc.flagged(1, row) is True and sc.flagged(0, row) is False


def test_a11_centre_override_applies_to_dev_metrics_only():
    row = {"kind": "dev", "median": -328.0, "T": 30.0}
    assert sc.flagged(-290.0, row) is True                    # calibration centre: 38 ms away
    assert sc.flagged(-290.0, row, centre=-291.0) is False    # the run's own centre
    up = {"kind": "up", "median": 0.0, "T": 1.0}
    assert sc.flagged(2.0, up, centre=100.0) is True          # a centre is ignored for one-sided kinds
    assert sc.CENTRE_RULE == {"g_db": "calibration", "dg_db": "calibration", "tau_ms": "run", "dtau_ms": "run"}


# ---------------------------------------------------------------- A7, groups, A1
def test_a7_above_range_cells_come_from_unrepresentable_2x_injections():
    res = [{"cell": "owsfz:single:tile_excess_db", "rates": {"2.0": {"flagged": 0, "of": 0}}, "n_slots": 10},
           {"cell": "wsjtx:multi:click_max", "rates": {"2.0": {"flagged": 4, "of": 4}}, "n_slots": 10},
           {"cell": "wsjtx:single:g_db", "rates": {"2.0": {"flagged": 10, "of": 10}}, "n_slots": 10},
           {"cell": "owsfz:single:hiccup", "rates": {"2.0": {"flagged": 3, "of": 5}}, "n_slots": 10},
           {"cell": "x:y:blind", "status": "BLIND"}]
    assert fz.above_range_cells(res) == ["owsfz:single:tile_excess_db", "wsjtx:multi:click_max"]


def test_a5_groups_are_fixed_by_scene_type():
    pairs = (("S1", 0), ("S3", 4), ("S4", 1), ("S7", 9), ("S8", 0), ("S5", 0), ("S5", 1), ("S5", 2), ("S5", 3))
    assert [sc.group_of(s, p) for s, p in pairs] == [
        "single", "single", "multi", "multi", "multi", "noise", "noise", "tone2", "tone3"]
    with pytest.raises(ValueError):
        sc.group_of("S9", 0)


def test_a1_discrimination_and_the_per_slot_margin():
    assert sr.is_discriminating({"ref_vs_neighbour_ref_rho": 0.49}) is True
    assert sr.is_discriminating({"ref_vs_neighbour_ref_rho": 0.5}) is False
    assert sr.a1_fails({"rho_peak": 0.7, "rho_neighbour_max": 0.51}) is True       # margin 0.19
    assert sr.a1_fails({"rho_peak": 0.71, "rho_neighbour_max": 0.5}) is False      # margin 0.21


# ---------------------------------------------------------------- classification and the A11 split
def test_classification_both_one_sided_by_family():
    fo = {"tau_ms": True, "drift_ppm": False, "g_db": True, "click_max": False}
    fw = {"tau_ms": False, "drift_ppm": True, "g_db": True, "click_max": True}
    assert set(ap.classify(fo, fw)) == {("BOTH", "level"), ("BOTH", "timing"), ("WSJTX-ONLY", "spectral")}
    assert ap.classify({}, {}) == []
    assert ap.classify(fo, {}) == [("OWSFZ-ONLY", "level"), ("OWSFZ-ONLY", "timing")]


def _row(slot, group, tau, g):
    r = {m: 0.0 for m in fz.ALL_METRICS}
    r.update({"slot": slot, "group": group, "scenario": "S1", "part": 0, "tau_ms": tau, "g_db": g,
              "lag_ambiguous": 0, "nondiscriminating": 0, "cycle_utc": "2026-10-03T00:00:00Z"})
    return r


def _th():
    def row(kind, med, T):
        return {"kind": kind, "median": med, "T": T}
    side = {g: {"tau_ms": row("dev", -328.0, 30.0), "g_db": row("dev", -1.0, 0.5)} for g in sc.GROUPS}
    return {"sides": {"owsfz": side, "wsjtx": side}, "cross": {g: {} for g in sc.GROUPS}}


def test_a11_split_a_run_offset_clears_but_a_run_level_change_stays_flagged():
    th = _th()
    # every slot sits 40 ms from the calibration timing centre (a run offset), and 0.9 dB below its gain centre
    scanned = {s: [_row(f"S1_p0_t{i}", "single", -288.0, -1.9) for i in range(5)] for s in fz.SIDES}
    by_slot = {s: {r["slot"]: r for r in scanned[s]} for s in fz.SIDES}
    f3 = ap.evaluate(th, set(), scanned, by_slot, "freeze3")["classes"]
    a11 = ap.evaluate(th, set(), scanned, by_slot, "a11")["classes"]
    assert all(("BOTH", "timing") in v for v in f3.values())                 # registered rule: 40 ms > 30 ms
    assert all(("BOTH", "timing") not in v for v in a11.values())            # A11: centred on the run's own median
    assert all(("BOTH", "level") in v for v in a11.values())                 # g_db is NOT re-centred
    deltas = ap.run_level_deltas(th, scanned)
    assert any(d["RUN-LEVEL"] and d["delta_db"] == pytest.approx(-0.9) for d in deltas)


def test_a11_a_single_slot_that_departs_from_its_own_run_is_flagged():
    th = _th()
    rows = [_row(f"S1_p0_t{i}", "single", -288.0, -1.0) for i in range(9)] + [_row("S1_p0_t9", "single", -200.0, -1.0)]
    scanned = {s: rows for s in fz.SIDES}
    by_slot = {s: {r["slot"]: r for r in scanned[s]} for s in fz.SIDES}
    cl = ap.evaluate(th, set(), scanned, by_slot, "a11")["classes"]
    assert [k for k, v in cl.items() if ("BOTH", "timing") in v] == ["S1_p0_t9"]


def test_descriptive_cells_never_flag():
    th = _th()
    scanned = {s: [_row("S1_p0_t0", "single", -200.0, -1.0)] for s in fz.SIDES}
    by_slot = {s: {r["slot"]: r for r in scanned[s]} for s in fz.SIDES}
    desc = {f"{s}:single:tau_ms" for s in fz.SIDES}
    cl = ap.evaluate(th, desc, scanned, by_slot, "freeze3")["classes"]
    assert not any(f == "timing" for v in cl.values() for _, f in v)       # the DESCRIPTIVE tau cell never flags
    live = ap.evaluate(th, set(), scanned, by_slot, "freeze3")["classes"]
    assert any(f == "timing" for v in live.values() for _, f in v)         # the same slot flags when it is not DESCRIPTIVE


# ---------------------------------------------------------------- the post-run wrapper (ruling 2055 section 4.3)
import post_run_scan as prs  # noqa: E402


def test_busy_reason_detects_timing_and_live_runs_and_ignores_itself():
    assert prs.busy_reason([r"python.exe qa\rr-study\harness\run_scenario.py s1.json"]) == "run_scenario"
    assert prs.busy_reason([r"C:\w\OpenWSFZ.Daemon.exe --urls http://x"]) == "OpenWSFZ.Daemon"
    assert prs.busy_reason(["python supervise_e4_run.py"]) == "supervise"
    assert prs.busy_reason(["python post_run_scan.py --run x --note run_study"]) is None     # itself
    assert prs.busy_reason(["notepad.exe", "chrome.exe"]) is None and prs.busy_reason([]) is None


def test_a_busy_machine_writes_a_skipped_report_and_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(prs, "list_cmdlines", lambda: ["python run_study.py --scenarios S1"])
    monkeypatch.setattr(prs, "scan", lambda a: (_ for _ in ()).throw(AssertionError("must not start")))
    rc = prs.main(["--run", "r", "--truth", "t", "--audio", "a", "--results", str(tmp_path), "--harness-commit", "x"])
    assert rc == 0 and "SKIPPED" in (tmp_path / "captured-audio-scan" / "scan_report.md").read_text(encoding="utf-8")


def test_a_scan_failure_is_written_into_the_report_and_never_fails_the_caller(tmp_path, monkeypatch):
    monkeypatch.setattr(prs, "list_cmdlines", lambda: [])

    def boom(a):
        raise RuntimeError("measure failed (exit 1): synthetic")
    monkeypatch.setattr(prs, "scan", boom)
    rc = prs.main(["--run", "r", "--truth", "t", "--audio", "a", "--results", str(tmp_path), "--harness-commit", "x"])
    text = (tmp_path / "captured-audio-scan" / "scan_report.md").read_text(encoding="utf-8")
    assert rc == 0 and "FAILED" in text and "synthetic" in text and "unaffected" in text


def test_force_start_skips_the_busy_check(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(prs, "list_cmdlines", lambda: ["python run_study.py"])
    monkeypatch.setattr(prs, "scan", lambda a: called.append(a.run))
    assert prs.main(["--run", "r", "--truth", "t", "--audio", "a", "--results", str(tmp_path),
                     "--harness-commit", "x", "--force-start"]) == 0 and called == ["r"]
