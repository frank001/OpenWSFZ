"""Tests for qa/rr-study/nhard-rep/nhard_rep_n0_rows.py (NHARD-REP Amendment 3, OSD-OFF: arm N0 at nhard 0 paired with the existing N40).

HK-026 / HK-021 (k): every row is exercised on an input that makes it PASS and one that makes it FAIL. The BLIND-INSTRUMENT case is tested explicitly: if nhard 0 never reached the gate, N0
equals N40, CI [0, 0], which clears the -0.10 margin and would read O-SAFE; V2'' must then withhold the verdict. All data is synthetic and numeric (NFR-021 / HK-037).
"""
import json
import sys
from pathlib import Path

import pytest

NH = Path(__file__).resolve().parent.parent / "rr-study" / "nhard-rep"
sys.path.insert(0, str(NH))
import nhard_rep_n0_rows as R  # noqa: E402
import nhard_rep_rows as NR  # noqa: E402

SELECTION = Path(__file__).resolve().parent.parent / "rr-study" / "results" / "2026-10-06-nhard-rep" / "selection.json"


def test_frozen_constants():
    assert R.BAR_SAFE_MARGIN_PP == 0.10 and R.ARM == "N0" and R.ARM_NHARD == 0 and R.PAIRED_ARM == "N40"      # 0.10 pp ratified by the Captain ~18:20Z, FROZEN
    assert NR.SEED == 20261006 and NR.BLOCK_REGISTERED == 8 and NR.B_RESAMPLES == 10_000
    assert NR.DLL_PIN == "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365"


@pytest.mark.parametrize("lo,hi,row", [
    (-0.5, -0.0001, "O-HARM"), (-0.9, -0.2, "O-HARM"),      # CI_hi < 0 fires first, even though CI_lo is far below the margin
    (0.0001, 0.6, "O-GAIN"), (0.2, 0.9, "O-GAIN"),
    (-0.10, 0.2, "O-SAFE"), (-0.05, 0.05, "O-SAFE"), (0.0, 0.3, "O-SAFE"),   # CI_lo == -0.10 inclusive; CI_lo == 0 is not > 0
    (-0.1001, 0.2, "O-OPEN"), (-0.4, 0.3, "O-OPEN"),
])
def test_verdict_rows_are_exclusive_in_the_specs_order_and_boundaries_are_right(lo, hi, row):
    assert R.verdict_row(lo, hi) == row


def test_harm_wins_over_safe_when_the_whole_interval_is_negative_but_within_the_margin():
    assert R.verdict_row(-0.09, -0.01) == "O-HARM"          # CI_lo >= -0.10 would say SAFE, but CI_hi < 0 is checked first


def _pins(arm="N0", sha=None):
    return [{"arm": arm, "when": w, "libft8_sha256": sha or NR.DLL_PIN, "pinned": NR.DLL_PIN} for w in ("start", "end")]


def test_v1():
    assert R.row_v1(_pins())[0] is True
    assert R.row_v1(_pins(sha="0" * 64))[0] is False
    assert R.row_v1(_pins()[:1])[0] is False
    assert R.row_v1(_pins(arm="N40"))[0] is False             # another arm's pins do not stand in for N0's


def _probe(lo_path, hi_path, lo_crc=None, points=("start", "end"), match=None):
    rows = []
    for w in points:
        for v, p in (("P_lo", lo_path), ("P_hi", hi_path)):
            acc = p == 1
            rows.append({"when": w, "vec": v, "rc": 0, "path": p, "crc_ok": 1 if acc else 0, "payload_match": acc if match is None else match})
    return rows


N0_OK = _probe(-1, -1)
N40_OK = _probe(1, -1)


