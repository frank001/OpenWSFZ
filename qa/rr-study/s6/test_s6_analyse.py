"""End-to-end test of the S6 analysis on a synthetic run: play log + two ALL.TXT slices + a daemon log, with known properties."""
import json
import os
import random
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, RR)
import s6_analyse as A  # noqa: E402
import s6_play as P  # noqa: E402
import s6_split as SP  # noqa: E402

TZ_H = 2          # the synthetic daemon logs local time = UTC + 2


def line(stamp, snr, freq, text):
    return "%s     14.074 Rx FT8 %5d  0.1 %4d %s\n" % (stamp, snr, freq, text)


def make_run(tmp, n_wavs=12, stray=False, drop_play=False, abandon_wav=None, seed=5, sequential=False):
    rng = random.Random(seed)
    run, scratch = tmp / "run", tmp / "scratch"
    (run / "s6").mkdir(parents=True)
    scratch.mkdir()
    t0 = datetime(2026, 10, 13, 16, 0, 0)
    rows, wsjt, ows, dlog = [], [], [], []
    shift = timedelta(hours=1) if sequential else timedelta(0)           # sequential S6: the OpenWSFZ pass played the same plays one hour later
    fmt = lambda d: d.strftime("%y%m%d_%H%M%S")
    if sequential:
        rows.append({"kind": "warmup", "attempt": 1, "boundary_utc": "x", "slot_stamp": fmt(t0), "offset_s": 0.0, "wsjtx_lines": 1, "owsfz_lines": 0, "pass": "w"})
        rows.append({"kind": "warmup", "attempt": 1, "boundary_utc": "x", "slot_stamp": fmt(t0 + shift), "offset_s": 0.0, "wsjtx_lines": 0, "owsfz_lines": 1, "pass": "o"})
    else:
        rows.append({"kind": "warmup", "attempt": 1, "boundary_utc": "x", "slot_stamp": fmt(t0), "offset_s": 0.0, "wsjtx_lines": 1, "owsfz_lines": 1})
    wsjt.append(line(fmt(t0), 6, 1500, "CQ QWARM FN42"))
    ows.append(line(fmt(t0 + shift), 6, 1500, "CQ QWARM FN42"))
    wavs = [{"id": "b%02d:s%02d" % (i, i), "band": ["17m", "20m", "40m", "80m"][i % 4], "sun": "day", "gain": 2.0} for i in range(n_wavs)]
    truth = {w["id"]: [("CQ Q%dAAA FN42" % (i * 10 + j), rng.uniform(-18, 0), 500 + 100 * j) for j in range(5)] for i, w in enumerate(wavs)}
    sched = P.make_schedule(wavs)
    slot = t0 + timedelta(seconds=45)
    for (n, trial, order, item) in sched:
        st = slot.strftime("%y%m%d_%H%M%S")
        if not (drop_play and n == 7):
            rows.append({"kind": "play", "play_index": n, "trial": trial, "order": order, "wav_id": item["id"], "band": item["band"], "sun": "day",
                         "gain": 2.0, "boundary_utc": "x", "slot_stamp": st, "offset_s": 0.0, "slips_so_far": 0,
                         **({"slot_stamp_o": fmt(slot + shift), "boundary_utc_o": "x", "offset_s_o": 0.0} if sequential else {})})
        for j, (text, snr, f) in enumerate(truth[item["id"]]):
            wsjt.append(line(st, round(snr), f, text))                                 # WSJT-X decodes all 5, steadily
            if rng.random() < 0.7:
                ows.append(line(fmt(slot + shift), round(snr + 1.0), f, text))         # OWS decodes 70 %, SNR +1 dB
        wsjt.append(line(st, -20, 1900, "CQ <...> FN42"))                              # a hashed row, excluded
        ab = (item["id"] == abandon_wav)
        local = slot + shift + timedelta(seconds=15 + 2 + 9) + timedelta(hours=TZ_H)    # pass ends 2 s of pass 0 + 9 s of residual after the slot's end
        dlog.append("[%s INF] Sub-feas residual pass: residualDecodes=1 elapsedMs=9000 deadlineAbandoned=%s containedException=False fittedSignals=7\n"
                    % (local.strftime("%H:%M:%S"), "True" if ab else "False"))
        slot += timedelta(seconds=15)
    if stray:
        wsjt.append(line((slot + timedelta(seconds=300)).strftime("%y%m%d_%H%M%S"), -5, 1000, "CQ QSTRAY FN42"))
    (run / "s6" / "s6_playlog.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf8")
    n_plays = len(wavs) * 3
    (run / "s6" / "s6_validity.json").write_text(json.dumps({
        "tier": "standard", "plays_planned": n_plays, "S6-V1": {"result": "PASS"}, "S6-V3": {"result": "PASS"},
        "S6-V5": {"result": "PASS", **({"pass_o_daemon_library": {"path": "/x/publish/libft8.so", "sha256": "abc123", "pid": 4242}} if sequential else {})}}), encoding="utf8")
    (scratch / "wsjt-s6.txt").write_text("".join(wsjt), encoding="utf8")
    (scratch / "owsfz-s6.txt").write_text("".join(ows), encoding="utf8")
    (tmp / "daemon.log").write_text("".join(dlog), encoding="utf8")
    (run / "s6" / "s6_tz.json").write_text(json.dumps({"gmtoff_s": TZ_H * 3600, "zone": "CEST", "isdst": 1}), encoding="utf8")
    return run, scratch, tmp / "daemon.log"


