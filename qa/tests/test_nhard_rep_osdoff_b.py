"""Tests for qa/rr-study/nhard-rep/nhard_rep_osdoff_b.py (the OSD-OFF confirmation on fresh cycles, pooled with the first sample).

HK-026 / HK-021 (k): the pooled estimate is shown to equal the single-sample estimate for one sample and to be row-weighted; the verdict rows are the closed ones; a blind arm is withheld.
Synthetic numeric data only (NFR-021 / HK-037).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

TESTS = Path(__file__).resolve().parent
NH = TESTS.parent / "rr-study" / "nhard-rep"
sys.path.insert(0, str(NH))
sys.path.insert(0, str(TESTS))
import nhard_rep_osdoff_b as B  # noqa: E402
import nhard_rep_n0_rows as NZ  # noqa: E402
import nhard_rep_rows as NR  # noqa: E402
import test_nhard_rep_n0_rows as T  # noqa: E402  (its synthetic-file helpers)

SELECTION = T.SELECTION


def test_constants_and_the_fresh_stratum_is_the_frozen_reserve():
    assert B.STRATUM == "SAMPLE_B" and dict(B.ARMS) == {"N40B": 40, "N0B": 0} and B.V2PP_FAIL_RC == 5
    s = json.loads(SELECTION.read_bytes())
    a, b = s["runs"][s["run"]]["SAMPLE"], s["runs"][s["run"]]["SAMPLE_B"]
    full = s["runs"][s["run"]]["FULL"]
    assert set(a).isdisjoint(b) and len(b) == 310 and b == [x for i, x in enumerate(full) if i % 10 == 5]


def test_pooled_with_one_sample_equals_the_closed_single_sample_estimate():
    rng = np.random.default_rng(3)
    W = rng.integers(20, 40, 120).astype(float)
    M40 = rng.integers(5, 15, 120).astype(float)
    M0 = M40 + rng.integers(-1, 2, 120)
    lo, hi, nb = NR.ci(W, M40, M0)
    p = B.pooled_o([(W, M40, M0)])
    assert p["NET_0_pp"] == pytest.approx(NR.net_pp(W, M40, M0)) and p["ci95"] == pytest.approx([lo, hi]) and p["n_blocks"] == nb


def test_pooled_keeps_blocks_within_samples_and_weights_by_rows():
    a = (np.full(20, 30.0), np.full(20, 10.0), np.full(20, 10.0) + 1)            # 20 cycles, +1 each: +3.33 pp
    b = (np.full(60, 30.0), np.full(60, 10.0), np.full(60, 10.0))               # 60 cycles, no change
    p = B.pooled_o([a, b])
    assert p["n_blocks"] == 3 + 8 and p["n_cycles"] == 80                         # 8,8,4 and 8*7+4: partial blocks stay inside their sample
    assert p["NET_0_pp"] == pytest.approx(100.0 * 20 / (30 * 80))                 # 20 gained over 2,400 WSJT-X decodes, not the mean of 3.33 and 0


def _world(tmp_path, delta_b=0, blind=False):
    s = json.loads(SELECTION.read_bytes())
    first_stamps, b_stamps = s["runs"][s["run"]]["SAMPLE"], s["runs"][s["run"]]["SAMPLE_B"]
    f0, f40, bd = tmp_path / "f0", tmp_path / "f40", tmp_path / "b"
    for d in (f0, f40, bd):
        d.mkdir()
    W = [30] * len(first_stamps)
    T._write_arm(f40, "N40", first_stamps, W, [10] * len(first_stamps), n_extra=2)
    T._write_arm(f0, "N0", first_stamps, W, [10 + (1 if i % 3 == 0 else 0) for i in range(len(first_stamps))])
    Wb = [30] * len(b_stamps)
    T._write_arm(bd, "N40B", b_stamps, Wb, [10] * len(b_stamps), n_extra=2)
    T._write_arm(bd, "N0B", b_stamps, Wb, [10 + (delta_b if (i % 3 == 0 and delta_b) else 0) for i in range(len(b_stamps))])
    probe40 = T.N40_OK
    probe0 = T.N40_OK if blind else T.N0_OK
    for d, arm, rows in ((bd, "N40B", probe40), (bd, "N0B", probe0)):
        (d / f"probe_{arm}.csv").write_text("when,vec,rc,path,crc_ok,payload_match,expected\n" + "".join(
            f"{r['when']},{r['vec']},{r['rc']},{r['path']},{r['crc_ok']},{int(r['payload_match'])},-\n" for r in rows))
    (bd / "log_N0B.log").write_text("\n".join(f"# readback {w} subtractionEnabled=True threadsConfigured=8 threadsResolved=8 cores=16 nhard=0" for w in ("start", "end")) + "\n")
    (bd / "pins.jsonl").write_text("\n".join(json.dumps(p) for p in T._pins(arm="N0B")) + "\n")
    return str(bd), str(f0), str(f40)


def test_score_pooled_gain_and_fresh_replication(tmp_path):
    bd, f0, f40 = _world(tmp_path, delta_b=1)
    out = B.score(bd, f0, f40, first_analysis_failing=[], selection_path=str(SELECTION))
    assert out["fresh_sample_alone"]["failing_rows"] == [] and out["fresh_sample_alone"]["verdict"] == "O-GAIN"
    assert out["pooled_verdict"] == "O-GAIN" and out["pooled"]["n_cycles"] == 311 + 310


def test_score_no_change_in_the_fresh_sample_dilutes_the_pooled_gain_and_reads_o_safe_or_gain_by_the_rows(tmp_path):
    bd, f0, f40 = _world(tmp_path, delta_b=0)
    out = B.score(bd, f0, f40, first_analysis_failing=[], selection_path=str(SELECTION))
    assert out["fresh_sample_alone"]["verdict"] == "O-SAFE" and out["fresh_sample_alone"]["estimand"]["NET_0_pp"] == 0.0
    assert out["pooled_verdict"] in ("O-GAIN", "O-SAFE") and out["pooled"]["NET_0_pp"] > 0


def test_score_a_blind_fresh_arm_is_withheld_never_o_safe(tmp_path):
    bd, f0, f40 = _world(tmp_path, delta_b=0, blind=True)
    out = B.score(bd, f0, f40, first_analysis_failing=[], selection_path=str(SELECTION))
    assert out["pooled_verdict"] == "NO VERDICT" and "fresh:V2pp" in out["verdict_withheld_because"]


def test_score_a_first_sample_failure_withholds_the_pooled_verdict(tmp_path):
    bd, f0, f40 = _world(tmp_path, delta_b=1)
    out = B.score(bd, f0, f40, first_analysis_failing=["V5"], selection_path=str(SELECTION))
    assert out["pooled_verdict"] == "NO VERDICT" and "first:V5" in out["verdict_withheld_because"]


def test_score_writes_a_distinct_analysis_name(tmp_path):
    bd, f0, f40 = _world(tmp_path, delta_b=1)
    res = tmp_path / "res"
    res.mkdir()
    (res / "n0_analysis.json").write_text("CLOSED")
    B.score(bd, f0, f40, str(res), first_analysis_failing=[], selection_path=str(SELECTION))
    assert (res / "n0_analysis.json").read_text() == "CLOSED" and (res / B.B_ANALYSIS).exists()
