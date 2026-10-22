"""Tests for s6_onset: the shift is DT(replay) - DT(live) per matched row, medianed per play; hashed rows and unmatched rows never count."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import s6_onset as O  # noqa: E402


def line(stamp, snr, dt, freq, text):
    return "%s     14.074 Rx FT8 %5d %4.1f %4d %s\n" % (stamp, snr, dt, freq, text)


def build(tmp_path, shift, n_rows=6, hashed=True):
    corpus = tmp_path / "corpus" / "wsjt-x" / "runA"
    corpus.mkdir(parents=True)
    texts = ["CQ Q%dAAA FN42" % i for i in range(n_rows)]
    live = "".join(line("261001_100015", -10, 0.2 + 0.1 * (i % 3), 500 + 100 * i, t) for i, t in enumerate(texts))
    live += line("261001_100015", -10, 0.3, 2800, "CQ <...> FN42")                  # hashed: ignored
    live += line("261001_100015", -12, 0.4, 2900, "CQ Q9ZZZ FN42")                  # decoded live only: ignored
    (corpus / "ALL.TXT").write_text(live, encoding="utf8")
    rep = "".join(line("261013_120000", -10, round(0.2 + 0.1 * (i % 3) + shift, 1), 500 + 100 * i, t) for i, t in enumerate(texts))
    rep += line("261013_120000", -10, 9.9, 2800, "CQ <...> FN42")                    # hashed: ignored, however far off
    sl = tmp_path / "wsjt-s6.txt"
    sl.write_text(rep, encoding="utf8")
    wl = {"items": [{"id": "b:s", "run": "runA", "stamp": "261001_100015"}]}
    plays = [{"wav_id": "b:s", "slot_stamp": "261013_120000"}]
    return plays, str(sl), str(tmp_path / "corpus"), wl


def test_the_shift_is_replay_dt_minus_live_dt_and_ignores_hashed_and_unmatched_rows(tmp_path):
    plays, sl, corpus, wl = build(tmp_path, shift=0.1)
    r = O.onset_row(plays, sl, corpus, wl)
    assert r["plays"] == 1 and r["plays_with_median"] == 1 and r["rows_matched"] == 6
    assert r["per_play_median_shift_s"]["median"] == 0.1 and r["all_rows_shift_s"]["median"] == 0.1
    (tmp_path / "b").mkdir()
    plays, sl, corpus, wl = build(tmp_path / "b", shift=-0.5)
    assert O.onset_row(plays, sl, corpus, wl)["per_play_median_shift_s"]["median"] == -0.5


def test_a_play_with_too_few_matched_rows_gives_no_median_but_is_counted(tmp_path):
    plays, sl, corpus, wl = build(tmp_path, shift=0.2, n_rows=2)
    r = O.onset_row(plays, sl, corpus, wl)
    assert r["plays_with_median"] == 0 and r["plays_without_enough_rows"] == 1 and r["rows_matched"] == 2
    assert r["per_play_median_shift_s"]["median"] is None


def test_a_missing_live_log_is_zero_matches_not_a_crash(tmp_path):
    plays, sl, corpus, wl = build(tmp_path, shift=0.1)
    os.remove(os.path.join(corpus, "wsjt-x", "runA", "ALL.TXT"))
    r = O.onset_row(plays, sl, corpus, wl)
    assert r["rows_matched"] == 0 and r["plays_with_median"] == 0


def test_output_holds_numbers_only(tmp_path):
    plays, sl, corpus, wl = build(tmp_path, shift=0.1)
    s = json.dumps(O.onset_row(plays, sl, corpus, wl))
    assert "CQ" not in s and "Q0AAA" not in s
