"""Tamper test for verify_corpus.py on a tiny synthetic corpus in a temp folder. Run: python test_verify_corpus.py (exit 0 = pass)."""
import json
import os
import shutil
import sys
import tempfile
import wave

import verify_corpus as V


def make(root):
    os.makedirs(os.path.join(root, "owsfz", "r"), exist_ok=True)
    files = []
    for i in range(2):
        rel = "owsfz/r/%06d_000000.wav" % i
        with wave.open(os.path.join(root, *rel.split("/")), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(12000)
            w.writeframes((b"\x01\x00" * 180000) if i == 0 else (b"\x02\x00" * 180000))
        p = os.path.join(root, *rel.split("/"))
        files.append({"path": rel, "sha256": V.sha256_file(p), "size": os.path.getsize(p)})
    open(os.path.join(root, "README.md"), "w").write("x")
    files.append({"path": "README.md", "sha256": V.sha256_file(os.path.join(root, "README.md")), "size": 1})
    m = os.path.join(root, "manifest.json")
    json.dump({"files": files}, open(m, "w"))
    open(os.path.join(root, "MANIFEST.sha256"), "w").write(V.sha256_file(m) + "  manifest.json\n")


def main():
    bad = 0

    def expect(cond, what):
        nonlocal bad
        if not cond:
            bad += 1
            print("FAIL", what)

    d = tempfile.mkdtemp(prefix="corpus_test_")
    try:
        make(d)
        ok, pr, n = V.verify(d)
        expect(ok and n == 3 and not pr, "intact corpus passes")
        # flip one byte
        p = os.path.join(d, "owsfz", "r", "000001_000000.wav")
        b = bytearray(open(p, "rb").read()); b[-1] ^= 0xFF; open(p, "wb").write(bytes(b))
        ok, pr, _ = V.verify(d)
        expect(not ok and any("SHA-256 differs" in x for x in pr), "a changed byte is refused")
        make(d)
        open(os.path.join(d, "owsfz", "r", "extra.wav"), "wb").write(b"x")
        ok, pr, _ = V.verify(d)
        expect(not ok and any("not in the manifest" in x for x in pr), "an added file is refused")
        make(d)
        os.remove(os.path.join(d, "owsfz", "r", "000000_000000.wav"))
        ok, pr, _ = V.verify(d)
        expect(not ok and any("missing" in x for x in pr), "a removed file is refused")
        make(d)
        open(os.path.join(d, "manifest.json"), "a").write(" ")
        ok, pr, _ = V.verify(d)
        expect(not ok and any("MANIFEST.sha256" in x for x in pr), "an edited manifest is refused")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("OK" if not bad else "%d FAILED" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