def test_v2pp_passes_only_when_both_vectors_are_rejected_in_n0_and_p_lo_was_accepted_in_n40():
    assert R.row_v2pp(N0_OK, N40_OK)[0] is True
    assert R.row_v2pp(_probe(1, -1), N40_OK)[0] is False                  # BLIND INSTRUMENT: P_lo still accepted at "0": the setting never reached the gate
    assert R.row_v2pp(_probe(-1, 1), N40_OK)[0] is False                  # P_hi accepted at 0
    assert R.row_v2pp(N0_OK, _probe(-1, -1))[0] is False                  # no contrast: N40's P_lo was not accepted either
    assert R.row_v2pp(_probe(-1, -1, points=("start",)), N40_OK)[0] is False       # no END probe in N0
    assert R.row_v2pp([], N40_OK)[0] is False and R.row_v2pp(N0_OK, [])[0] is False  # an absent file never reads as a pass


def test_v3_v4_v5():
    assert R.row_v3([{"exception": ""}] * 5, 0, 0)[0] is True
    assert R.row_v3([{"exception": "X"}], 0, 0)[0] is False and R.row_v3([], 1, 0)[0] is False and R.row_v3([], 0, 1)[0] is False
    rb = [{"when": w, "subtractionEnabled": True, "threadsConfigured": "8", "threadsResolved": "8", "cores": 16, "nhard": 0} for w in ("start", "end")]
    assert R.row_v4(rb, NR.SELECTION_SHA256, NR.PROBE_SHA256)[0] is True
    assert R.row_v4([dict(r, nhard=40) for r in rb], NR.SELECTION_SHA256, NR.PROBE_SHA256)[0] is False       # N0 that ran at 40
    assert R.row_v4([dict(r, subtractionEnabled=False) for r in rb], NR.SELECTION_SHA256, NR.PROBE_SHA256)[0] is False
    assert R.row_v4(rb[:1], NR.SELECTION_SHA256, NR.PROBE_SHA256)[0] is False
    assert R.row_v4(rb, "0" * 64, NR.PROBE_SHA256)[0] is False and R.row_v4(rb, NR.SELECTION_SHA256, "0" * 64)[0] is False
    stamps = [f"261004_{i:06d}" for i in range(100)]
    ok = {s: {"ran": True, "abandoned": i < 5, "contained": False} for i, s in enumerate(stamps)}
    assert R.row_v5(ok, stamps)[0] is True
    assert R.row_v5({s: dict(a, abandoned=i < 6) for i, (s, a) in enumerate(ok.items())}, stamps)[0] is False
    assert R.row_v5({}, stamps)[0] is False


# ---- end to end -------------------------------------------------------------------------------------------------------------------------------
def _write_arm(d, arm, stamps, W, M, n_extra=0, abandoned=()):
    tb, mt, ab, rr = ["run,stamp,kind,band,n,corroborated"], ["stamp,wsjtx_idx"], ["stamp,ran,abandoned,contained"], \
        ["run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n"]
    for i, s in enumerate(stamps):
        m = M[i]
        for kind in ("b1", "b2"):
            for band in "ABCD":
                n = c = 0
                if band == "B" and kind == "b1":
                    n, c = m + n_extra, m
                tb.append(f"x,{s},{kind},{band},{n},{c}")
        tb.append(f"x,{s},ws,ALL,{W[i]},{m}")
        mt.append(f"{s},{';'.join(str(x) for x in range(m))}")
        ab.append(f"{s},1,{int(s in abandoned)},0")
        rr.append(f"x,S,{s},{i},ON,100.0,{m + n_extra},,50.0,{m + n_extra},0")
    for name, lines in (("testb", tb), ("matched", mt), ("abandon", ab), ("run", rr)):
        (d / f"{name}_{arm}.csv").write_text("\n".join(lines) + "\n")


