"""COH-GAIN: tests for coh-gain/cg_rows.py, cg_select.py and cg_common.py (the pre-registered rows, as code).

HK-026 / HK-021 (k): every row is exercised on a synthetic input that makes it PASS and one that makes it FAIL; the verdict is shown to give COH-GO when
there is an effect, COH-STOP when there is none and COH-OPEN between, and NO VERDICT when a validity row fails. Frozen constants are ASSERTED, not recalled.
All data is synthetic and numeric (NFR-021 / HK-037): counts and offsets, no message text, no callsign.
"""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

CGD = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CGD))
import cg_common as CG  # noqa: E402
import cg_rows as R  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_synth as SY  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "rr-study" / "results" / "2026-10-06-coh-gain"


# ---- frozen constants and frozen files --------------------------------------------------------------------------------------------
def test_frozen_spec_constants():
    assert CG.BAR_G == 1.0                                   # ratified by the Captain ~16:26Z, FROZEN (over the proposed 2.0)
    assert CG.SEED == 20261006 and CG.B_RESAMPLES == 10_000 and CG.BLOCK_CYCLES == 8 and CG.BLOCKS_REPORTED == (4, 16)
    assert CG.SAMPLE_RESIDUE == 3 and CG.SAMPLE_MODULUS_PRIMARY == 10 and CG.SAMPLE_MODULUS_FALLBACK == 20
    assert CG.PILOT_ROWS == 50 and CG.PILOT_MAX_CPU_HOURS == 6.0 and CG.PILOT_RESIDUE != CG.SAMPLE_RESIDUE
    assert (CG.V2_N, CG.V2_SNR_DB, CG.V2_DF_MAX_HZ, CG.V2_DT_MAX_S) == (200, -14.0, 1.5, 0.06)
    # Amendment 1 (Architect, ~17:00Z): V2(b) became (b') -- the 0.15 Hz median bar was unpassable for the Costas-only estimator's 0.174 Hz grating lobes
    assert (CG.V2_C3_MIN, CG.V2_G_MIN, CG.V2_MEDIAN_DF_MAX_HZ, CG.V2_SIGNED_MEDIAN_DF_MAX_HZ, CG.V2_MEDIAN_DT_MAX_S) == (0.95, 0.90, 0.20, 0.05, 0.0075)
    assert (CG.V2T_N, CG.V2T_SNR_DB) == (200, -20.0)
    assert (CG.V3_MAX_EDGE_SHARE, CG.V4_G_MIN, CG.V5_ROWS) == (0.05, 0.90, 300)
    assert CG.DLL_PIN == "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365" and CG.SHIM == 20260058
    assert CG.PROD_PARAMS == (10, 0.10, 40) and CG.K_LDPC_ITERATIONS == 50 and CG.OSD_DEPTH == 2
    assert CG.V_STAR == (0, 32373) and CG.DELTA_S == 0.7 and CG.ARMS == ("G", "C1", "C3", "C3S")


def test_frozen_row_list_matches_its_description_and_the_nhard_rule():
    spec = json.loads((RESULTS / "rows.json").read_bytes().replace(b"\r\n", b"\n"))
    nh = json.loads((Path(__file__).resolve().parent.parent / "rr-study" / "results" / "2026-10-06-nhard-rep" / "selection.json").read_bytes())
    full = nh["runs"][nh["run"]]["FULL"]
    cols = spec["columns"]
    assert cols == ["cycle_index", "stamp", "widx", "ws_freq", "ws_dt", "ws_snr", "ws_load", "live_hit", "in_mod20"]
    for row in spec["rows"]:
        assert row[0] % 10 == 3 and full[row[0]] == row[1]                    # position i mod 10 == 3, by POSITION in the NHARD-REP list
        assert row[8] == int(row[0] % 20 == 3) and row[7] in (0, 1)
    for row in spec["pilot_rows"]:
        assert row[0] % 10 == 7                                               # the pilot is disjoint from the analysed sample
    assert {r[0] for r in spec["pilot_rows"]}.isdisjoint({r[0] for r in spec["rows"]})
    assert len(spec["pilot_rows"]) == 50
    keys = [(r[0], r[2]) for r in spec["rows"]]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert spec["counts"]["rows_mod10"] == len(spec["rows"]) and spec["counts"]["rows_mod20"] == sum(r[8] for r in spec["rows"])
    assert not any(isinstance(x, str) and len(x.split()) > 1 for r in spec["rows"] for x in r)   # no free text in any persisted field


