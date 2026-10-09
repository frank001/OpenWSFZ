"""Tests for the classifier v2 and the A1 verdict rows (spec amendment 1; HK-025(k)): the synthetic 2-copy cycle must come out
FREQ_MISS and DUP and E_ON_COPY and F_ON_OTHER_COPY, a cycle with no repeated text must not, and the verdict rows must not fire vacuously."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws_early_classify_v2 as C  # noqa: E402
import early_dup_rows as V  # noqa: E402

T1 = "CQ Q1AAA JO22"
CYC = "2026-10-09T12:00:15Z"
TRUTH2 = [(T1, 500.0), (T1, 1763.0), ("Q2BBB Q3CCC -07", 900.0), ("Q2BBB Q3CCC -07", 2163.0)]


class ClassifyRowTests(unittest.TestCase):
    def test_two_copy_cycle_early_on_one_copy_final_on_the_other(self):
        r = C.classify_row(T1, 501, [(T1, 1762)], [], TRUTH2)
        self.assertEqual(r["label"], "FREQ_MISS")
        self.assertTrue(r["DUP"] and r["E_ON_COPY"] and r["F_ON_OTHER_COPY"])
        self.assertEqual(r["df_this_hz"], 1261)

    def test_no_repeated_text_is_not_dup(self):
        r = C.classify_row(T1, 500, [(T1, 1700)], [], [(T1, 500.0)])
        self.assertFalse(r["DUP"])
        self.assertFalse(r["F_ON_OTHER_COPY"])

    def test_confirmed_position_would_not_be_far(self):
        r = C.classify_row(T1, 500, [(T1, 503)], [], TRUTH2)               # within the matcher's 10 Hz: not a FREQ_MISS
        self.assertNotEqual(r["label"], "FREQ_MISS")

    def test_echo_of_the_previous_slot_is_labelled_and_is_not_explained(self):
        r = C.classify_row(T1, 500, [], [(T1, 502)], TRUTH2)
        self.assertEqual(r["label"], "ECHO_PREV")
        self.assertFalse(V.explained(r))

    def test_early_off_every_copy(self):
        r = C.classify_row(T1, 1100, [(T1, 1762)], [], TRUTH2)
        self.assertFalse(r["E_ON_COPY"])
        self.assertFalse(V.explained(r))

    def test_no_text_leaves_the_function(self):
        r = C.classify_row(T1, 501, [(T1, 1762)], [], TRUTH2)
        self.assertNotIn("Q1AAA", json.dumps(r))


class TrackerTests(unittest.TestCase):
    def test_buffers_then_finalizes_against_the_plays_truth(self):
        tr = C.Tracker()
        tr.on_early({"payload": [{"earlyId": 1, "decode": {"message": T1, "freqHz": 501}}, {"earlyId": 2, "decode": {"message": "Q2BBB Q3CCC -07", "freqHz": 900}}]})
        tr.on_final({"payload": [{"message": T1, "freqHz": 1762}, {"message": "Q2BBB Q3CCC -07", "freqHz": 900}],
                     "resolves": [{"earlyId": 1, "outcome": "unconfirmed"}, {"earlyId": 2, "outcome": "confirmed", "finalIndex": 1}]}, "2026-10-09T12:00:30.100000Z")
        truth = [{"scenario_id": "S4", "cycle_utc": CYC, "message_text": t, "true_freq_hz": str(f)} for t, f in TRUTH2]
        out = tr.finalize(truth)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["final_frame"])
        self.assertEqual((out[0]["unconfirmed"], out[0]["confirmed"], out[0]["lookup_miss"]), (1, 1, 0))
        self.assertTrue(V.explained(out[0]["rows"][0]))
        self.assertTrue(out[0]["repeated_text_in_truth"])

    def test_a_cycle_without_a_final_frame_is_flagged(self):
        tr = C.Tracker()
        truth = [{"scenario_id": "S4", "cycle_utc": CYC, "message_text": T1, "true_freq_hz": "500"}]
        out = tr.finalize(truth)
        self.assertFalse(out[0]["final_frame"])

    def test_a_resolution_for_an_unseen_early_row_is_a_lookup_miss(self):
        tr = C.Tracker()
        tr.on_final({"payload": [], "resolves": [{"earlyId": 9, "outcome": "unconfirmed"}]}, "2026-10-09T12:00:30.100000Z")
        truth = [{"scenario_id": "S4", "cycle_utc": CYC, "message_text": T1, "true_freq_hz": "500"}]
        self.assertEqual(tr.finalize(truth)[0]["lookup_miss"], 1)


def cyc(rows=(), repeated=True, final=True, miss=0):
    return {"cycle_utc": CYC, "final_frame": final, "unconfirmed": len(rows), "confirmed": 5, "lookup_miss": miss, "rows": list(rows), "repeated_text_in_truth": repeated}


GOOD = {"label": "FREQ_MISS", "DUP": True, "E_ON_COPY": True, "F_ON_OTHER_COPY": True}


def play(cycles, disc=0, pin=True, fin=True):
    return {"cycles": cycles, "disconnects_during": disc, "finalized": fin, "pin_ok": pin}


class VerdictTests(unittest.TestCase):
    def test_none_is_not_dup(self):                                           # non-vacuity (amendment 1)
        v, _ = V.verdict([play([cyc()]), play([cyc()])])
        self.assertEqual(v, "ED-NONE")

    def test_dup_when_every_row_is_explained(self):
        v, d = V.verdict([play([cyc([GOOD, GOOD])]), play([cyc([GOOD])])])
        self.assertEqual((v, d["unconfirmed_total"], d["dup_rows_per_play"]), ("ED-DUP", 3, [2, 1]))

    def test_other_when_one_row_is_not_explained(self):
        bad = dict(GOOD, label="NO_MATCH", F_ON_OTHER_COPY=False)
        v, d = V.verdict([play([cyc([GOOD, bad])]), play([cyc()])])
        self.assertEqual(v, "ED-OTHER")
        self.assertEqual(d["unexplained_rows"], 1)

    def test_other_when_a_row_sits_in_a_cycle_without_a_repeated_text(self):
        v, d = V.verdict([play([cyc([GOOD], repeated=False)]), play([cyc()])])
        self.assertEqual(v, "ED-OTHER")
        self.assertEqual(d["rows_in_cycles_without_a_repeated_text"], 1)

    def test_invalid_beats_everything(self):
        for p in (play([cyc([GOOD], final=False)]), play([cyc([GOOD])], disc=1), play([cyc([GOOD], miss=1)]), play([cyc([GOOD])], pin=False), play([cyc([GOOD])], fin=False)):
            v, d = V.verdict([p, play([cyc([GOOD])])])
            self.assertEqual(v, "ED-INVALID", d)

    def test_play_facts_counts_disconnects_only_during_the_play(self):
        lines = [{"kind": "disconnect", "utc": "2026-10-09T12:00:00Z"}, {"kind": "frame", "utc": "2026-10-09T12:00:30Z"}, {"kind": "disconnect", "utc": "2026-10-09T12:01:00Z"},
                 {"kind": "finalized", "utc": "2026-10-09T12:05:00Z"}, {"kind": "disconnect", "utc": "2026-10-09T12:06:00Z"}]
        self.assertEqual(V.play_facts(lines)["disconnects_during"], 1)


if __name__ == "__main__":
    unittest.main()
