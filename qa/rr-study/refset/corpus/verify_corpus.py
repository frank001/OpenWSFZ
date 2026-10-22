"""Verify the frozen REFERENCE-SET corpus against its manifest (QA tooling). Every run's harness calls this FIRST and refuses on any problem.

    python verify_corpus.py [--corpus <folder>]        exit 0 = intact, 1 = refused (counts and file names only; no message text)

Checks: manifest.json matches MANIFEST.sha256; every file listed in the manifest exists, has the listed size and SHA-256; no file in the
folder is missing from the manifest (nothing added); every WAV has the expected format (12 kHz, mono, 16 bit, 180,000 samples).
"""
import argparse
import hashlib
import json
import os
import sys
import wave

DEFAULT = r"D:\Projects\claude\OpenWSFZ\artefacts\rr-s6-refset-corpus"
SELF_FILES = {"manifest.json", "MANIFEST.sha256"}      # not listed inside the manifest (it cannot hash itself)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify(root, check_wav_format=True):
    """-> (ok, problems[list of str], n_checked)."""
    problems = []
    mpath, spath = os.path.join(root, "manifest.json"), os.path.join(root, "MANIFEST.sha256")
    if not (os.path.isfile(mpath) and os.path.isfile(spath)):
        return False, ["manifest.json or MANIFEST.sha256 missing"], 0
    want = open(spath, encoding="utf8").read().split()[0]
    if sha256_file(mpath) != want:
        return False, ["manifest.json does not match MANIFEST.sha256"], 0
    manifest = json.load(open(mpath, encoding="utf8"))
    listed = {f["path"]: f for f in manifest["files"]}
    n = 0
    for rel, f in listed.items():
        p = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(p):
            problems.append("missing: " + rel)
            continue
        if os.path.getsize(p) != f["size"]:
            problems.append("size differs: " + rel)
            continue
        if sha256_file(p) != f["sha256"]:
            problems.append("SHA-256 differs: " + rel)
            continue
        if check_wav_format and rel.endswith(".wav"):
            try:
                with wave.open(p, "rb") as w:
                    if (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()) != (12000, 1, 2, 180000):
                        problems.append("WAV format: " + rel)
            except Exception as e:  # noqa: BLE001
                problems.append("WAV unreadable: %s (%s)" % (rel, type(e).__name__))
        n += 1
    for dp, _dirs, fns in os.walk(root):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
            if rel not in listed and rel not in SELF_FILES:
                problems.append("not in the manifest (added?): " + rel)
    return not problems, problems, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT)
    a = ap.parse_args()
    ok, problems, n = verify(a.corpus)
    if ok:
        print("CORPUS INTACT: %d files verified against manifest.json" % n)
        return 0
    print("CORPUS REFUSED: %d problem(s); first: %s" % (len(problems), problems[:5]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