# ---- verdict rows ------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lo,hi,row", [(1.0, 2.5, "COH-GO"), (1.7, 3.0, "COH-GO"), (-0.5, 0.999, "COH-STOP"), (-0.5, 1.0, "COH-OPEN"), (0.4, 1.8, "COH-OPEN")])
def test_verdict_rows_are_exclusive_and_boundaries_are_right(lo, hi, row):
    assert R.verdict_row(lo, hi) == row


# ---- V1 / V2 / V3 / V4 / V5 --------------------------------------------------------------------------------------------------------
def _pins(mode="main", sha=None):
    return [{"mode": mode, "when": w, "libft8_sha256": sha or CG.DLL_PIN} for w in ("start", "end")]


def test_v1_pass_fail_and_only_main_pins_count():
    assert R.row_v1(_pins())[0] is True
    assert R.row_v1(_pins(sha="0" * 64))[0] is False
    assert R.row_v1(_pins()[:1])[0] is False                 # no END record
    assert R.row_v1(_pins(mode="v2"))[0] is False            # a V2 pin does not stand in for the main run


def _synth(n=200, c3=1.0, g=1.0, df_err=0.05, dt_err=0.001, faults=0, signed=0.0):
    out = []
    for i in range(n):
        out.append({"i": i, "fault": 1 if i < faults else 0, "C3_ok": 1 if i < c3 * n else 0, "G_ok": 1 if i < g * n else 0, "C1_ok": 1, "C3S_ok": 1,
                    "err_df": df_err, "err_dt": dt_err, "err_df_oracle": 0.02, "err_dt_oracle": 0.001, "err_df_signed": signed})
    return out


def test_v2_passes_when_every_bar_is_met_and_each_part_fails_alone():
    assert R.row_v2(_synth())[0] is True
    assert R.row_v2(_synth(c3=0.94))[0] is False                          # (a)
    assert R.row_v2(_synth(df_err=0.201))[0] is False                     # (b') df magnitude
    assert R.row_v2(_synth(df_err=0.162))[0] is True                      # the first real V2 run's 0.162 Hz passes under (b'), which it failed under (b)
    assert R.row_v2(_synth(df_err=0.10, signed=0.06))[0] is False         # (b') a systematic bias, however small the magnitude
    assert R.row_v2(_synth(df_err=0.10, signed=-0.06))[0] is False
    assert R.row_v2(_synth(df_err=0.10, signed=0.05))[0] is True          # inclusive
    assert R.row_v2(_synth(dt_err=0.008))[0] is False                     # (b) dt
    assert R.row_v2(_synth(g=0.89))[0] is False                           # (c)
    assert R.row_v2(_synth(c3=0.95))[0] is True and R.row_v2(_synth(df_err=0.20, dt_err=0.0075, g=0.90))[0] is True   # boundaries inclusive


def test_v2_a_faulted_signal_is_a_failure_not_an_absence_and_the_count_must_be_200():
    assert R.row_v2(_synth(faults=11))[0] is False      # 11 faults: C3 and G both below the bars
    assert R.row_v2(_synth(n=199))[0] is False
    assert R.row_v2([])[0] is False


def _rows(n_cycles=40, per=10, edge_every=0, g_rate=1.0, hit_every=1, c3_extra=0):
    rows = []
    for c in range(n_cycles):
        for k in range(per):
            i = c * per + k
            rows.append({"cycle_index": 3 + 10 * c, "widx": k, "ws_snr": -20 + (i % 30), "ws_load": 20 + (c % 7), "live_hit": 1 if i % hit_every == 0 else 0,
                         "fault": 0, "G_ok": 1 if (i % 10) < g_rate * 10 else 0, "C3_edge": 1 if edge_every and i % edge_every == 0 else 0,
                         "C1_ok": 0, "C3_ok": 0, "C3S_ok": 0, "G_path": 0, "C3_df": 0.1, "C3_dt": 0.0})
    return rows


def test_v3_edge_share_pass_and_fail():
    assert R.row_v3(_rows(edge_every=0))[0] is True
    assert R.row_v3(_rows(edge_every=20))[0] is True        # 5.0 % exactly: inclusive
    assert R.row_v3(_rows(edge_every=19))[0] is False       # 5.26 %
    assert R.row_v3([])[0] is False


def test_v4_control_must_reproduce_on_live_hit_rows_only():
    assert R.row_v4(_rows(g_rate=0.9))[0] is True
    assert R.row_v4(_rows(g_rate=0.8))[0] is False
    rows = _rows(g_rate=0.5)
    for r in rows:
        r["live_hit"] = 0                                    # no live hits at all: cannot read as a pass
    assert R.row_v4(rows)[0] is False


