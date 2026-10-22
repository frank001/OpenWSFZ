"""Scenario-level retry helpers (Captain 2026-10-14). Synthetic run folders; no message text."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness import liveness as LV  # noqa: E402
from harness import scenario_retry as SR  # noqa: E402

COLS = ["scenario_id", "part_index", "trial_index", "cycle_utc"]


def mk(tmp, rows):
    with open(tmp / "truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        for r in rows:
            w.writerow(r)
    return tmp


def cyc(i, hour=10):
    return "2026-10-14T%02d:%02d:%02dZ" % (hour, i // 4, (i % 4) * 15)


def test_set_aside_moves_only_that_scenarios_truth_rows_and_keeps_them(tmp_path):
    rows = [["S1", 0, i, cyc(i)] for i in range(6)] + [["S1b", 0, i, cyc(i, 11)] for i in range(4)]
    run = mk(tmp_path, rows)
    aside = SR.set_aside(str(run), "S1b", 1)
    assert aside["truth_rows_set_aside"] == 4 and aside["cycles"] == sorted(cyc(i, 11) for i in range(4))
    left = list(csv.DictReader(open(run / "truth.csv", encoding="utf-8")))
    assert {r["scenario_id"] for r in left} == {"S1"} and len(left) == 6                      # the passed scenario is untouched
    kept = list(csv.DictReader(open(run / "truth_INVALID_S1b_attempt1.csv", encoding="utf-8")))
    assert len(kept) == 4 and kept[0]["scenario_id"] == "S1b"                                  # the failed attempt is KEPT as INVALID, not deleted


def test_set_aside_renames_the_s6_folder_and_returns_its_slots(tmp_path):
    run = mk(tmp_path, [["S1", 0, 0, cyc(0)]])
    (tmp_path / "s6").mkdir()
    (tmp_path / "s6" / "s6_playlog.jsonl").write_text("\n".join(json.dumps(x) for x in (
        {"kind": "warmup", "slot_stamp": "261014_100000"}, {"kind": "play", "slot_stamp": "261014_100100"}, {"kind": "play", "slot_stamp": "261014_100115"})) + "\n")
    aside = SR.set_aside(str(run), "S6", 2)
    assert (tmp_path / "s6-INVALID-attempt2" / "s6_playlog.jsonl").is_file() and not (tmp_path / "s6").exists()
    assert aside["cycles"] == ["2026-10-14T10:00:00Z", "2026-10-14T10:01:00Z", "2026-10-14T10:01:15Z"] and aside["moved"] == ["s6-INVALID-attempt2"]
    assert len(list(csv.DictReader(open(run / "truth.csv", encoding="utf-8")))) == 1         # S6 has no truth rows: truth.csv is not rewritten


def test_drop_cycles_removes_only_the_invalid_cycles_from_the_copy(tmp_path):
    f = tmp_path / "wsjt-all.txt"
    f.write_text("261014_100000   -5  0.1 1500 CQ Q1ABC FN42\n261014_100015   -9  0.2 1600 CQ Q1ABD FN42\n261014_100030   -7  0.3 1700 CQ Q1ABE FN42\n", encoding="utf-8")
    n = SR.drop_cycles_from_log(str(f), {"2026-10-14T10:00:15Z", "2026-10-14T10:00:30Z"})
    assert n == 2 and f.read_text(encoding="utf-8").splitlines() == ["261014_100000   -5  0.1 1500 CQ Q1ABC FN42"]
    assert SR.drop_cycles_from_log(str(f), set()) == 0 and SR.drop_cycles_from_log(str(tmp_path / "none.txt"), {"x"}) == 0


def test_coverage_failure_s1_uses_expected_minus_one_and_s6_needs_every_play_slot(tmp_path):
    cy = [cyc(i) for i in range(15)]
    run = mk(tmp_path, [["S4", 0, i, c] for i, c in enumerate(cy)])
    assert SR.coverage_failure(str(run), "S4", set(cy[:14]), set(cy)) is None                  # one missing is tolerated for S1-S8 (M3)
    f = SR.coverage_failure(str(run), "S4", set(cy[:13]), set(cy))
    assert f and "WSJT-X has data for only 13 of 15" in f["reason"]
    assert SR.coverage_failure(str(run), "S3c", set(), set()) is None                          # S3c: the stall gate only
    (tmp_path / "s6").mkdir()
    plays = ["261014_1001%02d" % (i * 15) for i in range(3)]
    (tmp_path / "s6" / "s6_playlog.jsonl").write_text("\n".join(json.dumps({"kind": "play", "slot_stamp": p}) for p in plays) + "\n")
    iso = [LV.stamp_to_iso(p) for p in plays]
    assert SR.coverage_failure(str(run), "S6", set(iso), set(iso)) is None
    f6 = SR.coverage_failure(str(run), "S6", set(iso[:2]), set(iso))                           # ONE missing play slot fails S6 (V7: bar 0)
    assert f6 and "S6-V7: 1 play slot(s) without a WSJT-X save WAV, 0" in f6["reason"]


def test_ledger_counts_retries_per_scenario_and_writes_the_record(tmp_path):
    led = SR.Ledger(str(tmp_path), 3)
    for sid in ("S1", "S1b"):
        led.start(sid)
    assert led.retries_used("S1b") == 0
    led.fail("S1b", "stall", "no new save WAV for 53 s", {"cycles": ["2026-10-14T10:00:00Z"], "moved": ["x"]}, True)
    assert led.start("S1b") == 2 and led.retries_used("S1b") == 1 and led.retries_used("S1") == 0      # the cap is PER SCENARIO
    led.fail("S1b", "coverage", "x", {"cycles": []}, True)
    led.start("S1b")
    led.fail("S1b", "stall", "y", {"cycles": []}, True)
    led.start("S1b")
    assert led.retries_used("S1b") == 3 and led.retries_used("S1b") >= led.cap                         # the 4th failure has no retry left
    led.fail("S1b", "stall", "z", {"cycles": []}, False)
    doc = json.loads((tmp_path / "scenario_retries.json").read_text())
    assert doc["totals"] == {"scenario_attempts": 5, "failed_attempts": 4, "replacements": 3}
    assert doc["scenarios"]["S1b"]["failed"][0]["replaced_by_attempt"] == 2 and doc["scenarios"]["S1b"]["failed"][3]["replaced_by_attempt"] is None
    assert "2026-10-14T10:00:00Z" in led.invalid_cycles


# ---- sequential S6 (Captain 2026-10-15): two passes, each appraiser in its own slots ----------------------------------------------------------

def _seq_s6(tmp):
    (tmp / "s6").mkdir()
    rows = [{"kind": "warmup", "slot_stamp": "261014_100000", "pass": "w"}, {"kind": "warmup", "slot_stamp": "261014_110000", "pass": "o"}]
    rows += [{"kind": "play", "play_index": i, "slot_stamp": "261014_1001%02d" % (i * 15), "slot_stamp_o": "261014_1101%02d" % (i * 15)} for i in range(3)]
    (tmp / "s6" / "s6_playlog.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return rows


def test_sequential_play_slots_are_per_appraiser(tmp_path):
    run = mk(tmp_path, [["S1", 0, 0, cyc(0)]])
    _seq_s6(tmp_path)
    assert SR.play_slots(str(run), "wsjtx") == ["2026-10-14T10:01:00Z", "2026-10-14T10:01:15Z", "2026-10-14T10:01:30Z"]
    assert SR.play_slots(str(run), "owsfz") == ["2026-10-14T11:01:00Z", "2026-10-14T11:01:15Z", "2026-10-14T11:01:30Z"]
    # a concurrent play log has one slot per play, the same for both appraisers
    (tmp_path / "s6" / "s6_playlog.jsonl").write_text(json.dumps({"kind": "play", "slot_stamp": "261014_100100"}) + "\n")
    assert SR.play_slots(str(run), "wsjtx") == SR.play_slots(str(run), "owsfz") == ["2026-10-14T10:01:00Z"]


def test_sequential_s6_coverage_is_judged_per_appraiser_against_its_own_pass(tmp_path):
    run = mk(tmp_path, [["S1", 0, 0, cyc(0)]])
    _seq_s6(tmp_path)
    w, o = set(SR.play_slots(str(run), "wsjtx")), set(SR.play_slots(str(run), "owsfz"))
    assert SR.coverage_failure(str(run), "S6", w, o) is None
    f = SR.coverage_failure(str(run), "S6", w, w)                                               # the OpenWSFZ archive holds only the WSJT-X pass's slots: not coverage
    assert f and "0 play slot(s) without a WSJT-X save WAV, 3 without an OpenWSFZ archive cycle" in f["reason"]
    f2 = SR.coverage_failure(str(run), "S6", o, o)
    assert f2 and "3 play slot(s) without a WSJT-X save WAV, 0 without" in f2["reason"]


def test_set_aside_of_a_sequential_s6_returns_the_slots_of_both_passes_even_before_the_merge(tmp_path):
    run = mk(tmp_path, [["S1", 0, 0, cyc(0)]])
    for sub, stamp in (("pass-w", "261014_100000"), ("pass-o", "261014_110000")):
        (tmp_path / "s6" / sub).mkdir(parents=True)
        (tmp_path / "s6" / sub / "s6_playlog.jsonl").write_text(json.dumps({"kind": "warmup", "slot_stamp": stamp}) + "\n" + json.dumps({"kind": "play", "slot_stamp": stamp[:9] + "0115"}) + "\n")
    assert not (tmp_path / "s6" / "s6_playlog.jsonl").exists()                                   # no merged log: pass O died, say
    aside = SR.set_aside(str(run), "S6", 1)
    assert aside["cycles"] == ["2026-10-14T10:00:00Z", "2026-10-14T10:01:15Z", "2026-10-14T11:00:00Z", "2026-10-14T11:01:15Z"]
    assert (tmp_path / "s6-INVALID-attempt1" / "pass-o" / "s6_playlog.jsonl").is_file()
