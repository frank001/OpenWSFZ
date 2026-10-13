"""S6 (off-air WAV replay) design: the frozen tier list (QA tooling; spec 2026-10-13-1625 section 2.2, amendment 1).

    python s6_design.py build  --corpus <rr-s6-refset-corpus> --out s6-wavlist.json     (ONCE; never regenerated)
    python s6_design.py verify --corpus <rr-s6-refset-corpus> --wavlist s6-wavlist.json (every S6 run, before any sound)

The list is ONE seeded, band-stratified order over the frozen reference-set corpus; each tier is a PREFIX of it
(quick 24 within standard 60 within extended 180) and every prefix of a multiple of 4 is balanced 1:1:1:1 over the bands.
Source recording = the WSJT-X-side WAV (12 kHz mono 16 bit, as WSJT-X saved it). The list holds ids, SHA-256, band, sun state,
route and the applied playback gain; NO message text (NFR-021 / HK-037).

Draw rule (mechanical):
  1. candidates = the SCORED cycles (after the warm-up) of every non-excluded corpus block; a cycle any scan row of which carries a
     disqualifying class (clipping, error, format, hot, silent) is dropped;
  2. per band: blocks in a seeded shuffle (seed = SEED + band index); pass r takes the r-th cycle (seeded shuffle within the block)
     of every block that still has one, so a block contributes a second cycle only after every block of that band has contributed one;
  3. the bands interleave 17m, 20m, 40m, 80m, 17m, ...; a band that runs out is reported and the interleave goes on without it
     (a prefix is then balanced "as far as the corpus allows", with the shortfall stated in the file).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import wave

SEED = 20261013
BANDS = ["17m", "20m", "40m", "80m"]
TIERS = {"quick": 24, "standard": 60, "extended": 180}
K_TRIALS = 3
DISQUALIFYING = {"clipping", "error", "format", "hot", "silent"}
PLAYBACK_PEAK_LEVEL = 0.9        # = harness.run_scenario._PLAYBACK_PEAK_LEVEL (asserted by the unit test)
CORPUS_FS = 12_000
PLAY_FS = 48_000
CYCLE_SAMPLES = 180_000
SLOT_SAMPLES_48K = CYCLE_SAMPLES * (PLAY_FS // CORPUS_FS)      # 720,000: inside a continuous buffer EVERY slot must be exactly this long
WAVLIST_VERSION = 1


class SlotLengthError(ValueError):
    """A WAV whose slot is not exactly CYCLE_SAMPLES long: S6 stops under S6-V1 (amendment 2 (a)), with no padding."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def wav_path(corpus: str, run: str, stamp: str) -> str:
    return os.path.join(corpus, "wsjt-x", run, stamp + ".wav")


def read_wav_int16(path: str):
    import numpy as np
    with wave.open(path, "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != CORPUS_FS:
            raise ValueError("not 12 kHz mono 16-bit: " + os.path.basename(path))
        return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)


