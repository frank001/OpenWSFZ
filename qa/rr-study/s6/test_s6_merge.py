"""Tests for the sequential-S6 merge (s6_merge.py) and the player's --appraiser / --out-sub options."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, RR)
import s6_merge as M  # noqa: E402
import s6_play as P  # noqa: E402


def _play_row(i, stamp, wav="w%d" % 0, trial=0, order=0, offset=0.0):
    return {"kind": "play", "play_index": i, "batch": 0, "trial": trial, "order": order, "wav_id": "%s:%d" % (wav, i), "band": "20m", "sun": "day", "gain": 5.5,
            "boundary_utc": "2026-10-16T10:00:%02d.000000Z" % (i % 60), "slot_stamp": stamp, "offset_s": offset, "slips_so_far": 0}


def _pass_rows(stamps, tag_warm="261016_095900"):
    rows = [{"kind": "warmup", "attempt": 1, "boundary_utc": "x", "slot_stamp": tag_warm, "offset_s": 0.0, "wsjtx_lines": 1, "owsfz_lines": 1},
            {"kind": "batch_plan", "batch": 0, "first_slot": stamps[0], "slots": len(stamps), "first_play_index": 0}]
    rows += [_play_row(i, s) for i, s in enumerate(stamps)]
    return rows


def test_merge_playlogs_adds_the_o_stamps_and_tags_the_passes():
    w = _pass_rows(["261016_100000", "261016_100015"], "261016_095900")
    o = _pass_rows(["261016_110000", "261016_110015"], "261016_105900")
    m = M.merge_playlogs(w, o)
    plays = [r for r in m if r["kind"] == "play"]
    assert [(p["slot_stamp"], p["slot_stamp_o"]) for p in plays] == [("261016_100000", "261016_110000"), ("261016_100015", "261016_110015")]
    assert [r["pass"] for r in m if r["kind"] == "warmup"] == ["w", "o"]
    assert {r["pass"] for r in m if r["kind"] == "batch_plan"} == {"w", "o"}
    assert all("pass" not in p for p in plays)


def test_merge_refuses_different_schedules_and_missing_plays():
    w = _pass_rows(["261016_100000", "261016_100015"])
    o = _pass_rows(["261016_110000", "261016_110015"])
    o[2]["wav_id"] = "other:0"
    with pytest.raises(M.MergeError, match="play 0 differs between the passes in wav_id"):
        M.merge_playlogs(w, o)
    with pytest.raises(M.MergeError, match="did not play the same plays"):
        M.merge_playlogs(w, o[:3])
    with pytest.raises(M.MergeError, match="no play rows"):
        M.merge_playlogs(w, [])


LIB = {"pid": 4242, "libft8_path": "/x/publish/libft8.so", "libft8_sha256": "a"}          # what s6-phase.sh o records from the live pass-O daemon


def _validity(v1="PASS", v3="PASS", v5="PASS", n=72, appraiser="wsjtx", tier="quick"):
    return {"tier": tier, "plays_planned": 72, "appraiser": appraiser, "S6-V1": {"result": v1}, "S6-V3": {"result": v3},
            "S6-V5": {"result": v5, "wsjtx_exe_pinned": True}, "S6-V4-plays_completed": n, "exit_code": 0}


def test_merge_validity_a_row_passes_only_if_it_passed_in_both_passes():
    pins = {"start": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}, "end": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [2, 2, 2]}}
    ok = M.merge_validity(_validity(), _validity(appraiser="owsfz"), pins, pins, LIB)
    assert [ok[k]["result"] for k in ("S6-V1", "S6-V3", "S6-V5")] == ["PASS"] * 3 and ok["S6-V4-plays_completed"] == 72 and ok["design"] == "sequential"
    bad = M.merge_validity(_validity(), _validity(v3="FAIL", n=60, appraiser="owsfz"), pins, pins, LIB)
    assert bad["S6-V3"]["result"] == "FAIL" and bad["S6-V4-plays_completed"] == 60
    skipped = M.merge_validity(_validity(v1="SKIPPED"), _validity(appraiser="owsfz"), pins, pins, LIB)
    assert skipped["S6-V1"]["result"] == "SKIPPED"
    gone = M.merge_validity(_validity(), None, pins, pins, LIB)
    assert gone["player_did_not_finish"] is True
    other_tier = M.merge_validity(_validity(), _validity(tier="standard", appraiser="owsfz"), pins, pins, LIB)
    assert other_tier["player_did_not_finish"] is True


def test_merge_validity_v5_needs_the_pins_equal_across_the_whole_s6():
    pw = {"start": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}, "end": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}}
    po = {"start": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}, "end": {"ows_lib_sha256": "CHANGED", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}}
    v = M.merge_validity(_validity(), _validity(appraiser="owsfz"), pw, po, LIB)
    assert v["S6-V5"]["result"] == "FAIL" and "across_passes" in v["S6-V5"]


def _dry_pass(run, appraiser, sub, extra=()):
    cmd = [sys.executable, os.path.join(HERE, "s6_play.py"), "--run-dir", str(run), "--tier", "quick", "--corpus", str(run), "--appraiser", appraiser, "--out-sub", sub,
           "--wsjt-all-txt", str(run / "w.txt"), "--owsfz-all-txt", str(run / "o.txt"), "--dry-run", "--skip-verify", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    assert r.returncode == P.EXIT_V5, r.stdout + r.stderr          # no --ows-lib: NOT PINNED, everything else done
    return r


def test_player_passes_write_into_their_own_folders_and_merge_joins_them(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    _dry_pass(run, "wsjtx", "pass-w")
    _dry_pass(run, "owsfz", "pass-o")
    for sub, who in (("pass-w", "wsjtx"), ("pass-o", "owsfz")):
        assert json.load(open(run / "s6" / sub / "s6_validity.json"))["appraiser"] == who
        assert json.load(open(run / "s6" / sub / "s6_window.json"))["appraiser"] == who
    assert not (run / "s6" / "s6_playlog.jsonl").exists()                # a pass never writes the top-level files
    r = M.merge(str(run))
    assert r["plays"] == 72
    rows = [json.loads(x) for x in open(run / "s6" / "s6_playlog.jsonl", encoding="utf8")]
    plays = [x for x in rows if x["kind"] == "play"]
    assert len(plays) == 72 and all("slot_stamp_o" in p and "slot_stamp" in p for p in plays)
    assert sorted(x["pass"] for x in rows if x["kind"] == "warmup") == ["o", "w"]
    v = json.load(open(run / "s6" / "s6_validity.json"))
    assert v["design"] == "sequential" and v["S6-V1"]["result"] == "SKIPPED" and v["S6-V3"]["result"] == "PASS" and v["S6-V5"]["result"] == "NOT PINNED"
    assert v["S6-V4-plays_completed"] == 72 and v["plays_planned"] == 72
    assert json.load(open(run / "s6" / "s6_sequential.json"))["order"] == ["w", "o"]
    assert json.load(open(run / "s6" / "s6_window.json"))["design"] == "sequential"


def test_a_pass_that_never_decoded_the_warmup_is_judged_only_on_its_own_appraiser(tmp_path):
    """Concurrent S6 needs BOTH logs to decode the warm-up; a sequential pass needs only the appraiser that was listening (the other is off)."""
    ok = P.warmup_ok
    assert ok(1, 1, "both") and not ok(1, 0, "both") and not ok(0, 1, "both") and not ok(0, 0, "both")
    assert ok(1, 0, "wsjtx") and ok(1, 1, "wsjtx") and not ok(0, 1, "wsjtx") and not ok(0, 0, "wsjtx")
    assert ok(0, 1, "owsfz") and ok(1, 1, "owsfz") and not ok(1, 0, "owsfz") and not ok(0, 0, "owsfz")


def test_merge_with_a_missing_pass_writes_nothing(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    _dry_pass(run, "wsjtx", "pass-w")
    with pytest.raises(M.MergeError, match="pass O left no s6_playlog.jsonl"):
        M.merge(str(run))
    assert not (run / "s6" / "s6_playlog.jsonl").exists()


def test_v5_needs_the_record_of_the_library_the_pass_o_daemon_loaded_and_it_must_equal_the_pinned_file():
    pins = {"start": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}, "end": {"ows_lib_sha256": "a", "wsjtx_exe_sha256": "b", "loadavg_1_5_15": [1, 1, 1]}}
    ok = M.merge_validity(_validity(), _validity(appraiser="owsfz"), pins, pins, LIB)
    assert ok["S6-V5"]["result"] == "PASS" and ok["S6-V5"]["pass_o_daemon_library"] == {"path": "/x/publish/libft8.so", "sha256": "a", "pid": 4242}
    none = M.merge_validity(_validity(), _validity(appraiser="owsfz"), pins, pins, None)          # Architect condition 1a: no record = NOT CHECKED, never PASS
    assert none["S6-V5"]["result"] == "NOT CHECKED" and "daemon_lib.json" in none["S6-V5"]["reason"]
    nosha = M.merge_validity(_validity(), _validity(appraiser="owsfz"), pins, pins, {"pid": 1, "libft8_path": None, "libft8_sha256": None})
    assert nosha["S6-V5"]["result"] == "NOT CHECKED"
    other = M.merge_validity(_validity(), _validity(appraiser="owsfz"), pins, pins, {**LIB, "libft8_sha256": "different"})
    assert other["S6-V5"]["result"] == "FAIL" and "differs from the pinned file" in other["S6-V5"]["across_passes"]
    notpinned = M.merge_validity(_validity(v5="NOT PINNED"), _validity(appraiser="owsfz"), pins, pins, None)
    assert notpinned["S6-V5"]["result"] == "NOT PINNED"                                              # a pass that was not pinned stays NOT PINNED, not turned into NOT CHECKED


def test_merge_copies_the_pass_o_library_record_into_the_s6_folder(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    _dry_pass(run, "wsjtx", "pass-w")
    _dry_pass(run, "owsfz", "pass-o")
    (run / "s6" / "pass-o" / "daemon_lib.json").write_text(json.dumps(LIB), encoding="utf-8")
    M.merge(str(run))
    assert json.load(open(run / "s6" / "s6_daemon_lib.json"))["libft8_sha256"] == "a"
    assert json.load(open(run / "s6" / "s6_validity.json"))["S6-V5"]["pass_o_daemon_library"]["sha256"] == "a"
