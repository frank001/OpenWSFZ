"""Tests for coh-gain/cg_wrongid.py and cg_wrongid_rows.py (COH-GAIN Amendment 6, WRONG-ID, with the Architect's note 1: F is WSJT-X-only).

HK-026 / HK-021 (k): every validity row and each reading row is shown to give BOTH answers; the classifier's precedence and window boundaries are exact. Synthetic numeric data only (NFR-021 / HK-037).
"""
import csv
import json
import sys
from pathlib import Path

import pytest

CGD = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CGD))
import cg_common as CG  # noqa: E402
import cg_wrongid as W  # noqa: E402
import cg_wrongid_rows as WR  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "rr-study" / "results" / "2026-10-06-coh-gain"


def bits(seed):
    import random
    r = random.Random(seed)
    return [r.randint(0, 1) for _ in range(77)]


A, B, C = bits(1), bits(2), bits(3)       # three distinct synthetic 77-bit payloads (the content is irrelevant: only equality matters)


def ws(*items):
    """[(snr, dt, freq, payload, text)] as payloads_of returns it."""
    return [(s, dt, f, pl, "TEXT") for (s, dt, f, pl) in items]


# ---- constants and the frozen list -------------------------------------------------------------------------------------------------------
def test_constants():
    assert W.NEAR_DF_HZ == 12.5 and W.NEAR_DT_S == pytest.approx(0.32) and WR.F_BAR == 0.5 and WR.W2_MAX_MATCH_SHARE == 0.05 and WR.W3_MIN_NEAR_SHARE == 0.80
    assert W.CLASSES == ("M-NEAR", "M-FAR", "M-OWS", "M-NONE") and WR.ANALYSIS_NAME != "rows.json"


def test_the_frozen_row_list_has_the_architects_expected_counts_and_no_free_text():
    spec = json.loads((RESULTS / "wrongid_rows.json").read_bytes())
    assert spec["counts"] == {"C3": {"0": 1352, "1": 215, "total": 1567}, "G": {"0": 533, "1": 112, "total": 645}}
    assert spec["columns"] == W.LIST_COLUMNS
    rows = [dict(zip(spec["columns"], r)) for r in spec["rows"]]
    for r in rows:
        if r["set"] == "C3":
            assert r["G_ok"] == 0 and r["C3_crc"] == 1 and r["C3_ok"] == 0                 # selected by numeric fields alone
        else:
            assert r["G_crc"] == 1 and r["G_ok"] == 0
        assert r["sample"] in (1, 2, 4, 5, 6, 8, 9)                                          # fresh samples only: never the first sample (3) or the pilot (7)
    assert not any(isinstance(x, str) and len(x.split()) > 1 for r in spec["rows"] for x in r)
    keys = [(r["set"], r["sample"], r["cycle_index"], r["widx"]) for r in rows]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)


# ---- the classifier ------------------------------------------------------------------------------------------------------------------------
def test_near_far_ows_none_and_their_precedence():
    row_f, row_dt = 1500.0, 0.3
    near = ws((-10, 0.3, 1505, A))
    assert W.classify(A, 0, row_f, row_dt, near, [])["cls"] == "M-NEAR"
    far = ws((-10, 0.3, 1600, A))
    assert W.classify(A, 0, row_f, row_dt, far, [])["cls"] == "M-FAR"
    assert W.classify(A, 0, row_f, row_dt, ws((-10, 0.3, 1505, B)), ws((-12, 0.1, 900, A)))["cls"] == "M-OWS"          # no WSJT-X match, equals an OWS decode
    assert W.classify(A, 0, row_f, row_dt, ws((-10, 0.3, 1505, B)), ws((-12, 0.1, 900, C)))["cls"] == "M-NONE"
    both = W.classify(A, 0, row_f, row_dt, near + far, ws((-1, 0.0, 1, A)))
    assert both["cls"] == "M-NEAR"                                                                                       # first match wins: WSJT-X near before far before OWS
    assert W.classify(A, 0, row_f, row_dt, far, ws((-1, 0.0, 1, A)))["cls"] == "M-FAR"


def test_window_boundaries_are_inclusive_and_use_the_rows_own_ws_values():
    f, dt = 1500.0, 0.3
    assert W.classify(A, 0, f, dt, ws((0, dt + 0.32, f + 12.5, A)), [])["cls"] == "M-NEAR"          # both at the limit
    assert W.classify(A, 0, f, dt, ws((0, dt + 0.33, f, A)), [])["cls"] == "M-FAR"                  # dt just outside
    assert W.classify(A, 0, f, dt, ws((0, dt, f + 12.6, A)), [])["cls"] == "M-FAR"                  # df just outside
    assert W.classify(A, 0, f, dt, ws((0, dt - 0.32, f - 12.5, A)), [])["cls"] == "M-NEAR"          # negative side too


def test_the_nearest_of_several_matches_is_reported_with_numbers_only():
    out = W.classify(A, 0, 1500.0, 0.0, ws((-9, 0.2, 1510, A), (-15, 0.05, 1502, A)), [])
    assert out["cls"] == "M-NEAR" and out["m_widx"] == 1 and out["m_df"] == 2.0 and out["m_snr"] == -15
    assert all(isinstance(v, (int, float, str)) for v in out.values()) and "TEXT" not in json.dumps(out)