def _setup(tmp_path, m0_delta=0, n_extra0=0, probe0=None, probe40=None, nhard0=0, sel_stamps=None):
    s = json.loads(SELECTION.read_bytes())
    stamps = s["runs"][s["run"]]["SAMPLE"]
    n0d, n40d = tmp_path / "n0", tmp_path / "n40"
    n0d.mkdir()
    n40d.mkdir()
    W = [30] * len(stamps)
    M40 = [10] * len(stamps)
    M0 = [10 + (m0_delta if (i % 3 == 0 and m0_delta) else 0) for i in range(len(stamps))]
    _write_arm(n40d, "N40", stamps, W, M40, n_extra=2)
    _write_arm(n0d, "N0", stamps, W, M0, n_extra=n_extra0)
    for d, arm, rows in ((n0d, "N0", probe0 or N0_OK), (n40d, "N40", probe40 or N40_OK)):
        lines = ["when,vec,rc,path,crc_ok,payload_match,expected"] + [f"{r['when']},{r['vec']},{r['rc']},{r['path']},{r['crc_ok']},{int(r['payload_match'])},-" for r in rows]
        (d / f"probe_{arm}.csv").write_text("\n".join(lines) + "\n")
    (n0d / "log_N0.log").write_text("\n".join(f"# readback {w} subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard={nhard0}" for w in ("start", "end")) + "\n")
    (n0d / "pins.jsonl").write_text("\n".join(json.dumps(p) for p in _pins()) + "\n")
    return n0d, n40d


def test_end_to_end_no_change_gives_o_safe(tmp_path):
    n0, n40 = _setup(tmp_path)
    res = R.analyse(str(n0), str(n40), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "O-SAFE" and res["estimand"]["NET_0_pp"] == 0.0


def test_end_to_end_a_real_gain_gives_o_gain_and_fewer_not_confirmed(tmp_path):
    n0, n40 = _setup(tmp_path, m0_delta=1)
    res = R.analyse(str(n0), str(n40), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "O-GAIN" and res["estimand"]["ci95"][0] > 0
    assert res["descriptive"]["K_minus_G"] > 0 and res["descriptive"]["not_confirmed_per_cycle"]["N0"] < res["descriptive"]["not_confirmed_per_cycle"]["N40"]


def test_end_to_end_a_real_loss_gives_o_harm(tmp_path):
    n0, n40 = _setup(tmp_path, m0_delta=-1)
    res = R.analyse(str(n0), str(n40), selection_path=str(SELECTION))
    assert res["failing_rows"] == [] and res["verdict"] == "O-HARM" and res["estimand"]["ci95"][1] < 0


def test_end_to_end_the_blind_instrument_case_is_caught_by_v2pp_and_never_reads_o_safe(tmp_path):
    n0, n40 = _setup(tmp_path, probe0=N40_OK)                  # "N0" whose probe still ACCEPTS P_lo: nhard 0 never applied; the data equals N40, CI [0, 0]
    res = R.analyse(str(n0), str(n40), selection_path=str(SELECTION))
    assert res["estimand"]["ci95"] == [0.0, 0.0]               # the instrument's own reading WOULD clear -0.10 ...
    assert res["verdict"] == "NO VERDICT" and "V2pp" in res["verdict_withheld_because"]    # ... and V2'' withholds it


def test_end_to_end_other_failures_withhold_the_verdict(tmp_path):
    n0, n40 = _setup(tmp_path, nhard0=40)
    assert "V4" in R.analyse(str(n0), str(n40), selection_path=str(SELECTION))["verdict_withheld_because"]
    n0b, n40b = _setup(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path, m0_delta=1)
    (n0b / "pins.jsonl").write_text("")
    assert "V1" in R.analyse(str(n0b), str(n40b), selection_path=str(SELECTION))["verdict_withheld_because"]


def test_the_analysis_never_overwrites_the_frozen_selection_or_the_closed_rows_json(tmp_path):
    n0, n40 = _setup(tmp_path)
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    (res_dir / "rows.json").write_text("CLOSED")
    R.analyse(str(n0), str(n40), str(res_dir), selection_path=str(SELECTION))
    assert (res_dir / "rows.json").read_text() == "CLOSED" and (res_dir / "n0_analysis.json").exists()
