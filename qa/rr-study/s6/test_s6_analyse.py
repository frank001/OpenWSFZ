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


def make_run(tmp, n_wavs=12, stray=False, drop_play=False, abandon_wav=None, seed=5):
    rng = random.Random(seed)
    run, scratch = tmp / "run", tmp / "scratch"
    (run / "s6").mkdir(parents=True)
    scratch.mkdir()
    t0 = datetime(2026, 10, 13, 16, 0, 0)
    rows, wsjt, ows, dlog = [], [], [], []
    rows.append({"kind": "warmup", "attempt": 1, "boundary_utc": "x", "slot_stamp": t0.strftime("%y%m%d_%H%M%S"), "offset_s": 0.0, "wsjtx_lines": 1, "owsfz_lines": 1})
    wsjt.append(line(t0.strftime("%y%m%d_%H%M%S"), 6, 1500, "CQ QWARM FN42"))
    ows.append(line(t0.strftime("%y%m%d_%H%M%S"), 6, 1500, "CQ QWARM FN42"))
    wavs = [{"id": "b%02d:s%02d" % (i, i), "band": ["17m", "20m", "40m", "80m"][i % 4], "sun": "day", "gain": 2.0} for i in range(n_wavs)]
    truth = {w["id"]: [("CQ Q%dAAA FN42" % (i * 10 + j), rng.uniform(-18, 0), 500 + 100 * j) for j in range(5)] for i, w in enumerate(wavs)}
    sched = P.make_schedule(wavs)
    slot = t0 + timedelta(seconds=45)
    for (n, trial, order, item) in sched:
        st = slot.strftime("%y%m%d_%H%M%S")
        if not (drop_play and n == 7):
            rows.append({"kind": "play", "play_index": n, "trial": trial, "order": order, "wav_id": item["id"], "band": item["band"], "sun": "day",
                         "gain": 2.0, "boundary_utc": "x", "slot_stamp": st, "offset_s": 0.0, "slips_so_far": 0})
        for j, (text, snr, f) in enumerate(truth[item["id"]]):
            wsjt.append(line(st, round(snr), f, text))                                 # WSJT-X decodes all 5, steadily
            if rng.random() < 0.7:
                ows.append(line(st, round(snr + 1.0), f, text))                        # OWS decodes 70 %, SNR +1 dB
        wsjt.append(line(st, -20, 1900, "CQ <...> FN42"))                              # a hashed row, excluded
        ab = (item["id"] == abandon_wav)
        local = slot + timedelta(seconds=15 + 2 + 9) + timedelta(hours=TZ_H)           # pass ends 2 s of pass 0 + 9 s of residual after the slot's end
        dlog.append("[%s INF] Sub-feas residual pass: residualDecodes=1 elapsedMs=9000 deadlineAbandoned=%s containedException=False fittedSignals=7\n"
                    % (local.strftime("%H:%M:%S"), "True" if ab else "False"))
        slot += timedelta(seconds=15)
    if stray:
        wsjt.append(line((slot + timedelta(seconds=300)).strftime("%y%m%d_%H%M%S"), -5, 1000, "CQ QSTRAY FN42"))
    (run / "s6" / "s6_playlog.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf8")
    n_plays = len(wavs) * 3
    (run / "s6" / "s6_validity.json").write_text(json.dumps({
        "tier": "standard", "plays_planned": n_plays, "S6-V1": {"result": "PASS"}, "S6-V3": {"result": "PASS"}, "S6-V5": {"result": "PASS"}}), encoding="utf8")
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
    assert "Daemon-log attribution: 36 of 36 plays matched" in md and "DESIGN number" in md and "Observed play-start offsets" in md
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


def test_a_late_play_fails_v2_offset(tmp_path):
    run, scratch, dl = make_run(tmp_path)
    p = run / "s6" / "s6_playlog.jsonl"
    rows = [json.loads(x) for x in p.read_text(encoding="utf8").splitlines()]
    rows[5]["offset_s"] = 0.9
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf8")
    r = A.run(str(run), str(scratch), str(dl), "x", "y", n_boot=50)
    assert r["validity"]["S6-V2"]["plays_outside_tolerance"] == 1 and r["status"].startswith("VOID")


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