def test_an_unencodable_decode_cannot_match_and_the_payload_is_not_the_row_itself():
    out = W.classify(A, 0, 1500.0, 0.0, ws((-9, 0.0, 1500, None)), [])
    assert out["cls"] == "M-NONE"                                       # a None payload (unencodable) is skipped: the blind spot the report states
    assert W.hamming(A, A) == 0 and W.hamming(A, [1 - b for b in A]) == 77


# ---- the validity and reading rows ------------------------------------------------------------------------------------------------------------
def rec(set_="C3", sample=1, cycle=3, widx=0, path=0, cls="M-NONE", w1=1, in_sample=None, m_widx=None, dist=40, uw=0, uo=0):
    return {"set": set_, "sample": sample, "cycle_index": cycle, "widx": widx, "path": path, "cls": cls, "w1_ok": w1, "ok": 0, "crc": 1, "nbe": 70, "in_sample": in_sample,
            "m_widx": m_widx, "m_df": None, "m_dt": None, "m_snr": None, "dist": dist, "n_ws_unenc": uw, "n_ows_unenc": uo}


def test_w1_exact_reproduction_pass_and_fail():
    assert WR.row_w1([rec(), rec(widx=1)])[0] is True
    ok, d = WR.row_w1([rec(), rec(widx=1, w1=0)])
    assert ok is False and d["not_reproduced"] == 1 and WR.row_w1([])[0] is False


def test_w2_negative_control_pass_fail_and_boundary():
    osd = lambda n_match, n: [rec(path=1, widx=i, cls="M-NEAR" if i < n_match else "M-NONE") for i in range(n)]
    assert WR.row_w2(osd(0, 215))[0] is True
    assert WR.row_w2(osd(10, 200))[0] is True                      # exactly 5 %
    assert WR.row_w2(osd(11, 200))[0] is False                     # a loose matcher
    assert WR.row_w2([rec(path=1, cls="M-FAR")] * 4 + [rec(path=1)] * 96)[0] is True and WR.row_w2([rec(path=0)])[0] is False     # no OSD rows: cannot pass


def test_w3_geometry_pass_fail_and_vacuous():
    mk = lambda near, far: [rec(widx=i, cls="M-NEAR") for i in range(near)] + [rec(widx=100 + i, cls="M-FAR") for i in range(far)]
    assert WR.row_w3(mk(80, 20))[0] is True
    assert WR.row_w3(mk(79, 21))[0] is False
    ok, d = WR.row_w3([rec(), rec(widx=1)])
    assert ok is True and d["vacuous"] is True


@pytest.mark.parametrize("lo,hi,row", [(0.50, 0.7, "W-REAL"), (0.6, 0.8, "W-REAL"), (0.1, 0.4999, "W-FALSE"), (0.2, 0.5, "W-MIXED"), (0.3, 0.7, "W-MIXED")])
def test_reading_rows_exclusive_and_boundaries(lo, hi, row):
    assert WR.reading_row(lo, hi) == row


def world(n_cycles=64, per=4, near_frac=0.0, sample=1):
    """One sample, n_cycles cycles, `per` C3 BP wrongs per cycle; the first near_frac of them are M-NEAR."""
    rows = []
    for c in range(n_cycles):
        for k in range(per):
            idx = c * per + k
            rows.append(rec(sample=sample, cycle=c, widx=k, cls="M-NEAR" if idx < near_frac * n_cycles * per else "M-NONE", in_sample=1 if idx % 3 == 0 else 0, m_widx=k))
    return rows, {sample: list(range(n_cycles))}


def test_f_bootstrap_degenerate_and_known_values():
    rows, cycles = world(near_frac=0.0)
    f, lo, hi, nb = WR.f_bootstrap(rows, cycles)
    assert f == 0.0 and lo == 0.0 and hi == 0.0 and nb == 8
    rows, cycles = world(near_frac=1.0)
    f, lo, hi, _ = WR.f_bootstrap(rows, cycles)
    assert f == 1.0 and lo == 1.0 and hi == 1.0
    rows, cycles = world(near_frac=0.5)
    f, lo, hi, _ = WR.f_bootstrap(rows, cycles)
    assert f == pytest.approx(0.5) and lo < 0.5 <= hi + 1e-9 or lo <= 0.5 <= hi


def test_f_uses_wsjtx_only_ows_is_descriptive():
    rows, cycles = world(near_frac=0.0)
    for r in rows[:128]:
        r["cls"] = "M-OWS"                                                    # half are M-OWS: they must NOT enter the row's F
    assert WR.f_bootstrap(rows, cycles)[0] == 0.0
    assert WR.f_bootstrap(rows, cycles, numerator=("M-NEAR", "M-OWS"))[0] == pytest.approx(0.5)