def test_valid_run_numbers_and_sensitivity(tmp_path):
    run, scratch, dl = make_run(tmp_path, abandon_wav="b03:s03")
    r = A.run(str(run), str(scratch), str(dl), "First S6 row of the LINUX series (tier standard)", "test chain", n_boot=200)
    assert r["status"] == "VALID", r["validity"]
    assert r["validity"]["S6-V2"]["stray_lines"] == {"wsjtx": 0, "owsfz": 0}
    h = r["full"]["headline"]
    assert h["wavs"] == 12 and abs(h["decodes_per_wav_wsjtx"] - 5.0) < 1e-9          # the hashed row is excluded
    assert 3.0 < h["decodes_per_wav_owsfz"] < 4.0 and abs(h["snr_delta_mean"] - 1.0) < 0.2
    assert h["consistency_own_wsjtx"] == 1.0 and h["consistency_own_owsfz"] < 0.7     # WSJT-X steady, OWS flickers
    assert 0.5 < h["positive_agreement"] < 0.8
    assert abs(r["hashed_per_play"]["wsjtx"] - 1.0) < 1e-9 and r["hashed_per_play"]["owsfz"] == 0
    # the daemon log was attributed (offset recovered) and exactly the abandoned WAV's 3 plays are flagged
    ab = r["abandonment"]
    assert ab["daemon_log_attributed"] and ab["tz_offset_h_system"] == TZ_H and ab["tz_offset_h_inferred"] == TZ_H and ab["plays_abandoned"] == 3
    assert r["no_abandon_wavs"] == {"kept": 11, "of": 12} and r["no_abandon"]["headline"]["wavs"] == 11
    assert r["order_effect"]["wsjtx"]["n"] == 36 and len(r["trial_effect"]["owsfz"]["mean_by_trial"]) == 3
    assert r["figure"] == "s6_figure.png" and (run / "s6" / "s6_figure.png").stat().st_size > 10_000
    md = open(run / "s6" / "s6_section5.md", encoding="utf8").read()
    assert "First S6 row of the LINUX series" in md and "Positive agreement" in md and "Sensitivity: WAVs with no abandoned play" in md
    assert "36 of 36 residual-pass lines in the window map to a play slot by both rules" in md and "Daemon-log attribution (Architect amendment 5)" in md and "a design number" in md and "player call time" in md
    assert "QWARM" not in md and "Q1" not in md                                          # no message text in the report block


def test_a_stray_line_voids_the_block_only(tmp_path):
    run, scratch, dl = make_run(tmp_path, stray=True)
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["status"].startswith("VOID") and r["validity"]["S6-V2"]["stray_lines"]["wsjtx"] == 1
    assert "full" not in r and "WITHHELD" in open(run / "s6" / "s6_section5.md", encoding="utf8").read()


def test_a_missing_play_fails_v4(tmp_path):
    run, scratch, dl = make_run(tmp_path, drop_play=True)
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["validity"]["S6-V4"]["result"] == "FAIL" and r["status"].startswith("VOID")


