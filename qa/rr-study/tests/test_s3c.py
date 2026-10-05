"""S3c start-time edge guard: design, point rule, k*, determinism, scoring (no audio, no station)."""
import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RR = Path(__file__).resolve().parents[1]
for p in (str(RR / "s3c"), str(RR), str(RR / "lateness-edge")):
    if p not in sys.path:
        sys.path.insert(0, p)

import s3c_design as S  # noqa: E402
import s3c_score as SC  # noqa: E402

SCENARIO = RR / "scenarios" / "s3c-edge-guard.json"


@pytest.fixture(scope="module")
def scen():
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


def test_points_are_the_architects_ruled_points(scen):
    assert scen["points"] == {"S3c-L90": 2.75, "S3c-L50": 3.0, "S3c-E90": -1.75, "S3c-E50": -2.0}


def test_pick_points_moves_outward_when_edges_equal_and_not_otherwise():
    def edges(e90, e50, e90e, e50e):
        mk = lambda v: {"edge": v, "label": f"{v:+.2f}"}
        return {"edges": {"owsfz": {"E90(snr=-8)": mk(e90), "E50(snr=-8)": mk(e50),
                                     "E90e(snr=-8)": mk(e90e), "E50e(snr=-8)": mk(e50e)}}}
    assert S.pick_points(edges(2.75, 2.75, -1.75, -1.75)) == \
        {"S3c-L90": 2.75, "S3c-L50": 3.0, "S3c-E90": -1.75, "S3c-E50": -2.0}
    assert S.pick_points(edges(2.5, 2.75, -1.5, -1.75)) == \
        {"S3c-L90": 2.5, "S3c-L50": 2.75, "S3c-E90": -1.5, "S3c-E50": -1.75}


def test_pick_points_refuses_an_edge_beyond_the_grid():
    mk = lambda v, l: {"edge": v, "label": l}
    bad = {"edges": {"owsfz": {"E90(snr=-8)": mk(6.0, "> 6.00"), "E50(snr=-8)": mk(6.0, "> 6.00"),
                                "E90e(snr=-8)": mk(-1.0, "-1.00"), "E50e(snr=-8)": mk(-1.0, "-1.00")}}}
    with pytest.raises(AssertionError):
        S.pick_points(bad)


def test_k_star_known_values_and_the_zero_row():
    assert S.k_star(0.8928208002353198) == 24
    assert S.k_star(0.28165331009809136) == 4
    assert S.k_star(0.8425573603233156) == 22
    assert S.k_star(0.0) == 0                      # cannot fail: DESCRIPTIVE
    # defining property of k*: P(X<k*) <= 0.01 < P(X<k*+1)
    for r in (0.28165331009809136, 0.8428, 0.8928208002353198):
        k = S.k_star(r)
        assert S.binom_cdf_lt(k, 32, r) <= 0.01 < S.binom_cdf_lt(k + 1, 32, r)


def test_reference_rows_and_descriptive_labels(scen):
    ref = scen["reference"]
    assert ref["S3c-L50"]["OpenWSFZ"]["descriptive"] and ref["S3c-L50"]["WSJT-X"]["descriptive"]
    for part in ("S3c-L90", "S3c-E90", "S3c-E50"):
        for dec in ("OpenWSFZ", "WSJT-X"):
            assert not ref[part][dec]["descriptive"]
    assert ref["S3c-E50"]["OpenWSFZ"]["k_star"] == 4   # the weak guard (r_ref 0.28), recorded not hidden


def test_layout_12_cycles_8_planted_32_per_part(scen):
    d = scen["design"]
    assert len(d["cycles"]) == 12 and sum(c["planted"] for c in d["cycles"]) == 8
    assert len(d["signals"]) == 128
    for part in ("S3c-L90", "S3c-L50", "S3c-E90", "S3c-E50"):
        sl = [s for s in d["signals"] if s["cell"] == part]
        assert len(sl) == 32 and len({s["slot"] for s in sl}) >= 12
    for i, c in enumerate(d["cycles"]):
        if c["block"] == "EARLY" and c["planted"]:
            assert not d["cycles"][i - 1]["planted"]
    assert all(s["snr_db"] == -8 for s in d["signals"])
    assert all(all(w.startswith("Q") for w in s["text"].split()[:2]) for s in d["signals"])   # NFR-021
    assert len({s["text"] for s in d["signals"]}) == 128


def test_design_is_deterministic(scen):
    again = S.build_design(scen["points"])
    assert S.canonical_json(again) == S.canonical_json(scen["design"])


def test_scenario_json_is_lf_canonical():
    raw = SCENARIO.read_bytes().replace(bytes((13, 10)), bytes((10,)))      # a CRLF checkout (autocrlf) is fine
    assert raw == S.canonical_json(json.loads(raw))