def _csv(tmp_path, rows):
    p = tmp_path / "wrongid_rows.csv"
    with open(p, "w", newline="\n") as fh:
        w = csv.writer(fh)
        w.writerow(W.OUT_COLUMNS)
        for r in rows:
            w.writerow([("" if r.get(c) is None else r.get(c, "")) for c in W.OUT_COLUMNS])
    return str(p)


def _rbs(rows, sample=1):
    return {sample: {(r["cycle_index"], r["widx"]): {"G_ok": 0, "ws_snr": -12, "C3_ok": 1} for r in rows}}


def test_end_to_end_w_real_when_most_wrongs_are_near_and_all_validity_passes(tmp_path):
    rows, cycles = world(near_frac=0.9)
    rows += [rec(path=1, widx=50 + i, cycle=i % 64) for i in range(40)]                       # OSD wrongs: none matched
    res = WR.analyse(_csv(tmp_path, rows), None, _rbs(rows), cycles)
    assert res["failing_rows"] == [] and res["reading"] == "W-REAL" and res["F_wsjtx_only"]["ci95"][0] >= 0.5
    assert res["descriptive"]["M_NEAR_in_sample"]["of_M_NEAR"] > 0


def test_end_to_end_w_false_when_nothing_matches(tmp_path):
    rows, cycles = world(near_frac=0.0)
    res = WR.analyse(_csv(tmp_path, rows + [rec(path=1, widx=60 + i, cycle=i) for i in range(10)]), None, _rbs(rows), cycles)
    assert res["reading"] == "W-FALSE" and res["descriptive"]["M_NONE_bp"] == 256
    assert res["descriptive"]["M_NONE_per_correct_recovery_after_osd_off"] == pytest.approx(256 / len(rows))


def test_end_to_end_a_loose_matcher_withholds_the_reading(tmp_path):
    rows, cycles = world(near_frac=0.9)
    rows += [rec(path=1, widx=50 + i, cycle=i % 64, cls="M-NEAR") for i in range(40)]            # the negative control FAILS: OSD wrongs "match"
    res = WR.analyse(_csv(tmp_path, rows), None, _rbs(rows), cycles)
    assert res["reading"] == "NO READING" and "W2" in res["reading_withheld_because"] and "F_wsjtx_only" not in res


def test_end_to_end_a_non_reproduced_row_withholds_the_reading(tmp_path):
    rows, cycles = world(near_frac=0.9)
    rows[5]["w1_ok"] = 0
    rows += [rec(path=1, widx=50 + i, cycle=i % 64) for i in range(40)]
    res = WR.analyse(_csv(tmp_path, rows), None, _rbs(rows), cycles)
    assert res["reading"] == "NO READING" and "W1" in res["reading_withheld_because"]


def test_the_analysis_never_overwrites_a_rows_named_file(tmp_path):
    rows, cycles = world(near_frac=0.9)
    rows += [rec(path=1, widx=50 + i, cycle=i % 64) for i in range(40)]
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    (res_dir / "rows.json").write_text("FROZEN")
    WR.analyse(_csv(tmp_path, rows), str(res_dir), _rbs(rows), cycles)
    assert (res_dir / "rows.json").read_text() == "FROZEN" and (res_dir / WR.ANALYSIS_NAME).exists()


def test_w2_counts_far_matches_too_not_only_near():
    far_only = [rec(path=1, widx=i, cls="M-FAR") for i in range(20)] + [rec(path=1, widx=100 + i) for i in range(180)]     # 10 % M-FAR, 0 M-NEAR
    assert WR.row_w2(far_only)[0] is False


DLL = Path(__file__).resolve().parents[2] / "artefacts" / "rr_2026-10-06_coh_gain" / "bin" / "libft8_20260058.dll"


@pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
def test_reproduction_functions_recover_the_true_payload_on_a_clean_synthetic_signal_and_stay_inside_the_function():
    import cg_synth as SY
    dec = CG.load_decoder(str(DLL))
    s = dict(json.loads((CGD / "synthetic_set.json").read_bytes())[0], snr_db=0.0)
    pcm = SY.render_signal(s)
    truth_bits = dec.true_codeword(s["message"])
    truth = truth_bits[:77]
    c3, c3_pl = W.reproduce_c3(dec, pcm, s["anchor_f"], s["anchor_t"], s["message"], truth_bits, truth)
    g, g_pl = W.reproduce_g(dec, pcm, s["anchor_f"], s["anchor_t"], s["message"], truth_bits, truth)
    assert c3["ok"] == g["ok"] == 1 and c3_pl == truth and g_pl == truth and W.hamming(c3_pl, truth) == 0
    # the reproduction agrees field-for-field with the production arm function (this is what W1 asserts on real rows)
    full = CG.evaluate_signal(dec, pcm, s["anchor_f"], s["anchor_t"], s["message"])
    assert (c3["ok"], c3["crc"], c3["path"], c3["nbe"]) == (full["C3_ok"], full["C3_crc"], full["C3_path"], full["C3_nbe"])
    assert (g["ok"], g["crc"], g["path"], g["nbe"]) == (full["G_ok"], full["G_crc"], full["G_path"], full["G_nbe"])