def test_v5_determinism_pass_and_each_failure_mode():
    main = [dict({c: float(i) for c in R.CSV_COLUMNS}, cycle_index=i // 10, widx=i % 10) for i in range(400)]
    assert R.row_v5(main, [dict(r) for r in main[:300]])[0] is True
    bad = [dict(r) for r in main[:300]]
    bad[7]["C3_df"] += 0.1
    ok, d = R.row_v5(main, bad)
    assert ok is False and d["differing_fields"] == 1
    assert R.row_v5(main, [dict(r) for r in main[:299]])[0] is False
    nan = [dict(r, C3_df=float("nan")) for r in main]
    assert R.row_v5(nan, [dict(r) for r in nan[:300]])[0] is True        # NaN equals NaN


# ---- statistics --------------------------------------------------------------------------------------------------------------------
def _set_success(rows, arm, pred):
    for r in rows:
        r[f"{arm}_ok"] = 1 if pred(r) else 0


def test_net_is_zero_for_identical_arms_and_positive_with_a_diffuse_gain():
    rows = _rows(n_cycles=80, per=10, g_rate=0.6)
    _set_success(rows, "C3", lambda r: r["G_ok"])
    e = R.net_with_ci(rows, "C3")
    assert e["NET_pp"] == 0.0 and e["ci95"] == [0.0, 0.0] and e["n_cycles"] == 80 and e["n_rows"] == 800
    for i, r in enumerate(rows):
        r["C3_ok"] = 1 if r["G_ok"] or i % 10 == 8 else 0     # +10 pp diffuse (i % 10 == 8 is a row G fails)
    e = R.net_with_ci(rows, "C3")
    assert e["NET_pp"] > 5 and e["ci95"][0] > 1.0


def test_gains_and_losses_are_counted_separately_with_cycle_cis():
    rows = _rows(n_cycles=20, per=10, g_rate=0.5)
    _set_success(rows, "C3", lambda r: (not r["G_ok"] and r["widx"] == 7) or (r["G_ok"] and r["widx"] != 2))
    gl = R.gains_losses(rows, "C3")
    assert gl["gains"] == 20 and gl["losses"] == 20 and gl["n"] == 200
    assert gl["gains_pct_of_rows"] == pytest.approx(10.0) and gl["losses_ci95_pct"][0] <= gl["losses_pct_of_rows"] <= gl["losses_ci95_pct"][1]


def test_db_shift_recovers_a_known_horizontal_shift():
    rng = np.random.default_rng(1)
    rows = []
    for snr in range(-24, 12):
        for k in range(200):
            p_g = 1 / (1 + math.exp(-(snr + 10) / 2.0))
            p_c = 1 / (1 + math.exp(-(snr + 12) / 2.0))        # the C3 curve is 2 dB to the left
            rows.append({"ws_snr": snr, "G_ok": int(rng.random() < p_g), "C3_ok": int(rng.random() < p_c), "live_hit": int(rng.random() < p_g)})
    sh = R.db_shift(rows, "C3")
    assert sh["median_db"] == pytest.approx(2.0, abs=0.4)
    same = R.db_shift([dict(r, C3_ok=r["G_ok"]) for r in rows], "C3")
    assert same["median_db"] == pytest.approx(0.0, abs=1e-9)
    g = R.shift_estimator_gain_pp(rows, 2.0)
    assert g is not None and g > 0 and R.shift_estimator_gain_pp(rows, 0.0) == pytest.approx(0.0, abs=1e-9)
    assert R.shift_estimator_gain_pp(rows, None) is None


def test_crossing_edge_cases():
    assert R.crossing([-10, -5, 0], [0.1, 0.5, 0.9], 0.5) == pytest.approx(-5.0)
    assert R.crossing([-10, -5, 0], [0.1, 0.5, 0.9], 0.95) is None
    assert R.crossing([-10, -5, 0], [0.6, 0.7, 0.9], 0.5) is None      # starts above the level: no crossing to measure


def test_strata_structure():
    rows = _rows(n_cycles=60, per=10, g_rate=0.5, hit_every=2)
    _set_success(rows, "C3", lambda r: r["G_ok"])
    s = R.strata(rows)
    assert set(s["by_ws_load_quintile"]) == {"Q1", "Q2", "Q3", "Q4", "Q5"} and "live_misses_only" in s
    assert s["live_misses_only"]["n_rows"] == 300


# ---- end to end through analyse() -----------------------------------------------------------------------------------------------------
def test_osd_arm_report_counts_rescues_wrong_payloads_and_path0():
    rows = _rows(n_cycles=10, per=10, g_rate=0.5)
    for i, r in enumerate(rows):
        bp = 1 if i % 4 == 0 else 0
        # a row can have BP success in one lattice cell AND a corrected-OSD success in another: those are NOT BP-failure rescues
        osd = 1 if ((not bp and i % 4 == 1) or (bp and i % 8 == 0)) else 0
        r.update({"GO_bp_ok": bp, "GO_osd_ok": osd, "GO_ok": int(bp or osd), "GO_wrong": 1 if i % 20 == 2 else 0, "GO_neg0": 1 if i % 50 == 3 else 0})
    rep = R.osd_arm_report(rows, "GO", "G")
    assert rep["n_rows"] == 100 and rep["bp_only_success"] == 25 and rep["bp_fail_rows"] == 75
    assert rep["bp_fail_rows_recovered_true_payload_by_corrected_osd"] == 25      # the 13 rows with BOTH are not counted
    assert rep["rows_corrected_osd_returned_crc_valid_wrong_payload"] == 5 and rep["wrong_pct_of_rows"] == pytest.approx(5.0)
    assert rep["wrong_pct_of_bp_fail_rows"] == pytest.approx(100.0 * 5 / 75) and rep["rows_negated_call_returned_path0"] == 2
    assert set(rep["NET_vs_base"]) >= {"NET_pp", "ci95", "n_cycles"}


def test_osd_arm_fields_are_part_of_the_persisted_columns_and_the_determinism_check():
    for arm in CG.OSD_ARMS:
        for f in CG.OSD_FIELDS:
            assert f"{arm}_{f}" in CG.ROW_FIELDS and f"{arm}_{f}" in R.CSV_COLUMNS
    assert CG.OSD_ARMS == ("GO", "C3O") and CG.NEG_MAX_ITERS == 1


def _write_run(tmp_path, rows, synth=None, v5=None, pins=None, v4p_batch2=None, v4p_ws=None):
    def dump(path, recs, cols):
        with open(path, "w", newline="\n") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in recs:
                w.writerow([r.get(c, "") for c in cols])
    full = []
    for r in rows:
        d = {c: 0 for c in R.CSV_COLUMNS}
        d.update(r)
        full.append(d)
    dump(tmp_path / "rows.csv", full, R.CSV_COLUMNS)
    synth = synth or _synth()
    dump(tmp_path / "synthetic.csv", synth, list(synth[0].keys()))
    dump(tmp_path / "v5.csv", v5 if v5 is not None else full[:300], R.CSV_COLUMNS)
    (tmp_path / "v4p").mkdir(exist_ok=True)
    by = {}
    for d in full:
        by.setdefault(int(d["cycle_index"]), []).append(d)
    lines, tb = ["stamp,wsjtx_idx_batch"], ["run,stamp,kind,band,n,corroborated"]
    for ci, rs in by.items():
        lines.append(f"c{ci}," + ";".join(f"{int(d['widx'])}:{1 if (v4p_batch2 is None or int(d['widx']) not in v4p_batch2) else 2}" for d in rs))
        tb.append(f"x,c{ci},ws,ALL,{int(rs[0]['ws_load']) if v4p_ws is None else v4p_ws},0")
    (tmp_path / "v4p" / "matched_batch.csv").write_text("\n".join(lines) + "\n")
    (tmp_path / "v4p" / "testb.csv").write_text("\n".join(tb) + "\n")
    (tmp_path / "pins.jsonl").write_text("\n".join(json.dumps(p) for p in (pins or _pins())) + "\n")


def _big(n_cycles=60, per=10):
    rows = _rows(n_cycles=n_cycles, per=per, g_rate=0.9, hit_every=1)     # G = 0.90 on live hits: V4's bar, inclusive
    for r in rows:
        r["C1_ok"] = r["G_ok"]
        r["C3S_ok"] = r["G_ok"]
    return rows


def test_end_to_end_no_effect_gives_coh_stop(tmp_path):
    rows = _big()
    _set_success(rows, "C3", lambda r: r["G_ok"])
    _write_run(tmp_path, rows)
    res = R.analyse(str(tmp_path), stamp_of={})
    assert res["failing_rows"] == [] and res["verdict"] == "COH-STOP" and res["estimand"]["NET_C3"]["NET_pp"] == 0.0


def test_end_to_end_a_diffuse_gain_gives_coh_go(tmp_path):
    rows = _big(n_cycles=320)                  # 40 blocks of 8: top-5 of 8 blocks would carry > 1/2 of ANY gain, which is not clustering
    for i, r in enumerate(rows):
        r["C3_ok"] = 1 if r["G_ok"] or i % 10 == 9 else 0              # +10 pp: every row G fails is recovered
    _write_run(tmp_path, rows)
    res = R.analyse(str(tmp_path), stamp_of={})
    assert res["failing_rows"] == [] and res["verdict"] == "COH-GO" and res["estimand"]["NET_C3"]["ci95"][0] >= 1.0
    assert res["descriptive"]["gains_losses"]["C3"]["losses"] == 0 and res["first_paragraph_flags"] == []


def test_end_to_end_a_clustered_gain_near_the_bar_gives_coh_open_and_the_cluster_flag(tmp_path):
    rows = _big(n_cycles=80)
    for r in rows:
        r["C3_ok"] = r["G_ok"]
    gain_cycles = {rows[i]["cycle_index"] for i in range(0, 800, 10)[:6]}      # six cycles carry the whole gain
    for r in rows:
        if r["cycle_index"] in gain_cycles and not r["G_ok"]:
            r["C3_ok"] = 1
    _write_run(tmp_path, rows)
    res = R.analyse(str(tmp_path), stamp_of={})
    assert res["verdict"] in ("COH-OPEN", "COH-GO", "COH-STOP") and res["failing_rows"] == []
    assert res["cluster"]["top5_share_of_positive_sum"] is not None and res["cluster"]["flag_gt_half"] is True
    assert any("top-5 blocks" in f for f in res["first_paragraph_flags"])


def test_end_to_end_a_failed_validity_row_withholds_the_verdict_and_names_it(tmp_path):
    rows = _big()
    for i, r in enumerate(rows):
        r["C3_ok"] = 1 if r["G_ok"] or i % 7 == 0 else 0
    _write_run(tmp_path, rows, synth=_synth(df_err=0.30))                   # an estimator that is NOT merely lobe-ambiguous
    res = R.analyse(str(tmp_path), stamp_of={})
    assert res["verdict"] == "NO VERDICT" and "V2" in res["verdict_withheld_because"]
    _write_run(tmp_path, rows, pins=_pins(sha="0" * 64))
    assert "V1" in R.analyse(str(tmp_path), stamp_of={})["verdict_withheld_because"]
    _write_run(tmp_path, rows, v5=[dict({c: 0 for c in R.CSV_COLUMNS})] * 300)
    assert "V5" in R.analyse(str(tmp_path), stamp_of={})["verdict_withheld_because"]


# ---- selection helpers (pure) ------------------------------------------------------------------------------------------------------
def test_test_b_matching_is_one_to_one_nearest_first_and_text_exact():
    ws = [(0, 0.0, 1000, "A B C"), (0, 0.0, 1004, "A B C"), (0, 0.0, 2000, "X Y Z")]
    ows = [(0, 0.0, 1003, "A B C"), (0, 0.0, 2005, "X Y Z"), (0, 0.0, 2000, "X Y W")]
    assert SEL.test_b_matches(ws, ows) == [False, True, True]         # OWS 1003 is nearer to 1004; WSJT-X 1000 stays unmatched; the text must be exact
    assert SEL.test_b_matches(ws, []) == [False, False, False]
    assert SEL.test_b_matches([(0, 0.0, 1000, "A B C")], [(0, 0.0, 1011, "A B C")]) == [False]     # |df| 11 > 10
    assert SEL.test_b_matches([(0, 0.0, 1000, "A B C")], [(0, 0.0, 1010, "A B C")]) == [True]      # |df| 10 inclusive


def test_text_feature_is_a_coarse_feature_never_the_text():
    assert SEL.text_feature("CQ <...> AB12") == "hashed_call_token"
    assert SEL.text_feature("SOMETHING ELSE") == "other_unencodable"


# ---- anchor mapping and the synthetic set -----------------------------------------------------------------------------------------
def test_anchor_mapping_is_ws_dt_plus_delta_raw():
    assert CG.anchor_time(0.3) == pytest.approx(1.0) and CG.anchor_time(-2.3) == pytest.approx(-1.6)


def test_synthetic_set_is_the_frozen_one_and_is_off_lattice_with_the_specified_ranges():
    spec = json.loads((CGD / "synthetic_set.json").read_bytes())
    assert len(spec) == 200 and SY.build_set() == spec                    # deterministic: regenerating gives the committed set
    for s in spec:
        assert abs(s["df_off"]) <= 1.5 and abs(s["dt_off"]) <= 0.06 and s["snr_db"] == -14.0
        assert s["message"].count("Q") >= 1                               # Q-prefix synthetic calls only
    assert max(abs(s["df_off"]) for s in spec) > 1.2 and min(abs(s["df_off"]) for s in spec) < 0.3   # spans the range, not a point


DLL = Path(__file__).resolve().parents[2] / "artefacts" / "rr_2026-10-06_coh_gain" / "bin" / "libft8_20260058.dll"


@pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
def test_evaluate_signal_on_a_clean_synthetic_signal_decodes_in_every_arm_and_the_bit_convention_holds():
    dec = CG.load_decoder(str(DLL))
    s = json.loads((CGD / "synthetic_set.json").read_bytes())[0]
    s = dict(s, snr_db=0.0)
    out = SY.evaluate(dec, s)
    assert out["fault"] == 0 and out["G_ok"] == out["C1_ok"] == out["C3_ok"] == out["C3S_ok"] == 1
    assert out["C3_nbe"] <= 2 and out["C3S_nbe"] <= 2          # bit errors counted with positive LLR = bit 1 (BP's sense): small on a clean signal
    assert "message" not in out and all(isinstance(v, (int, float)) for v in out.values())    # numeric only: no text leaves the function


@pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
def test_a_wrong_dll_pin_is_refused(tmp_path):
    bad = tmp_path / "x.dll"
    bad.write_bytes(DLL.read_bytes() + b"\0")
    with pytest.raises(Exception):
        CG.load_decoder(str(bad))


def test_frozen_files_match_their_pins_in_code():
    assert CG.sha256_lf(str(RESULTS / "rows.json")) == CG.ROWS_JSON_SHA256
    assert CG.sha256_lf(str(CGD / "synthetic_set.json")) == CG.SYNTH_SHA256
    assert CG.sha256_lf(str(CGD / "synthetic_set_t.json")) == CG.SYNTH_T_SHA256


def test_v2t_tier_is_the_amendment_1_one_and_distinct_from_the_gated_set():
    t = json.loads((CGD / "synthetic_set_t.json").read_bytes())
    g = json.loads((CGD / "synthetic_set.json").read_bytes())
    assert len(t) == 200 and all(s["snr_db"] == -20.0 for s in t) and SY.build_set(SY.LABEL_T, CG.V2T_N, CG.V2T_SNR_DB) == t
    assert SY.LABEL_T == "COH-GAIN-V2T" and {s["seed"] for s in t}.isdisjoint({s["seed"] for s in g})


def test_rescaled_net_credits_zero_gain_to_the_excluded_rows():
    counts = {"rows_mod10": 9524, "excluded_before_extraction": {"hashed_call_token": 523, "other_unencodable": 113}}
    out = R.rescaled_net({"NET_pp": 2.0, "ci95": [1.0, 3.0]}, counts, 10)
    f = 9524 / (9524 + 636)
    assert out["NET_pp_all_decodes"] == pytest.approx(2.0 * f) and out["ci95_all_decodes"] == [pytest.approx(f), pytest.approx(3.0 * f)]
    assert out["NET_pp_encodable"] == 2.0 and out["excluded_rows_mod10"] == 636
    assert R.rescaled_net({"NET_pp": 0.0, "ci95": [0.0, 0.0]}, counts, 10)["NET_pp_all_decodes"] == 0.0


def test_v2_reevaluation_uses_the_stored_estimates_and_the_true_offsets_with_no_rerender(tmp_path):
    spec = json.loads((CGD / "synthetic_set.json").read_bytes())
    p = tmp_path / "s.csv"
    with open(p, "w", newline="\n") as fh:
        w = csv.writer(fh)
        w.writerow(["i", "fault", "C3_df", "C3_dt"])
        for s in spec:
            w.writerow([s["i"], 0, s["df_off"] + 0.03, s["dt_off"] - 0.002])      # estimates = truth + a constant bias
    recs = R.load_synth(str(p), str(CGD / "synthetic_set.json"))
    assert all(r["err_df_signed"] == pytest.approx(0.03) and r["err_dt_signed"] == pytest.approx(-0.002) for r in recs)


def test_v4_uses_live_hit_rows_only_not_the_whole_population():
    rows = _rows(n_cycles=20, per=10, g_rate=1.0, hit_every=2)
    for r in rows:
        if int(r["live_hit"]) == 0:
            r["G_ok"] = 0                                     # G fails on every live MISS, succeeds on every live HIT
    ok, d = R.row_v4(rows)
    assert ok is True and d["G_success_on_live_hits"] == 1.0 and d["n_live_hits"] == 100     # the whole-population rate would be 0.5
    for r in rows:
        r["G_ok"] = 0 if int(r["live_hit"]) == 1 else 1       # the opposite: fails on hits, succeeds on misses
    assert R.row_v4(rows)[0] is False


PROBES = CGD.parent / "nhard-rep" / "probe_vectors.json"


@pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
def test_corrected_osd_arm_on_the_calibrated_vectors():
    """The V2' vectors are built in OSD's own sign (positive = bit 0). NEGATING them gives the production sense (positive = bit 1): BP on that cannot decode the
    26 / 52 pivot sign errors, and the corrected OSD (which negates back) is gated by nhard exactly as calibrated: P_lo (26) accepted, P_hi (52) rejected at 40."""
    dec = CG.load_decoder(str(DLL))
    j = json.loads(PROBES.read_bytes())
    text = j["message"]
    truth = dec.true_codeword(text)[:77]
    shipped = {n: [-x for x in j["vectors"][n]["llr"]] for n in ("P_lo", "P_hi")}
    lo = CG.corrected_osd_arm(dec, [shipped["P_lo"]], text, truth)
    assert (lo["ok"], lo["bp_ok"], lo["osd_ok"], lo["wrong"], lo["neg0"]) == (1, 0, 1, 0, 0)
    hi = CG.corrected_osd_arm(dec, [shipped["P_hi"]], text, truth)
    assert (hi["ok"], hi["osd_ok"], hi["wrong"]) == (0, 0, 0)                      # 52 errors > nhard 40: the gate rejects
    other = dec.true_codeword("Q4XYZ Q1ABC -07")[:77]
    wrong = CG.corrected_osd_arm(dec, [shipped["P_lo"]], "Q4XYZ Q1ABC -07", other)
    assert (wrong["ok"], wrong["osd_ok"], wrong["wrong"]) == (0, 0, 1)             # CRC-valid, but not the payload that was sent
    assert CG.corrected_osd_arm(dec, [], text, truth)["ok"] == 0


@pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
def test_evaluate_signal_carries_the_osd_arms_and_a_clean_signal_is_a_bp_success():
    dec = CG.load_decoder(str(DLL))
    s = dict(json.loads((CGD / "synthetic_set.json").read_bytes())[0], snr_db=0.0)
    out = SY.evaluate(dec, s)
    for arm in CG.OSD_ARMS:
        assert out[f"{arm}_ok"] == 1 and out[f"{arm}_bp_ok"] == 1 and out[f"{arm}_wrong"] == 0 and out[f"{arm}_neg0"] == 0


@pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
def test_corrected_osd_arm_a_negated_call_that_converges_in_bp_is_counted_and_is_a_failure():
    """Hand the arm a CLEAN vector in OSD's sign (positive = bit 0). BP on it fails (it sees the complement), so the arm negates it; the negated vector is a clean
    BP-sign vector and BP converges in one iteration: path 0 on the negated call. That is COUNTED (neg0) and is NOT a success."""
    dec = CG.load_decoder(str(DLL))
    j = json.loads(PROBES.read_bytes())
    cw = np.array(j["codeword_bits"])
    clean_osd_sign = list(np.where(cw == 0, 4.0, -4.0))
    truth = dec.true_codeword(j["message"])[:77]
    out = CG.corrected_osd_arm(dec, [clean_osd_sign], j["message"], truth)
    assert out["neg0"] == 1 and out["ok"] == 0 and out["osd_ok"] == 0 and out["wrong"] == 0 and out["bp_ok"] == 0
    shipped_clean = list(np.where(cw == 1, 4.0, -4.0))                     # a clean vector in the SHIPPED sense: BP converges, OSD is never reached
    ok = CG.corrected_osd_arm(dec, [shipped_clean], j["message"], truth)
    assert ok["bp_ok"] == 1 and ok["ok"] == 1 and ok["neg0"] == 0 and ok["osd_ok"] == 0


# ---- V4' (Amendment 3) ---------------------------------------------------------------------------------------------------------------
def _v4p_inputs(n_cycles=20, per=10, g_on_b1=1.0, g_on_b2=0.0):
    """Rows where the replay matched widx 0..7 in batch 1 and widx 8..9 in batch 2; G reads batch-1 rows with rate g_on_b1 and batch-2 rows with g_on_b2."""
    rows, mb, ws, stamp_of = [], {}, {}, {}
    j1 = 0
    for c in range(n_cycles):
        ci = 3 + 10 * c
        st = f"2610{c:02d}_000000"
        stamp_of[ci] = st
        ws[st] = per
        mb[st] = {k: (1 if k < 8 else 2) for k in range(per)}
        for k in range(per):
            rate = g_on_b1 if k < 8 else g_on_b2
            g_ok = 1 if (j1 % 10) < rate * 10 else 0          # a running counter over the rows of the class: exact rates, independent of widx
            j1 += 1 if k < 8 else 0
            rows.append({"cycle_index": ci, "widx": k, "ws_load": per, "fault": 0, "G_ok": g_ok})
    return rows, mb, stamp_of, ws


def test_v4p_passes_on_batch1_rows_even_when_the_whole_population_would_fail_v4():
    rows, mb, st, ws = _v4p_inputs(g_on_b1=0.95, g_on_b2=0.0)
    ok, d = R.row_v4p(rows, mb, st, ws)
    assert ok is True and d["P1_n"] == 160 and d["G_success_on_P1"] >= 0.90 and d["batch2_rows_n"] == 40
    assert d["replay_batch2_share_of_matches"] == pytest.approx(0.2) and d["G_success_on_batch2_only"] == 0.0
    whole = sum(r["G_ok"] for r in rows) / len(rows)
    assert whole < 0.90                                    # the original V4's population rate: the pre-subtraction bar the Architect withdrew


def test_v4p_bar_is_unchanged_and_inclusive_and_fails_below_it():
    rows, mb, st, ws = _v4p_inputs(g_on_b1=0.9)
    assert R.row_v4p(rows, mb, st, ws)[0] is True          # exactly 0.90 on P1
    rows, mb, st, ws = _v4p_inputs(g_on_b1=0.8)
    ok, d = R.row_v4p(rows, mb, st, ws)
    assert ok is False and d["G_success_on_P1"] == pytest.approx(0.8)


def test_v4p_fails_on_an_empty_p1_and_on_a_ws_count_mismatch_between_replay_and_row_list():
    rows, mb, st, ws = _v4p_inputs(g_on_b1=1.0)
    assert R.row_v4p(rows, {}, st, ws)[0] is False                                   # the replay matched nothing: cannot read as a pass
    ws2 = dict(ws)
    ws2[st[3]] = 11                                                                  # the replay saw a different number of WSJT-X lines in one cycle
    ok, d = R.row_v4p(rows, mb, st, ws2)
    assert ok is False and d["ws_count_mismatch_cycles"] == 1
    assert R.row_v4p(rows, mb, st, {})[0] is False                                   # no replay counts at all


def test_load_matched_batch_parses_the_harness_file(tmp_path):
    f = tmp_path / "mb.csv"
    f.write_text("stamp,wsjtx_idx_batch\n261004_163415,\n261004_163430,0:1;3:2;7:1\n", encoding="utf-8")
    d = R.load_matched_batch(str(f))
    assert d["261004_163415"] == {} and d["261004_163430"] == {0: 1, 3: 2, 7: 1} and R.load_matched_batch(str(tmp_path / "x.csv")) == {}


def test_end_to_end_v4p_replaces_v4_as_the_gate_and_v4_stays_a_diagnostic(tmp_path):
    rows = _big(n_cycles=320)
    for i, r in enumerate(rows):
        r["C3_ok"] = 1 if r["G_ok"] or i % 10 == 9 else 0
    # G (0.90 overall in _big) is unreadable on batch-2 matches: mark widx 9 as batch 2 (G fails there by construction: i % 10 == 9)
    _write_run(tmp_path, rows, v4p_batch2={9})
    res = R.analyse(str(tmp_path), stamp_of={})
    assert "V4" not in res["validity"] and res["validity"]["V4P"]["P1_n"] == 2880 and res["validity"]["V4P"]["G_success_on_P1"] == 1.0
    assert res["failing_rows"] == [] and res["verdict"] == "COH-GO"
    assert res["v4_retired_diagnostic_whole_live_hit_population"]["G_success_on_live_hits"] == pytest.approx(0.9)
    _write_run(tmp_path, rows, v4p_ws=99)
    assert "V4P" in R.analyse(str(tmp_path), stamp_of={})["verdict_withheld_because"]


def test_analysis_never_overwrites_the_frozen_row_list(tmp_path):
    """Regression: the first analysis run wrote its result to rows.json, the frozen row list's own name, in the same results folder."""
    assert R.ANALYSIS_NAME != "rows.json"
    rows = _big(n_cycles=40)
    for r in rows:
        r["C3_ok"] = r["G_ok"]
    _write_run(tmp_path, rows)
    res_dir = tmp_path / "results"
    frozen = res_dir / "rows.json"
    res_dir.mkdir()
    frozen.write_text("FROZEN")
    R.analyse(str(tmp_path), str(res_dir), stamp_of={})
    assert frozen.read_text() == "FROZEN" and (res_dir / R.ANALYSIS_NAME).exists()


def test_v4p_replay_list_is_the_309_cycles_of_the_frozen_row_list_in_order():
    import cg_v4p as V
    cycles = V.sampled_cycles()
    spec = json.loads((RESULTS / "rows.json").read_bytes())
    by_index = {}
    for r in spec["rows"]:
        by_index.setdefault(r[0], r[1])
    assert len(cycles) == 309 == len(by_index) and cycles == [by_index[i] for i in sorted(by_index)] and len(set(cycles)) == 309
    assert V.DLL == CG.DLL_PIN and V.BUILD_COMMIT == "be3cc5ac" and V.THREADS == "8"