def render_48k(samples_int16):
    """12 kHz int16 -> float32 at 48 kHz, peak-normalised to PLAYBACK_PEAK_LEVEL exactly as every battery scenario is
    (run_scenario's peak normalisation). Returns (samples float32, gain applied, peak before normalisation)."""
    import numpy as np
    from scipy.signal import resample_poly
    if samples_int16.size != CYCLE_SAMPLES:
        # amendment 2 (a): a slot of any other length would shift every later play of its batch. Stop, never pad or cut.
        raise SlotLengthError("slot is %d samples at %d Hz, not %d" % (samples_int16.size, CORPUS_FS, CYCLE_SAMPLES))
    x = samples_int16.astype(np.float64) / 32768.0
    x = resample_poly(x, PLAY_FS // CORPUS_FS, 1).astype(np.float32)
    if x.size != SLOT_SAMPLES_48K:
        raise SlotLengthError("rendered slot is %d samples at %d Hz, not %d" % (x.size, PLAY_FS, SLOT_SAMPLES_48K))
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 0.0:
        return x, 0.0, 0.0
    gain = PLAYBACK_PEAK_LEVEL / peak
    return (x * gain).astype(np.float32), gain, peak


def scan_disqualified(corpus: str) -> set:
    """{(run, stamp)} with a disqualifying scan class on either side."""
    bad = set()
    p = os.path.join(corpus, "scan_cycles.csv")
    with open(p, newline="", encoding="utf8") as fh:
        for r in csv.DictReader(fh):
            flags = set(f for f in r["flags"].split("+") if f)
            if flags & DISQUALIFYING:
                bad.add((r["run"], r["stamp"]))
    return bad


def candidate_cycles(manifest: dict, bad: set) -> dict:
    """band -> {block_id: [cycle dict, ...]} over the scored cycles of the usable blocks."""
    out = {b: {} for b in BANDS}
    for blk in manifest["blocks"]:
        if blk.get("excluded") or blk["band"] not in out:
            continue
        w = int(blk["warmup_cycles"])
        cyc = [{"block": blk["id"], "run": blk["run"], "band": blk["band"], "sun": blk["sun"], "route": blk["route"], "stamp": s}
               for s in blk["cycles"][w:] if (blk["run"], s) not in bad]
        if cyc:
            out[blk["band"]][blk["id"]] = cyc
    return out


def draw_order(cands: dict, seed: int = SEED) -> tuple:
    """-> (ordered list of cycle dicts, per-band stats). Pure function of the candidates and the seed."""
    per_band_lists, stats = {}, {}
    for bi, band in enumerate(BANDS):
        rng = random.Random(seed + bi)
        blocks = sorted(cands[band])                     # sorted first: the shuffle must not depend on dict order
        rng.shuffle(blocks)
        shuffled = {bid: rng.sample(sorted(cands[band][bid], key=lambda c: c["stamp"]), len(cands[band][bid])) for bid in blocks}
        order, r = [], 0
        while True:
            took = [shuffled[bid][r] for bid in blocks if len(shuffled[bid]) > r]
            if not took:
                break
            order.extend(took)
            r += 1
        per_band_lists[band] = order
        stats[band] = {"blocks": len(blocks), "candidates": sum(len(v) for v in cands[band].values()), "passes": r}
    out, idx = [], {b: 0 for b in BANDS}
    while any(idx[b] < len(per_band_lists[b]) for b in BANDS):
        for b in BANDS:
            if idx[b] < len(per_band_lists[b]):
                out.append(per_band_lists[b][idx[b]])
                idx[b] += 1
    return out, stats


def build(corpus: str, out_path: str) -> dict:
    if os.path.exists(out_path):
        raise SystemExit("REFUSED: %s exists; the S6 wavlist is built once and never regenerated" % out_path)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "refset", "corpus"))
    import verify_corpus
    ok, problems, n = verify_corpus.verify(corpus)
    if not ok:
        raise SystemExit("REFUSED: corpus verification failed: %s" % problems[:3])
    manifest = json.load(open(os.path.join(corpus, "manifest.json"), encoding="utf8"))
    cands = candidate_cycles(manifest, scan_disqualified(corpus))
    order, stats = draw_order(cands)
    need = TIERS["extended"]
    if len(order) < need:
        raise SystemExit("REFUSED: only %d candidate cycles, the extended tier needs %d" % (len(order), need))
    files = {f["path"]: f["sha256"] for f in manifest["files"]}
    items = []
    for i, c in enumerate(order[:need]):
        rel = "wsjt-x/%s/%s.wav" % (c["run"], c["stamp"])
        path = wav_path(corpus, c["run"], c["stamp"])
        s16 = read_wav_int16(path)
        if s16.size != CYCLE_SAMPLES:
            raise SystemExit("REFUSED: unexpected length for " + rel)
        _, gain, peak = render_48k(s16)
        sha = files[rel]
        items.append({"rank": i, "id": "%s:%s" % (c["block"], c["stamp"]), "block": c["block"], "run": c["run"], "stamp": c["stamp"],
                      "band": c["band"], "sun": c["sun"], "route": c["route"], "wav_sha256": sha,
                      "peak_before_norm": round(peak, 6), "gain": round(gain, 6)})
    doc = {"version": WAVLIST_VERSION, "seed": SEED, "bands": BANDS, "k_trials": K_TRIALS, "tiers": TIERS,
           "corpus_manifest_sha256": sha256_file(os.path.join(corpus, "manifest.json")),
           "source": "WSJT-X-side WAV of each corpus cycle (12 kHz mono 16 bit)",
           "playback": "12 kHz -> 48 kHz (resample_poly x4), peak-normalised to %.2f as every battery scenario" % PLAYBACK_PEAK_LEVEL,
           "draw_stats_by_band": stats, "candidates_total": len(order),
           "tier_band_counts": {t: {b: sum(1 for x in items[:n] if x["band"] == b) for b in BANDS} for t, n in TIERS.items()},
           "tier_sun_counts": {t: {s: sum(1 for x in items[:n] if x["sun"] == s) for s in ("day", "twilight", "night")} for t, n in TIERS.items()},
           "items": items}
    with open(out_path, "w", encoding="utf8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
    return doc


def check_lengths(corpus: str, items: list) -> list:
    """Header-only check, before any sound: every WAV of the tier is 12 kHz mono 16-bit and exactly CYCLE_SAMPLES long. -> problems."""
    problems = []
    for it in items:
        try:
            with wave.open(wav_path(corpus, it["run"], it["stamp"]), "rb") as wf:
                if (wf.getframerate(), wf.getnchannels(), wf.getsampwidth(), wf.getnframes()) != (CORPUS_FS, 1, 2, CYCLE_SAMPLES):
                    problems.append("format or length of " + it["id"])
        except (OSError, wave.Error):
            problems.append("unreadable " + it["id"])
    return problems


def tier_items(wavlist: dict, tier: str) -> list:
    if tier not in TIERS:
        raise ValueError("unknown tier " + tier)
    return wavlist["items"][:TIERS[tier]]


def verify(corpus: str, wavlist_path: str, tier: str = "extended") -> tuple:
    """S6-V1: the corpus verifies, the manifest is the one the list was built from, and every WAV of the tier hashes as listed."""
    problems = []
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "refset", "corpus"))
    import verify_corpus
    ok, probs, _ = verify_corpus.verify(corpus)
    if not ok:
        problems += ["corpus: " + p for p in probs[:5]]
    wl = json.load(open(wavlist_path, encoding="utf8"))
    if sha256_file(os.path.join(corpus, "manifest.json")) != wl["corpus_manifest_sha256"]:
        problems.append("corpus manifest differs from the one the wavlist was built from")
    manifest = json.load(open(os.path.join(corpus, "manifest.json"), encoding="utf8"))
    files = {f["path"]: f["sha256"] for f in manifest["files"]}     # the corpus verification above hashed every one of them
    for it in tier_items(wl, tier):
        rel = "wsjt-x/%s/%s.wav" % (it["run"], it["stamp"])
        if files.get(rel) != it["wav_sha256"]:
            problems.append("WAV not in the manifest or hash differs from the list: " + it["id"])
    return (not problems), problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "verify"])
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out")
    ap.add_argument("--wavlist")
    ap.add_argument("--tier", default="extended")
    a = ap.parse_args()
    if a.cmd == "build":
        d = build(a.corpus, a.out)
        print("built", a.out, "items", len(d["items"]), "tier band counts", d["tier_band_counts"])
    else:
        ok, probs = verify(a.corpus, a.wavlist, a.tier)
        print("S6-V1", "PASS" if ok else "FAIL", probs[:5])
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
