"""Tests for osd_fix_chunks.py: the 7 chunks, concatenated, equal TRAIN exactly; no cycle twice; warm-up rule; committed files match the generator."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osd_fix_chunks as C  # noqa: E402


class ChunkTests(unittest.TestCase):
    def setUp(self):
        self.sel = json.loads(C.lf_bytes(C.SELECTION))
        self.chunks = C.cut(self.sel["TRAIN"], self.sel["warmup"])

    def test_concatenation_equals_train(self):
        cat = [s for c in self.chunks for s in c["cycles"]]
        self.assertEqual(cat, self.sel["TRAIN"])
        self.assertEqual(len(set(cat)), 621)

    def test_sizes(self):
        self.assertEqual([len(c["cycles"]) for c in self.chunks], [89, 89, 89, 89, 89, 89, 87])

    def test_warmup_rule(self):
        self.assertEqual(self.chunks[0]["warmup"], self.sel["warmup"])
        for k in range(1, 7):
            self.assertEqual(self.chunks[k]["warmup"], self.chunks[k - 1]["cycles"][-1])
            self.assertNotIn(self.chunks[k]["warmup"], self.chunks[k]["cycles"], "a warm-up must not also be scored in its own chunk")

    def test_pin_refuses_wrong_source(self):
        orig = C.SELECTION_SHA256
        C.SELECTION_SHA256 = "0" * 64
        try:
            with self.assertRaises(AssertionError):
                C.build()
        finally:
            C.SELECTION_SHA256 = orig

    def test_committed_files_equal_generator(self):
        files, manifest = C.build()
        for name, data in files.items():
            self.assertEqual(C.lf_bytes(os.path.join(C.CHUNK_DIR, name)), data, name)
        self.assertEqual(C.lf_bytes(os.path.join(C.CHUNK_DIR, "chunks_manifest.json")), manifest)


if __name__ == "__main__":
    unittest.main()