def _write_alltxt(path, design, boundaries, decoded_sig_ids, dt=0.1):
    lines = []
    for sid in decoded_sig_ids:
        s = design["signals"][sid]
        b = boundaries[s["cycle"]]
        lines.append(f"{b:%y%m%d_%H%M%S}    14.074 Rx FT8     -8  {dt:4.1f} {int(s['freq_hz']):4d} {s['text']}")
    lines.append("260101_000000    14.074 Rx FT8     -5  0.1 1000 CQ Q9ZZZ AA00")      # a non-planted line
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _log(path, design, start):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(["cycle_index", "boundary_utc", "planted", "play_started_utc"])
        out = {}
        for i, c in enumerate(design["cycles"]):
            b = start + timedelta(seconds=15 * i)
            out[i] = b
            wr.writerow([i, b.strftime("%Y-%m-%dT%H:%M:%SZ"), int(c["planted"]), ""])
    return out


def _run(tmp_path, scen, owsfz_ids, wsjtx_ids):
    d = scen["design"]
    b = _log(tmp_path / "playback_log.csv", d, datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc))
    _write_alltxt(tmp_path / "o.txt", d, b, owsfz_ids)
    _write_alltxt(tmp_path / "w.txt", d, b, wsjtx_ids)
    return SC.score(scen, tmp_path / "w.txt", tmp_path / "o.txt", tmp_path / "playback_log.csv")


def _sig_ids(scen, part, n):
    return [s["sig_id"] for s in scen["design"]["signals"] if s["cell"] == part][:n]


def _all(scen):
    return [s["sig_id"] for s in scen["design"]["signals"]]


def test_all_decoded_passes_both_rows_and_counts_descriptive_x(tmp_path, scen):
    r = _run(tmp_path, scen, _all(scen), _all(scen))
    assert r["rows"]["S3c-WSJT-X (validity)"] == "PASS" and r["rows"]["S3c-OWSFZ (guard)"] == "PASS"
    assert r["decoders"]["OpenWSFZ"]["parts"]["S3c-L50"]["X"] == 32       # reported even though descriptive


def test_owsfz_below_kstar_flags_and_wsjtx_validity_unaffected(tmp_path, scen):
    ow = [i for i in _all(scen) if i not in set(_sig_ids(scen, "S3c-L90", 10))]      # L90: 22 < 24
    r = _run(tmp_path, scen, ow, _all(scen))
    assert r["rows"]["S3c-WSJT-X (validity)"] == "PASS"
    assert r["rows"]["S3c-OWSFZ (guard)"].startswith("FLAG")


def test_wsjtx_validity_fail_means_owsfz_rows_not_read(tmp_path, scen):
    ws = [i for i in _all(scen) if i not in set(_sig_ids(scen, "S3c-E90", 20))]
    r = _run(tmp_path, scen, _all(scen), ws)
    assert r["rows"]["S3c-WSJT-X (validity)"] == "FAIL"
    assert r["rows"]["S3c-OWSFZ (guard)"].startswith("NOT READ")
    assert r["state"].startswith("INVALID")


def test_descriptive_part_cannot_fail(tmp_path, scen):
    ow = [i for i in _all(scen) if i not in set(_sig_ids(scen, "S3c-L50", 32))]      # 0 of 32 at L +3.00
    r = _run(tmp_path, scen, ow, _all(scen))
    assert r["rows"]["S3c-OWSFZ (guard)"] == "PASS"


def test_wrong_cycle_decode_does_not_count_and_is_counted(tmp_path, scen):
    d = scen["design"]
    b = _log(tmp_path / "playback_log.csv", d, datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc))
    s = d["signals"][0]
    wrong = b[(s["cycle"] + 1) % 12]
    line = f"{wrong:%y%m%d_%H%M%S}    14.074 Rx FT8     -8   0.1 {int(s['freq_hz']):4d} {s['text']}\n"
    (tmp_path / "o.txt").write_text(line, encoding="utf-8")
    (tmp_path / "w.txt").write_text("", encoding="utf-8")
    r = SC.score(scen, tmp_path / "w.txt", tmp_path / "o.txt", tmp_path / "playback_log.csv")
    assert r["decoders"]["OpenWSFZ"]["parts"][s["cell"]]["X"] == 0
    assert r["decoders"]["OpenWSFZ"]["wrong_cycle_decodes"] == 1


def test_frequency_tolerance_is_10_hz(tmp_path, scen):
    d = scen["design"]
    b = _log(tmp_path / "playback_log.csv", d, datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc))
    s = d["signals"][0]
    far = f"{b[s['cycle']]:%y%m%d_%H%M%S}    14.074 Rx FT8     -8   0.1 {int(s['freq_hz']) + 11:4d} {s['text']}\n"
    (tmp_path / "o.txt").write_text(far, encoding="utf-8")
    (tmp_path / "w.txt").write_text("", encoding="utf-8")
    r = SC.score(scen, tmp_path / "w.txt", tmp_path / "o.txt", tmp_path / "playback_log.csv")
    assert r["decoders"]["OpenWSFZ"]["parts"][s["cell"]]["X"] == 0