def test_a_late_play_is_recorded_but_no_longer_fails_v2_offset_retired_as_a_check(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    p = run / "s6" / "s6_playlog.jsonl"
    rows = [json.loads(x) for x in p.read_text(encoding="utf8").splitlines()]
    rows[5]["offset_s"] = 0.9
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    # Architect amendment 3 (2026-10-14): the call-time row (a) is RETIRED as a check and kept as a record: it cannot fail, so a late play is recorded and does not void the block
    assert r["validity"]["S6-V2"]["plays_outside_tolerance"] == 1 and r["validity"]["S6-V2"]["result"] == "PASS" and r["status"] == "VALID"


def test_unattributable_daemon_log_gives_unknown_not_zero(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    r = A.run(str(run), str(scratch), None, "x", "y", n_boot=50)
    assert not r["abandonment"]["daemon_log_attributed"] and r["abandonment"]["plays_abandoned"] is None
    assert "no_abandon" not in r and "UNKNOWN" in r["abandonment"]["summary"]


def test_split_moves_s6_lines_out_of_the_copies(tmp_path):
    run, scratch, _ = make_run(tmp_path)
    w, o = tmp_path / "wsjt-all.txt", tmp_path / "owsfz-all.txt"
    pre = line("261013_155000", -9, 1200, "CQ QOLD FN42")
    w.write_text(pre + (scratch / "wsjt-s6.txt").read_text(encoding="utf8"), encoding="utf8")
    o.write_text(pre + (scratch / "owsfz-s6.txt").read_text(encoding="utf8"), encoding="utf8")
    out = tmp_path / "scratch2"
    r = SP.split_logs(str(run), str(w), str(o), str(out))
    assert r["wsjtx"]["kept"] == 1 and r["owsfz"]["kept"] == 1 and r["wsjtx"]["moved"] > 100
    assert w.read_text(encoding="utf8") == pre and "QOLD" not in (out / "wsjt-s6.txt").read_text(encoding="utf8")


def test_a_system_zone_that_disagrees_with_the_inference_gives_unknown(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    (run / "s6" / "s6_tz.json").write_text(json.dumps({"gmtoff_s": 3 * 3600, "zone": "X"}), encoding="utf8")     # the log was written at +2 h
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    ab = r["abandonment"]
    assert not ab["daemon_log_attributed"] and ab["plays_abandoned"] is None and "no_abandon" not in r
    assert "UNKNOWN" in ab["summary"] and ab["tz_offset_h_system"] == 3 and ab["tz_offset_h_inferred"] == TZ_H


def test_no_recorded_zone_gives_unknown_even_if_the_log_is_clean(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    os.remove(run / "s6" / "s6_tz.json")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert not r["abandonment"]["daemon_log_attributed"] and "UNKNOWN" in r["abandonment"]["summary"]


def test_a_half_hour_zone_cannot_be_cross_checked_so_it_is_unknown(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    (run / "s6" / "s6_tz.json").write_text(json.dumps({"gmtoff_s": 5 * 3600 + 1800, "zone": "IST"}), encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert not r["abandonment"]["daemon_log_attributed"]


def test_a_player_that_did_not_finish_voids_the_block_instead_of_crashing(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    os.remove(run / "s6" / "s6_validity.json")                         # the player was killed: it never writes this file
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["status"].startswith("VOID") and r["validity"]["S6-V4"]["result"] == "FAIL" and "did not finish" in r["validity"]["S6-V4"]["note"]
    assert "WITHHELD" in open(run / "s6" / "s6_section5.md", encoding="utf8").read()


def test_the_s6_only_report_header_names_the_build_from_the_arm_config(tmp_path):
    from pathlib import Path
    import s6_report_header as H
    arm = {"build": {"commit": "a" * 40}, "daemon": {"dll_sha256": "b" * 64, "shim_version": 20260060, "daemon_version": "0.57", "decoder_readback": {"osdNhardMax": 24}}, "wsjtx": {"NDepth": 3, "mode": "FT8"}}

    class Args:
        s6_tier = "quick"
    h = H.header(Path("results/2026-10-13-abc1234"), arm, Args())
    assert ("a" * 40) in h and ("b" * 64) in h and "`osdNhardMax` = 24" in h and "S6 only, tier `quick`" in h and "no S1-S8 verdict" in h


def test_the_chain_label_comes_from_the_runs_own_readback_and_never_claims_the_default(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    (run / "arm_config.json").write_text(json.dumps({"daemon": {"decoder_readback": {"subtractionMaxThreads": 8}}}), encoding="utf8")
    label = A.describe_chain(str(run))
    cpus = os.cpu_count()
    assert "subtractionMaxThreads 8 on %d CPUs" % cpus in label and "SILENT" in label and "deadline ON" in label
    assert ("(station value, not auto)" in label) == (8 != max(1, cpus - 2))
    (run / "arm_config.json").write_text("{}", encoding="utf8")
    assert "NOT READ BACK" in A.describe_chain(str(run))
    r = A.run(str(run), str(scratch), str(dl), "x", None, n_boot=50)          # no explicit label: built from the run
    assert "SILENT" in r["cpu_chain_label"]


def test_the_split_survives_batch_plan_rows_in_the_play_log(tmp_path):
    run, scratch, _ = make_run(tmp_path)
    p = run / "s6" / "s6_playlog.jsonl"
    rows = p.read_text(encoding="utf8").splitlines()
    plan = json.dumps({"kind": "batch_plan", "batch": 0, "first_slot": "261013_160045", "slots": 20, "first_play_index": 0})
    p.write_text("\n".join([rows[0], plan] + rows[1:]) + "\n", encoding="utf8")           # the real log has these between the warm-up and the plays
    w, o = tmp_path / "wsjt-all.txt", tmp_path / "owsfz-all.txt"
    w.write_text(line("261013_155000", -9, 1200, "CQ QOLD FN42") + (scratch / "wsjt-s6.txt").read_text(encoding="utf8"), encoding="utf8")
    o.write_text(line("261013_155000", -9, 1200, "CQ QOLD FN42") + (scratch / "owsfz-s6.txt").read_text(encoding="utf8"), encoding="utf8")
    r = SP.split_logs(str(run), str(w), str(o), str(tmp_path / "scratch3"))
    assert r["first_s6_slot"] == "261013_160000" and r["wsjtx"]["kept"] == 1 and r["wsjtx"]["moved"] > 100


def test_missing_or_empty_log_slices_void_the_block_instead_of_reading_valid(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    os.remove(scratch / "wsjt-s6.txt")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["status"].startswith("VOID") and r["validity"]["S6-V2"]["logs"] == "S6 log slices missing"
    (scratch / "wsjt-s6.txt").write_text("", encoding="utf8")
    (scratch / "owsfz-s6.txt").write_text("", encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["status"].startswith("VOID") and r["validity"]["S6-V2"]["logs"] == "both S6 log slices are empty"


def test_the_block_says_when_the_onset_row_is_not_computed(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)            # no corpus given
    assert r["onset"] is None
    assert "Sound onset, from WSJT-X's own DT:** not computed" in open(run / "s6" / "s6_section5.md", encoding="utf8").read()


def test_the_attribution_floor_is_read_on_pass_lines_and_a_missing_line_means_no_pass_ran(tmp_path):
    run, scratch, dl = make_run(tmp_path, abandon_wav="b03:s03")
    kept = []
    for i, ln in enumerate(dl.read_text(encoding="utf8").splitlines()):
        if i % 3 == 0 or "deadlineAbandoned=True" in ln:                  # only some plays have a pass line, and every abandoned pass keeps its line
            kept.append(ln)
    dl.write_text("\n".join(kept) + "\n", encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    ab = r["abandonment"]
    assert ab["daemon_log_attributed"] and ab["plays_with_pass_line"] < 36 and ab["pass_line_share"] == 1.0 and ab["pass_lines_mapped"] == ab["pass_lines_in_window"]
    assert ab["plays_abandoned"] == 3                                      # the abandoned WAV's three plays; plays without a line are not abandoned
    assert "residual-pass lines in the window map to a play slot" in open(run / "s6" / "s6_section5.md", encoding="utf8").read()


def test_lines_that_map_to_no_play_slot_push_the_share_below_the_floor(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    # 60 lines whose slot is the one AFTER the last play (inside the window's +30 s margin, but no play): local 18:10:10 - 5 s of pass = UTC 16:10:05 -> slot 16:09:45
    extra = ["[18:10:10 INF] Sub-feas residual pass: residualDecodes=0 elapsedMs=5000 deadlineAbandoned=False containedException=False fittedSignals=4" for i in range(60)]
    dl.write_text(dl.read_text(encoding="utf8") + "\n".join(extra) + "\n", encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert not r["abandonment"]["daemon_log_attributed"] and r["abandonment"]["pass_line_share"] < A.MIN_ATTRIBUTED_SHARE


def test_a_second_pass_line_for_the_same_slot_is_unmapped_and_one_line_stands_for_the_slot(tmp_path):
    """Architect amendment 5, ruling 1: ONE line maps a slot; a second line is unmapped (counting it passes exactly the error the 90 % floor guards). An ABANDONED line may stand for
    its slot, because that changes no count."""
    import re
    run, scratch, dl = make_run(tmp_path)
    base = dl.read_text(encoding="utf8").splitlines()
    assert A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)["abandonment"]["plays_abandoned"] == 0
    hh, mm, ss = map(int, re.match(r"\[(\d\d):(\d\d):(\d\d) ", base[0]).groups())
    dup = re.sub(r"^\[\d\d:\d\d:\d\d ", "[%02d:%02d:%02d " % (hh, mm, ss + 1), base[0]).replace("deadlineAbandoned=False", "deadlineAbandoned=True")   # one second later: the same slot by the formula
    dl.write_text("\n".join(base) + "\n" + dup + "\n", encoding="utf8")
    ab = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)["abandonment"]
    assert ab["pass_lines_in_window"] == len(base) + 1 and ab["pass_lines_mapped"] == len(base)          # the second line is NOT mapped
    assert ab["daemon_log_attributed"] and ab["plays_abandoned"] == 1                                    # still above the floor; the abandoned line stands for its slot


def test_formula_only_attribution_stands_the_abandoned_line_for_its_slot():
    def ln(sod, ms, ab):
        return {"sod": sod, "elapsed_ms": ms, "abandoned": ab, "exception": False, "fitted": 5, "residual_decodes": 0, "cycle_sod": None}
    # local = UTC + 2 h. Slot 15:59:30 UTC takes a pass whose start (T - elapsed) lies in [15:59:45, 16:00:00): T 15:59:53 / 3000 ms and T 15:59:55 / 3200 ms are both in it
    lines = [ln(17 * 3600 + 59 * 60 + 53, 3000, False), ln(17 * 3600 + 59 * 60 + 55, 3200, True)]
    slot = "261015_155930"
    pl = A.attribute_pass_lines(lines, [slot], 2 * 3600)
    assert pl["by_slot"][slot]["abandoned"] is True and pl["attributed_plays"] == 1
    assert pl["lines_mapped"] == 1 and pl["lines_in_window"] == 2                                   # ONE line maps the slot; the other is unmapped
    assert A.attribute_pass_lines([lines[0]], [slot], 2 * 3600)["by_slot"][slot]["abandoned"] is False


DESK_LOG = "\n".join([
    "[17:59:00 INF] Native FT8 decoder shim ABI version: 20260062.",
    "[17:59:46 INF] Early decode: cycle=15:59:30, n=1, elapsedMs=300, skipped=0, skipReason=none, finalWaitMs=0.",
    "[17:59:46 INF] Cycle 15:59:30: 3 decode(s) found, elapsed=900 ms.",
    "[17:59:50 INF] Sub-feas residual pass: residualDecodes=1 elapsedMs=3800 deadlineAbandoned=False containedException=False fittedSignals=5",
    "[18:00:00 INF] Early decode: cycle=15:59:45, n=1, elapsedMs=300, skipped=0, skipReason=none, finalWaitMs=0.",
    "[18:00:00 INF] Cycle 15:59:45: 2 decode(s) found, elapsed=800 ms.",
    # the artefact of the desk check (2026-10-15): this pass is fast, T has whole-second resolution, so T - elapsed = 15:59:59.86 falls BEFORE the 16:00:00 boundary and the formula
    # places the line one slot early (slot 15:59:30); its adjacent Cycle line says 15:59:45
    "[18:00:01 INF] Sub-feas residual pass: residualDecodes=0 elapsedMs=1141 deadlineAbandoned=True containedException=False fittedSignals=4",
]) + "\n"


def test_a_pass_line_belongs_to_the_cycle_of_its_adjacent_cycle_line_and_the_formula_is_the_cross_check(tmp_path):
    dl = tmp_path / "d.log"
    dl.write_text(DESK_LOG, encoding="utf8")
    lines = A.read_pass_lines(str(dl))
    assert [x["cycle_sod"] for x in lines] == [15 * 3600 + 59 * 60 + 30, 15 * 3600 + 59 * 60 + 45]
    slots = ["261015_155930", "261015_155945"]
    pl = A.attribute_pass_lines(lines, slots, 2 * 3600)
    assert pl["attribution"].startswith("the adjacent Cycle line")
    assert set(pl["by_slot"]) == set(slots) and pl["by_slot"]["261015_155945"]["abandoned"] is True      # the Cycle line puts the fast pass in ITS slot
    assert pl["lines_agree"] == 1 and pl["lines_disagree"] == 1 and pl["lines_cycle_mapped"] == 2 and pl["lines_in_window"] == 2
    assert pl["line_share"] == 0.5 and pl["share_cycle_mapped"] == 1.0                                   # the floor reads the lines where BOTH rules agree
    assert not pl["trusted"] and pl["window_abandoned_lines"] == 1
    # the formula ALONE (what the code did before) puts both lines in the first slot: the second slot has no line and its abandonment would be missed
    only = A.attribute_pass_lines([{**x, "cycle_sod": None} for x in lines], slots, 2 * 3600)
    assert set(only["by_slot"]) == {"261015_155930"}


def test_the_cycle_pairing_is_for_two_stage_logs_only_and_resets_at_a_daemon_start(tmp_path):
    two = tmp_path / "two.log"
    two.write_text(DESK_LOG + "\n".join(["[18:01:00 INF] Native FT8 decoder shim ABI version: 20260062.",
                                         "[18:01:03 INF] Sub-feas residual pass: residualDecodes=0 elapsedMs=900 deadlineAbandoned=False containedException=False fittedSignals=3"]) + "\n", encoding="utf8")
    assert [x["cycle_sod"] is None for x in A.read_pass_lines(str(two))] == [False, False, True]        # a pass line after a daemon start has no earlier Cycle line of ITS process
    single = tmp_path / "single.log"                                                                      # no 'Early decode' lines: single-stage, where the pass runs BEFORE the Cycle line
    single.write_text("\n".join(x for x in DESK_LOG.splitlines() if "Early decode" not in x) + "\n", encoding="utf8")
    assert all(x["cycle_sod"] is None for x in A.read_pass_lines(str(single)))                           # the formula alone is used there


def test_interim_rule_no_abandoned_line_in_the_window_reads_zero_and_the_sensitivity_equals_the_full_figure(tmp_path):
    """Architect amendment 5, ruling 2 (mechanical): below the floor, if NO parsed line in the S6 window is abandoned the field reads 0 and needs no attribution."""
    run, scratch, dl = make_run(tmp_path)
    extra = ["[18:10:10 INF] Sub-feas residual pass: residualDecodes=0 elapsedMs=5000 deadlineAbandoned=False containedException=False fittedSignals=4" for i in range(60)]
    dl.write_text(dl.read_text(encoding="utf8") + "\n".join(extra) + "\n", encoding="utf8")           # below the floor, nothing abandoned
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    ab = r["abandonment"]
    assert not ab["daemon_log_attributed"] and ab["interim_rule"] and ab["plays_abandoned"] == 0
    assert "no abandoned line in the window; attribution not needed" in ab["summary"]
    assert r["no_abandon"] is r["full"] and r["no_abandon_wavs"] == {"kept": 12, "of": 12} and "equals the full figure" in r["no_abandon_note"]
    md = open(run / "s6" / "s6_section5.md", encoding="utf8").read()
    assert "interim rule" in md and "equals the full figure" in md
    # one abandoned line anywhere in the window and the same log reads UNKNOWN, as before
    dl.write_text(dl.read_text(encoding="utf8") + extra[0].replace("deadlineAbandoned=False", "deadlineAbandoned=True") + "\n", encoding="utf8")
    r2 = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert not r2["abandonment"]["interim_rule"] and r2["abandonment"]["plays_abandoned"] is None and "UNKNOWN" in r2["abandonment"]["summary"] and "no_abandon" not in r2


def line_dt(stamp, snr, dt, freq, text):
    return "%s     14.074 Rx FT8 %5d %4.1f %4d %s\n" % (stamp, snr, dt, freq, text)


def with_corpus(tmp_path, run, shift, missing_live=False):
    """A synthetic corpus whose live ALL.TXT has the same rows as the replay slice, DT lower by `shift` (so DT(replay) - DT(live) = shift)."""
    from collections import defaultdict
    wl_items, live = [], defaultdict(list)
    rows = [json.loads(x) for x in (run / "s6" / "s6_playlog.jsonl").read_text(encoding="utf8").splitlines()]
    plays = [r for r in rows if r["kind"] == "play"]
    texts = {}
    for ln in (tmp_path / "scratch" / "wsjt-s6.txt").read_text(encoding="utf8").splitlines():
        p = ln.split(None, 7)
        texts.setdefault(p[0], []).append((p[4], p[6], " ".join(p[7:])))
    seen = set()
    for p in plays:
        if p["wav_id"] in seen:
            continue
        seen.add(p["wav_id"])
        stamp = "261001_10%02d%02d" % ((len(seen) * 15) // 60, (len(seen) * 15) % 60)        # on a 15 s slot boundary (the reader snaps off-grid stamps)
        wl_items.append({"id": p["wav_id"], "run": "runA", "stamp": stamp})
        for snr, freq, text in texts[p["slot_stamp"]]:
            if "<" not in text:
                live[stamp].append(line_dt(stamp, int(snr), round(0.1 - shift, 1), int(freq), text))
    d = tmp_path / "corpus" / "wsjt-x" / "runA"
    d.mkdir(parents=True, exist_ok=True)
    if not missing_live:
        (d / "ALL.TXT").write_text("".join("".join(v) for v in live.values()), encoding="utf8")
    wl = tmp_path / "wl.json"
    wl.write_text(json.dumps({"items": wl_items}), encoding="utf8")
    return str(tmp_path / "corpus"), str(wl)


def test_v2d_passes_when_every_read_play_shift_is_inside_the_bar(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    corpus, wl = with_corpus(tmp_path, run, shift=0.1)
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50, corpus=corpus, wavlist_path=wl)
    od = r["validity"]["S6-V2"]["onset"]
    assert od["result"] == "PASS" and od["plays_read"] == 36 and od["min_s"] == od["max_s"] == 0.1 and od["bar_s"] == [0.0, 0.3]
    assert r["status"] == "VALID" and "S6-V2(d) onset: PASS" in open(run / "s6" / "s6_section5.md", encoding="utf8").read()


def test_v2d_fails_and_voids_the_block_when_a_read_play_is_outside_the_bar(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    corpus, wl = with_corpus(tmp_path, run, shift=0.4)                       # the replay chain added 0.4 s: outside [0.0, +0.3]
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50, corpus=corpus, wavlist_path=wl)
    assert r["validity"]["S6-V2"]["onset"]["result"] == "FAIL" and r["validity"]["S6-V2"]["result"] == "FAIL" and r["status"].startswith("VOID")
    corpus2, wl2 = with_corpus(tmp_path, run, shift=-0.1)                     # overwrites the same synthetic corpus
    r2 = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50, corpus=corpus2, wavlist_path=wl2)
    assert r2["validity"]["S6-V2"]["onset"]["result"] == "FAIL" and r2["validity"]["S6-V2"]["onset"]["min_s"] == -0.1     # early is outside as well


def test_v2d_fails_when_the_check_can_be_made_but_no_play_can_be_read(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    corpus, wl = with_corpus(tmp_path, run, shift=0.1, missing_live=True)
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50, corpus=corpus, wavlist_path=wl)
    assert r["validity"]["S6-V2"]["onset"]["result"] == "FAIL" and "no play could be read" in r["validity"]["S6-V2"]["onset"]["reason"]


def test_v2d_is_not_checked_without_a_corpus_and_says_so(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["validity"]["S6-V2"]["onset"]["result"] == "NOT CHECKED" and r["status"] == "VALID"
    assert "S6-V2(d) onset: NOT CHECKED" in open(run / "s6" / "s6_section5.md", encoding="utf8").read()


# ---- S6-V7, appraiser coverage (Architect amendment 3, 2026-10-14) ---------------------------------------------------------------------------

def _slots(run, plays_rows, drop_wsjtx=0, drop_owsfz=0, wsjtx=True, owsfz=True, gate=True):
    from harness import liveness as LV
    iso = [LV.stamp_to_iso(r["slot_stamp"]) for r in plays_rows if r["kind"] == "play"]
    if wsjtx:
        LV.write_slots(str(run / "coverage_slots_wsjtx.txt"), set(iso[drop_wsjtx:]))
    if owsfz:
        LV.write_slots(str(run / "coverage_slots_owsfz.txt"), set(iso[drop_owsfz:]))
    if gate:
        (run / "liveness_gate.json").write_text("{}", encoding="utf8")


def _rows(run):
    return [json.loads(x) for x in (run / "s6" / "s6_playlog.jsonl").read_text(encoding="utf8").splitlines()]


def test_v7_passes_with_every_play_slot_present_for_both_appraisers(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    _slots(run, _rows(run))
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    v7 = r["validity"]["S6-V7"]
    assert v7["result"] == "PASS" and v7["wsjtx"]["missing"] == 0 and v7["owsfz"]["missing"] == 0 and r["status"] == "VALID"


def test_v7_one_missing_slot_for_one_appraiser_fails_and_voids_the_block(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    _slots(run, _rows(run), drop_wsjtx=1)                           # WSJT-X has no WAV for the first play slot: not a tolerance of expected - 1
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    v7 = r["validity"]["S6-V7"]
    assert v7["result"] == "FAIL" and v7["wsjtx"]["missing"] == 1 and v7["owsfz"]["missing"] == 0 and r["status"].startswith("VOID") and "S6-V7 FAIL" in r["status"]


def test_v7_the_dry_run_shape_a_third_of_the_plays_unheard_fails(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    rows = _rows(run)
    _slots(run, rows, drop_wsjtx=0)
    from harness import liveness as LV
    iso = [LV.stamp_to_iso(x["slot_stamp"]) for x in rows if x["kind"] == "play"]
    LV.write_slots(str(run / "coverage_slots_wsjtx.txt"), set(iso[: len(iso) * 2 // 3]))
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["validity"]["S6-V7"]["result"] == "FAIL" and r["validity"]["S6-V7"]["wsjtx"]["missing"] == len(iso) - len(iso) * 2 // 3


def test_v7_lists_missing_with_the_gate_on_fails_and_without_the_gate_reads_not_measured(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    (run / "liveness_gate.json").write_text("{}", encoding="utf8")                       # the battery ran with the gate but no slot lists were written
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["validity"]["S6-V7"]["result"] == "FAIL" and r["status"].startswith("VOID")
    run2, scratch2, dl2 = make_run(tmp_path / "second")
    r2 = A.run(str(run2), str(scratch2), str(dl2), "x", "y", n_boot=50)
    assert r2["validity"]["S6-V7"]["result"] == "NOT MEASURED" and r2["status"] == "VALID"   # an older run: not a PASS, and it does not void


# ---- SEQUENTIAL S6 (Captain 2026-10-15): the two appraisers played the identical schedule in turn, in different slots ---------------------------

def test_sequential_run_gives_the_same_figures_as_the_concurrent_run_of_the_same_decodes(tmp_path):
    run_c, scr_c, dl_c = make_run(tmp_path / "c", abandon_wav="b03:s03")
    run_s, scr_s, dl_s = make_run(tmp_path / "s", abandon_wav="b03:s03", sequential=True)
    rc = A.run(str(run_c), str(scr_c), str(dl_c), "x", "y", n_boot=50)
    rs = A.run(str(run_s), str(scr_s), str(dl_s), "x", "y", n_boot=50)
    assert rc["design"] == "concurrent" and rs["design"] == "sequential"
    assert rs["status"] == "VALID", rs["validity"]
    assert rs["validity"]["S6-V2"]["stray_lines"] == {"wsjtx": 0, "owsfz": 0}
    hc, hs = rc["full"]["headline"], rs["full"]["headline"]
    for k in ("decodes_per_wav_wsjtx", "decodes_per_wav_owsfz", "positive_agreement", "consistency_own_wsjtx", "consistency_own_owsfz", "snr_delta_mean"):
        assert hc[k] == hs[k], k                                                       # same decodes, same attribution: the slots are only keys
    assert rs["abandonment"]["plays_abandoned"] == 3 and rs["abandonment"]["daemon_log_attributed"]      # the daemon log is read in the OpenWSFZ pass's slots
    md = open(run_s / "s6" / "s6_section5.md", encoding="utf8").read()
    assert "SEQUENTIAL" in md and "Not pooled with a concurrent S6 row" in md
    assert "SEQUENTIAL" not in open(run_c / "s6" / "s6_section5.md", encoding="utf8").read()


def test_sequential_stray_lines_are_judged_against_each_logs_own_pass(tmp_path):
    run, scratch, dl = make_run(tmp_path, sequential=True)
    # an OpenWSFZ line stamped in the WSJT-X pass's slot (the daemon was supposed to be OFF then) is a stray in the OpenWSFZ log
    rows = _rows(run)
    first_w = [r for r in rows if r["kind"] == "play"][0]["slot_stamp"]
    with open(scratch / "owsfz-s6.txt", "a", encoding="utf8") as fh:
        fh.write(line(first_w, -5, 1000, "CQ QSTRAY FN42"))
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["validity"]["S6-V2"]["stray_lines"] == {"wsjtx": 0, "owsfz": 1} and r["status"].startswith("VOID")


def test_sequential_v7_checks_each_appraiser_against_its_own_pass_slots(tmp_path):
    from harness import liveness as LV
    run, scratch, dl = make_run(tmp_path, sequential=True)
    plays = [r for r in _rows(run) if r["kind"] == "play"]
    LV.write_slots(str(run / "coverage_slots_wsjtx.txt"), {LV.stamp_to_iso(p["slot_stamp"]) for p in plays})
    LV.write_slots(str(run / "coverage_slots_owsfz.txt"), {LV.stamp_to_iso(p["slot_stamp_o"]) for p in plays})
    (run / "liveness_gate.json").write_text("{}", encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    v7 = r["validity"]["S6-V7"]
    assert v7["result"] == "PASS" and v7["wsjtx"]["missing"] == 0 and v7["owsfz"]["missing"] == 0 and r["status"] == "VALID"
    # the OpenWSFZ archive holding the WSJT-X pass's slots (the concurrent assumption) is NOT coverage of the OpenWSFZ pass
    LV.write_slots(str(run / "coverage_slots_owsfz.txt"), {LV.stamp_to_iso(p["slot_stamp"]) for p in plays})
    r2 = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r2["validity"]["S6-V7"]["result"] == "FAIL" and r2["validity"]["S6-V7"]["owsfz"]["missing"] == len(plays)


def test_the_chain_label_is_the_architects_sequential_label_built_from_the_host(tmp_path):
    run, scratch, dl = make_run(tmp_path, sequential=True)
    rc = tmp_path / "asoundrc"
    rc.write_text("\n".join(["pcm.rr_in {", " type plug", ' slave.pcm "rr_cap"', ' rate_converter "samplerate_best"', "}"]) + "\n", encoding="utf8")
    assert A.alsa_chain_label(str(rc)) == "non-default ALSA chain (rate_converter samplerate_best)"
    rc.write_text("pcm.rr_in { type plug }\n", encoding="utf8")
    assert A.alsa_chain_label(str(rc)).startswith("default ALSA chain")
    assert "NOT READ" in A.alsa_chain_label(str(tmp_path / "missing"))
    lab = A.describe_chain(str(run), "sequential")
    assert "subtraction deadline ON" in lab and "SEQUENTIAL (each appraiser alone on the CPU)" in lab and "ALSA chain" in lab
    assert "WSJT-X decoding on the same CPUs" in A.describe_chain(str(run)) and "SEQUENTIAL" not in A.describe_chain(str(run))


def test_the_sequential_block_marks_every_between_appraiser_figure_and_states_the_library_and_the_abandonment_caveat(tmp_path):
    run, scratch, dl = make_run(tmp_path, sequential=True)
    r = A.run(str(run), str(scratch), str(dl), "x", None, n_boot=50)
    md = open(run / "s6" / "s6_section5.md", encoding="utf8").read()
    for frag in ("Positive agreement between the appraisers** †", "Decodes per WAV, OpenWSFZ minus WSJT-X †", "SNR delta (OpenWSFZ − WSJT-X) †", "Cohen's κ †",
                 "appraiser (AV) †", "part × appraiser (INT) †", "total R&R †", "appraiser means †"):
        assert frag in md, frag
    assert "**not separable**" in md and "Within-appraiser figures keep their meaning" in md
    assert "Library loaded by the fresh pass-O daemon" in md and "/x/publish/libft8.so" in md and "abc123" in md
    assert "NOT comparable with the concurrent 10-14 dry run's 0 of 68" in md
    assert "SEQUENTIAL (each appraiser alone on the CPU)" in r["cpu_chain_label"]
    # the within-appraiser rows carry no dagger, and a concurrent block carries none at all
    assert "within-appraiser consistency, own universe (decoded in all 3 of the trials it decoded in at least once) †" not in md
    run2, scratch2, dl2 = make_run(tmp_path / "c")
    A.run(str(run2), str(scratch2), str(dl2), "x", "y", n_boot=50)
    assert "†" not in open(run2 / "s6" / "s6_section5.md", encoding="utf8").read()
