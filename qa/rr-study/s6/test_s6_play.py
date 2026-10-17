"""Unit tests for s6_play: the schedule is a pure function; a --dry-run writes a play log without sound or waiting."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, RR)
import s6_design as D  # noqa: E402
import s6_play as P  # noqa: E402

WL = json.load(open(os.path.join(HERE, "s6-wavlist.json"), encoding="utf8"))


def test_prewarm_equals_the_batterys():
    from harness import run_scenario
    assert P.PREWARM_S == run_scenario._CYCLE_PREWARM_S == 0.5 and P.SLOT_S == 15
    assert P.BATCH_PLAYS == run_scenario._MAX_BATCH_TRIALS == 20
    assert P.START_LEAD_S == 0.0 and P.OFFSET_NOMINAL_S == 0.0          # real recordings start AT the boundary (not the synthetic scenes' -0.5 s)


def test_trial_seed_is_the_corpus_replay_rule():
    import hashlib
    assert P.trial_seed(0) == int(hashlib.sha256(b"S6,0").hexdigest(), 16) % (2 ** 31)
    assert len({P.trial_seed(t) for t in range(3)}) == 3


def test_schedule_every_wav_exactly_once_per_trial_and_orders_differ():
    items = D.tier_items(WL, "quick")
    s = P.make_schedule(items)
    assert len(s) == 24 * 3 and [x[0] for x in s] == list(range(72))
    for t in range(3):
        ids = [x[3]["id"] for x in s if x[1] == t]
        assert sorted(ids) == sorted(i["id"] for i in items) and len(ids) == 24
    orders = [tuple(x[3]["id"] for x in s if x[1] == t) for t in range(3)]
    assert len(set(orders)) == 3
    assert s == P.make_schedule(items)


def test_slot_stamp_and_boundary():
    assert P.slot_stamp(0) == "700101_000000"
    assert P.next_boundary(14.2) == 15.0 and P.next_boundary(15.0) == 30.0


def test_lines_for_slot_counts_only_the_stamped_lines_after_pos(tmp_path):
    f = tmp_path / "ALL.TXT"
    f.write_text("261013_120000  14.074 Rx FT8 -10 0.1 1500 A\n", encoding="utf8")
    pos = f.stat().st_size
    with open(f, "a", encoding="utf8") as fh:
        fh.write("261013_120015  14.074 Rx FT8 -10 0.1 1500 B\n261013_120015  14.074 Rx FT8 -12 0.2 1600 C\n261013_120030  14.074 Rx FT8 -9 0.1 1500 D\n")
    assert P.lines_for_slot(str(f), pos, "261013_120015") == 2
    assert P.lines_for_slot(str(f), 0, "261013_120000") == 1
    assert P.lines_for_slot(str(tmp_path / "none"), 0, "x") == 0


def test_dry_run_writes_a_consistent_play_log(tmp_path):
    run = tmp_path / "run"
    cmd = [sys.executable, os.path.join(HERE, "s6_play.py"), "--run-dir", str(run), "--tier", "quick", "--corpus", str(tmp_path),
           "--wsjt-all-txt", str(tmp_path / "w.txt"), "--owsfz-all-txt", str(tmp_path / "o.txt"), "--dry-run", "--skip-verify"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)   # no inherited stdin: a closed one raises WinError 6
    assert r.returncode == P.EXIT_V5, r.stdout + r.stderr          # no --ows-lib => "NOT PINNED" => the V5 exit, everything else done
    rows = [json.loads(x) for x in open(run / "s6" / "s6_playlog.jsonl", encoding="utf8")]
    plays = [x for x in rows if x["kind"] == "play"]
    assert len(plays) == 72 and sum(1 for x in rows if x["kind"] == "warmup") == 1
    plans = [x for x in rows if x["kind"] == "batch_plan"]
    assert [p["slots"] for p in plans] == [20, 20, 20, 12] and plans[0]["first_slot"] == plays[0]["slot_stamp"]
    stamps = [x["slot_stamp"] for x in plays]
    assert len(set(stamps)) == 72                                   # one play per slot
    from datetime import datetime
    def t_of(st): return datetime.strptime(st, "%y%m%d_%H%M%S").timestamp()
    by_batch = {}
    for x in plays:
        by_batch.setdefault(x["batch"], []).append(x)
    assert sorted(by_batch) == [0, 1, 2, 3] and [len(by_batch[i]) for i in range(4)] == [20, 20, 20, 12]
    for i, xs in by_batch.items():                                  # consecutive slots inside a batch
        assert [t_of(x["slot_stamp"]) - t_of(xs[0]["slot_stamp"]) for x in xs] == [15.0 * j for j in range(len(xs))]
    for i in range(3):                                              # exactly ONE idle slot between batches, none unexplained
        gap = t_of(by_batch[i + 1][0]["slot_stamp"]) - t_of(by_batch[i][-1]["slot_stamp"])
        assert gap == 30.0, gap
    w = json.load(open(run / "s6" / "s6_window.json"))
    assert w["batches"] == 4 and w["idle_slots_between_batches"] == 3 and w["slips"] == 0
    assert all(abs(x["offset_s"] - P.OFFSET_NOMINAL_S) <= P.OFFSET_TOLERANCE_S for x in plays)
    v = json.load(open(run / "s6" / "s6_validity.json"))
    assert v["S6-V1"]["result"] == "SKIPPED" and v["S6-V3"]["result"] == "PASS" and v["S6-V5"]["result"] == "NOT PINNED"
    assert v["S6-V4-plays_completed"] == 72
    assert "S6 batch 4/4 done: plays 61-72" in r.stdout and "S6 playback done: 72 plays, 0 slip(s)" in r.stdout


def test_pins_hash_the_daemon_config_and_a_change_breaks_the_pin_identity(tmp_path):
    """Architect 2026-10-17 (F1' ruling): the decoder settings are PINNED by the hash of config.json, not inferred. A changed config must break start/end equality."""
    import argparse
    cfg = tmp_path / "config.json"
    cfg.write_text('{"a": 1}', encoding="utf8")
    a = argparse.Namespace(ows_lib=None, wsjtx_exe=None, config=str(cfg))
    start = P.pins(a)
    assert start["config_json_sha256"] == D.sha256_file(str(cfg))
    cfg.write_text('{"a": 2}', encoding="utf8")
    assert P.pin_identity(start) != P.pin_identity(P.pins(a))
    assert P.pins(argparse.Namespace(ows_lib=None, wsjtx_exe=None, config=None))["config_json_sha256"] is None
