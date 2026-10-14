"""Tests for osd_fix_test.py: the chunker, the pinned manifests, the configured TRAIN machinery, and the data-blindness of the runner."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_test as X  # noqa: E402


class TestRunnerTests(unittest.TestCase):
    def test_cut_sizes_and_warmup(self):
        cyc = [f"c{i:04d}" for i in range(860)]
        ch = X.cut(cyc, "warm")
        self.assertEqual([len(c["cycles"]) for c in ch], [215] * 4)
        self.assertEqual(ch[0]["warmup"], "warm")
        self.assertEqual(ch[1]["warmup"], ch[0]["cycles"][-1])
        self.assertEqual([x for c in ch for x in c["cycles"]], cyc)

    def test_chunks_match_their_pinned_manifests(self):
        for listname in X.LISTS:
            self.assertEqual(X.lf_sha(os.path.join(X.chunk_dir(listname), "chunks_manifest.json")), X.MANIFEST_SHA[listname])
            files, manifest = X.build_chunks(listname)
            for name, data in files.items():
                self.assertEqual(open(os.path.join(X.chunk_dir(listname), name), "rb").read().replace(b"\r\n", b"\n"), data)

    def test_sample_is_the_first_residue_of_test(self):
        import json
        sel = json.loads(X.lf_bytes(X.SELECTION))
        self.assertTrue(set(sel["SAMPLE"]) <= set(sel["TEST"]))
        self.assertEqual(len(sel["TEST"]), 860)

    def test_configure_points_the_train_machinery_at_test(self):
        X.configure("TEST")
        T = X.T
        self.assertEqual([a[0] for a in T.ARMS], ["REF", "FIX24"])
        self.assertEqual(T.N_ROUNDS, 4)
        self.assertEqual(X.N0.RUN, "20260930_1930")
        self.assertEqual(T.LABEL_STAGE, "test")
        self.assertTrue(T.OUT.endswith("rr_2026-10-09_osd_fix_test"))
        self.assertEqual(T.arm_order(1), [0, 1])
        self.assertEqual(T.arm_order(2), [1, 0])

    def test_arms_are_today_and_n_star(self):
        self.assertEqual(X.ARMS, [("REF", 0, 40), ("FIX24", 1, 24)])

    def test_runner_never_opens_result_files(self):
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "osd_fix_test.py"), encoding="utf-8").read()
        body = src.split('"""', 2)[2]
        for bad in ("testb.csv", "matched.csv", "outcomes.csv"):
            self.assertIsNone(re.search(r"open\([^)]*" + re.escape(bad), body), bad)

    def test_not_the_train_night(self):
        self.assertNotEqual(X.RUN, "20261004_1634")


if __name__ == "__main__":
    unittest.main()
