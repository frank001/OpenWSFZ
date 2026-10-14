"""Tests for osd_fix_train.py: the rotation, the per-process validity predicate (fires on every failure mode), and data-blindness of the runner."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_train as T  # noqa: E402


def good(**kw):
    m = {"rc": 0, "dll_start": T.DLL_PIN, "dll_end": T.DLL_PIN, "replay81_sha": T.REPLAY81_PIN, "chunk_sha": "c", "chunk_sha_expected": "c",
         "readbacks": [(40, 1, 1), (40, 1, 1)], "nhard": 40, "sign": 1, "probes": [(40, True), (40, True)], "contained": 0, "cycles_done": 89, "cycles_expected": 89}
    m.update(kw)
    return m


class RotationTests(unittest.TestCase):
    def test_every_arm_takes_every_position_once(self):
        pos = {i: set() for i in range(7)}
        for r in range(1, 8):
            order = T.arm_order(r)
            self.assertEqual(sorted(order), list(range(7)))
            for p, arm in enumerate(order):
                pos[arm].add(p)
        for arm, s in pos.items():
            self.assertEqual(s, set(range(7)), arm)

    def test_documented_positions(self):
        self.assertEqual(T.arm_order(1)[0], 0)          # REF first in round 1
        self.assertEqual(T.arm_order(2)[-1], 0)         # ... last in round 2
        self.assertEqual(T.arm_order(3).index(0), 5)    # ... sixth in round 3


class ValidityTests(unittest.TestCase):
    def test_good(self):
        self.assertEqual(T.process_valid(good()), (True, []))

    def test_each_failure_fires(self):
        cases = {"V2prime_probe_miss": dict(rc=5), "rc": dict(rc=1), "V1_pin": dict(dll_end="x"), "V1_harness_pin": dict(replay81_sha="x"), "V2_chunk_sha": dict(chunk_sha="d"),
                 "V2_readback": dict(readbacks=[(40, 1, 1)]), "V2prime_probe": dict(probes=[(40, True), (40, False)]), "V3_contained_exception": dict(contained=1),
                 "V3_incomplete": dict(cycles_done=88)}
        for row, kw in cases.items():
            ok, bad = T.process_valid(good(**kw))
            self.assertFalse(ok, row)
            self.assertIn(row, bad)

    def test_wrong_switch_readback_fires(self):
        self.assertFalse(T.process_valid(good(readbacks=[(40, 0, 0), (40, 0, 0)]))[0])
        self.assertFalse(T.process_valid(good(readbacks=[(60, 1, 1), (60, 1, 1)]))[0])

    def test_arms(self):
        self.assertEqual([a[0] for a in T.ARMS], ["REF", "FIX40", "FIX30", "FIX24", "FIX50", "FIX60", "FIX0"])
        self.assertEqual([a[1] for a in T.ARMS], [0, 1, 1, 1, 1, 1, 1])


class BlindnessTests(unittest.TestCase):
    def test_runner_never_opens_result_files(self):
        src = open(T.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        body = src.split('class CpuSampler')[1]
        for forbidden in ("testb", "outcomes", "matched", "load_testb", "load_outcomes", "NET", "net_pp"):
            # these names may appear only in the command-line construction (file path arguments), never in a read
            for m in re.finditer(r"open\([^)]*" + forbidden, body):
                self.fail(f"runner opens a result file: {m.group(0)}")
        self.assertNotIn("import onoff_replay_rows", src)


if __name__ == "__main__":
    unittest.main()