def test_output_carries_no_message_text(tmp_path, scen):
    r = _run(tmp_path, scen, _all(scen), _all(scen))
    blob = json.dumps(r) + SC.render_md(r, {"subtraction_enabled": "true", "build_sha": "x",
                                              "dll_sha256_prefix": "y", "scenario_sha256": "z"})
    for s in scen["design"]["signals"]:
        assert s["text"] not in blob


@pytest.mark.skipif(not (RR / ".venv").exists(), reason="renders need the study venv (numpy/scipy)")
def test_renders_match_the_frozen_index(scen):
    import s3c_render as R
    _, index = R.render_all(scen["design"])
    assert index == scen["renders_index"]


def test_trend_columns_are_distinct():
    assert len(SC.TREND_FIELDS) == len(set(SC.TREND_FIELDS))
    assert {"x_owsfz_l90", "x_owsfz_e50", "x_wsjtx_l50", "x_wsjtx_e90"} <= set(SC.TREND_FIELDS)


def test_an_earlier_batterys_decodes_in_the_cumulative_log_are_not_wrong_cycle(tmp_path, scen):
    d = scen["design"]
    b = _log(tmp_path / "playback_log.csv", d, datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc))
    earlier = {i: t - timedelta(hours=2) for i, t in b.items()}          # same texts, an earlier battery's stamps
    _write_alltxt(tmp_path / "o.txt", d, earlier, _all(scen))
    _write_alltxt(tmp_path / "w.txt", d, earlier, _all(scen))
    r = SC.score(scen, tmp_path / "w.txt", tmp_path / "o.txt", tmp_path / "playback_log.csv")
    assert r["decoders"]["OpenWSFZ"]["wrong_cycle_decodes"] == 0
    assert all(v["X"] == 0 for v in r["decoders"]["OpenWSFZ"]["parts"].values())


def test_owsfz_e50_is_descriptive_so_it_cannot_flag_but_wsjtx_e50_still_guards_validity(tmp_path, scen):
    """Ruling 2026-10-05 4c: the OpenWSFZ E -2.00 cell is cycle-clustered (effective n ~ 4), so it is descriptive; WSJT-X's rows are unchanged."""
    ow = [i for i in _all(scen) if i not in set(_sig_ids(scen, "S3c-E50", 32))]            # 0 of 32 at E -2.00
    r = _run(tmp_path, scen, ow, _all(scen))
    p = r["decoders"]["OpenWSFZ"]["parts"]["S3c-E50"]
    assert p["X"] == 0 and p["descriptive"] and p["pass"] and p["k_star"] == 4          # k* recorded, not hidden
    assert r["rows"]["S3c-OWSFZ (guard)"] == "PASS"
    ws = [i for i in _all(scen) if i not in set(_sig_ids(scen, "S3c-E50", 32))]          # the same collapse on WSJT-X is a validity FAIL
    r2 = _run(tmp_path, scen, _all(scen), ws)
    assert not r2["decoders"]["WSJT-X"]["parts"]["S3c-E50"]["descriptive"]
    assert r2["rows"]["S3c-WSJT-X (validity)"] == "FAIL"


def test_e90_is_still_the_owsfz_early_guard(tmp_path, scen):
    ow = [i for i in _all(scen) if i not in set(_sig_ids(scen, "S3c-E90", 10))]          # 22 < k* 24
    r = _run(tmp_path, scen, ow, _all(scen))
    assert not r["decoders"]["OpenWSFZ"]["parts"]["S3c-E90"]["descriptive"]
    assert r["rows"]["S3c-OWSFZ (guard)"].startswith("FLAG")


def test_cycles_with_decode_counts_cycles_not_signals(tmp_path, scen):
    sigs = [s for s in scen["design"]["signals"] if s["cell"] == "S3c-E50"]
    one_cycle = sorted({s["cycle"] for s in sigs})[0]
    ids = [s["sig_id"] for s in sigs if s["cycle"] == one_cycle]                          # all 8 signals of ONE cycle
    ow = [i for i in _all(scen) if i not in {s["sig_id"] for s in sigs}] + ids
    p = _run(tmp_path, scen, ow, _all(scen))["decoders"]["OpenWSFZ"]["parts"]["S3c-E50"]
    assert (p["X"], p["cycles_with_decode"], p["cycles_total"]) == (8, 1, 4)
    # one signal in each of the four cycles: 4 signals, 4 cycles
    per_cycle = {c: [s["sig_id"] for s in sigs if s["cycle"] == c][0] for c in {s["cycle"] for s in sigs}}
    ow2 = [i for i in _all(scen) if i not in {s["sig_id"] for s in sigs}] + list(per_cycle.values())
    p2 = _run(tmp_path, scen, ow2, _all(scen))["decoders"]["OpenWSFZ"]["parts"]["S3c-E50"]
    assert (p2["X"], p2["cycles_with_decode"], p2["cycles_total"]) == (4, 4, 4)
