#!/usr/bin/env python
"""OSD-FIX TRAIN, interleaved (amendment 2026-10-08-1745 section 2): cut the frozen TRAIN list into 7 chunks, mechanically.

Source: qa/rr-study/results/2026-10-08-osd-fix/selection.json (LF SHA-256 pinned below), list TRAIN (621 cycles) IN ITS STORED ORDER.
Chunks 1..6 hold 89 cycles, chunk 7 holds 87 (6 x 89 + 87 = 621). Warm-up (one cycle, decoded and discarded by Replay81 at every process start):
chunk 1 = the file's own warmup; chunk k > 1 = the LAST cycle of chunk k-1 (scored once in chunk k-1, never scored as a warm-up).
Output (committed BEFORE any TRAIN decode): chunks/chunk_<k>.json in Replay81's selection format, and chunks/chunks_manifest.json with every file's LF SHA-256.
No decode happens here; only stamps are read (HK-037).

  python qa/rr-study/osd-fix/osd_fix_chunks.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RESULTS = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-08-osd-fix")
SELECTION = os.path.join(RESULTS, "selection.json")
SELECTION_SHA256 = "27bb840f45c77da6e65f18f855ade547e9a002a253c2946bf723a6eaa53db11e"
CHUNK_DIR = os.path.join(RESULTS, "chunks")
N_CHUNKS, CHUNK_SIZE, TRAIN_N = 7, 89, 621
STRATUM = "A"


def lf_bytes(path):
    return open(path, "rb").read().replace(b"\r\n", b"\n")


def lf_sha(path):
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def cut(train, warmup):
    """-> list of dicts {k, warmup, cycles}; pure function (tested)."""
    assert len(train) == TRAIN_N and len(set(train)) == TRAIN_N
    out, i = [], 0
    for k in range(1, N_CHUNKS + 1):
        n = CHUNK_SIZE if k < N_CHUNKS else TRAIN_N - CHUNK_SIZE * (N_CHUNKS - 1)
        cyc = train[i:i + n]
        i += n
        out.append({"k": k, "cycles": cyc, "warmup": warmup if k == 1 else out[-1]["cycles"][-1]})
    assert i == TRAIN_N
    return out


def render(obj):
    return (json.dumps(obj, sort_keys=True, indent=1) + "\n").encode("utf-8")


def build():
    assert lf_sha(SELECTION) == SELECTION_SHA256, "TRAIN selection.json differs from its pin"
    sel = json.loads(lf_bytes(SELECTION))
    chunks = cut(sel["TRAIN"], sel["warmup"])
    run = sel["run"]
    files, manifest = {}, {"selection_sha256_lf": SELECTION_SHA256, "run": run, "sizes": [len(c["cycles"]) for c in chunks], "chunks": {}}
    for c in chunks:
        name = f"chunk_{c['k']}.json"
        data = render({"note": f"OSD-FIX TRAIN chunk {c['k']} of {N_CHUNKS}", "run": run, "runs": {run: {"warmup": c["warmup"], STRATUM: c["cycles"]}}})
        files[name] = data
        manifest["chunks"][str(c["k"])] = {"file": name, "sha256_lf": hashlib.sha256(data).hexdigest(), "cycles": len(c["cycles"]), "warmup": c["warmup"]}
    return files, render(manifest)


def main():
    files, manifest = build()
    os.makedirs(CHUNK_DIR, exist_ok=True)
    for name, data in files.items():
        with open(os.path.join(CHUNK_DIR, name), "wb") as fh:
            fh.write(data)
    with open(os.path.join(CHUNK_DIR, "chunks_manifest.json"), "wb") as fh:
        fh.write(manifest)
    print("manifest_sha256_lf", hashlib.sha256(manifest).hexdigest())
    for k, v in json.loads(manifest)["chunks"].items():
        print(k, v["cycles"], v["sha256_lf"][:12], "warmup", v["warmup"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
