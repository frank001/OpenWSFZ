#!/usr/bin/env python
"""NHARD-REP: render the V2 noise positive control and freeze selection.json (cycle list, sample, AA list, noise manifest).

Spec (PRE-REGISTERED, Architect 2026-10-06 14:31Z + Amendment 1 15:01Z; BAR_N = 0.5 pp ratified by the Captain 14:34Z):
  qa/rr-study/2026-10-06-1430-architect-to-qa-spec-nhard-replication.md   (read on branch arch/nhard-replication)

  Corpus   : artefacts/20261004_1634_endurance_run-gathered/owsfz/wav/   (3 106 OpenWSFZ WAVs)
  Included : every WAV that passes R0 (RIFF/WAVE, mono, 12 kHz, 16-bit, exactly 180 000 samples) EXCEPT the first and last
             stamps of the window. Cycles where WSJT-X logged 0 decodes are KEPT (excluding them would select on the reference).
             Warm-up = the first stamp (an excluded edge cycle), decoded and discarded at every process start.
  SAMPLE   : positions i (0-based, in the included list, by POSITION not stamp) with i mod 10 == 0      (Amendment 1)
  SAMPLE_B : positions i mod 10 == 5 -- the pre-named second sample the Captain MAY add under N-OPEN (frozen now, not run)
  AA       : the FIRST 200 entries of SAMPLE (row V6)
  NOISE    : 200 scored seeded pure-noise WAVs (+1 warm-up), label NHARD-REP-PC, normalise_rms(., 0.20) (row V2)

No decode happens here. Only WAV headers are read (corpus) and noise is synthesised. No message text, callsign or ALL.TXT
content is read or written (HK-037 / NFR-021). selection.json is deterministic (sorted keys, indent 1, LF); its LF-normalised
SHA-256 is pinned in nhard_rep_run.py and asserted before every arm.

  python qa/rr-study/nhard-rep/nhard_rep_select.py
  OPENWSFZ_ARTEFACTS=<dir> overrides the artefacts directory.
"""
import hashlib
import json
import os
import re
import struct
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study"))
from harness.common import compute_seed  # noqa: E402  (the E1 seeding convention: SHA-256 of "label,part,trial")

ART = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
RUN = "20261004_1634"
WAV_DIR = os.path.join(ART, f"{RUN}_endurance_run-gathered", "owsfz", "wav")
OUT_ART = os.path.join(ART, "rr_2026-10-06_nhard_rep")
NOISE_DIR = os.path.join(OUT_ART, "noise")
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep")
SELECTION = os.path.join(OUT_DIR, "selection.json")

STAMP = re.compile(r"^\d{6}_\d{6}$")
PCM_SAMPLES = 180_000
SAMPLE_RATE_HZ = 12_000
SAMPLE_STEP = 10          # Amendment 1
SAMPLE_OFFSET_A = 0
SAMPLE_OFFSET_B = 5
AA_CYCLES = 200           # Amendment 1, row V6
NOISE_LABEL = "NHARD-REP-PC"
NOISE_SCORED = 200        # Amendment 1, row V2
NOISE_TARGET_RMS = 0.20   # Ft8Decoder.cs PcmNormalisationTargetRms, the E1 contract
NOISE_FIRST_STAMP = "261006_000000"   # synthetic stamps, 15 s apart (the harness parses a yyMMdd_HHmmss stamp)


def r0_ok(path):
    """The harness's own per-file assertion (Program.cs ReadWav): 12 kHz mono 16-bit, exactly 180 000 samples."""
    with open(path, "rb") as fh:
        b = fh.read()
    if len(b) < 44 or b[0:4] != b"RIFF" or b[8:12] != b"WAVE":
        return False, "not_riff_wave"
    pos, channels, rate, bits, data_len = 12, 0, 0, 0, -1
    while pos + 8 <= len(b):
        cid = b[pos:pos + 4]
        (clen,) = struct.unpack_from("<i", b, pos + 4)
        if cid == b"fmt ":
            channels = struct.unpack_from("<h", b, pos + 10)[0]
            rate = struct.unpack_from("<i", b, pos + 12)[0]
            bits = struct.unpack_from("<h", b, pos + 22)[0]
        elif cid == b"data":
            data_len = clen
            break
        pos += 8 + clen + (clen & 1)
    if channels != 1 or rate != SAMPLE_RATE_HZ or bits != 16 or data_len < 0 or data_len // 2 != PCM_SAMPLES:
        return False, f"format ch={channels} rate={rate} bits={bits} samples={data_len // 2 if data_len >= 0 else -1}"
    return True, ""


def normalise_rms(pcm, target=NOISE_TARGET_RMS):
    """pcm * target/rms(pcm): identical formula to the E1 / part_nt contract."""
    src = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    return (pcm * (target / src)).astype(np.float64)


def noise_stamps():
    """201 synthetic stamps: index 0 is the discarded warm-up, 1..200 are scored."""
    import datetime
    t0 = datetime.datetime.strptime(NOISE_FIRST_STAMP, "%y%m%d_%H%M%S")
    return [(t0 + datetime.timedelta(seconds=15 * i)).strftime("%y%m%d_%H%M%S") for i in range(NOISE_SCORED + 1)]


def render_noise_pcm(index):
    """int16 samples of noise file `index` (0 = warm-up). Seed = compute_seed(label, 0, index), numpy PCG64 default_rng."""
    rng = np.random.default_rng(compute_seed(NOISE_LABEL, 0, index))
    x = normalise_rms(rng.standard_normal(PCM_SAMPLES))
    return np.clip(np.round(x * 32768.0), -32768, 32767).astype("<i2")


def write_noise():
    os.makedirs(NOISE_DIR, exist_ok=True)
    manifest = {}
    for i, st in enumerate(noise_stamps()):
        pcm = render_noise_pcm(i)
        path = os.path.join(NOISE_DIR, st + ".wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE_HZ)
            w.writeframes(pcm.tobytes())
        ok, why = r0_ok(path)
        assert ok, (st, why)
        with open(path, "rb") as fh:
            manifest[st] = hashlib.sha256(fh.read()).hexdigest()
    return manifest


def build(noise_manifest):
    stamps = sorted(f[:-4] for f in os.listdir(WAV_DIR) if f.endswith(".wav"))
    bad_name = [s for s in stamps if not STAMP.match(s)]
    assert not bad_name, f"unexpected file names: {len(bad_name)}"
    assert len(stamps) >= 3, "too few cycles"
    first, last = stamps[0], stamps[-1]
    included, r0_failed = [], []
    for s in stamps[1:-1]:
        ok, why = r0_ok(os.path.join(WAV_DIR, s + ".wav"))
        (included if ok else r0_failed).append(s)
    assert included == sorted(included)
    sample_a = [s for i, s in enumerate(included) if i % SAMPLE_STEP == SAMPLE_OFFSET_A]
    sample_b = [s for i, s in enumerate(included) if i % SAMPLE_STEP == SAMPLE_OFFSET_B]
    aa = sample_a[:AA_CYCLES]
    assert len(aa) == AA_CYCLES, "fewer than 200 sampled cycles"
    ns = noise_stamps()
    assert len(ns) == NOISE_SCORED + 1 and set(ns) == set(noise_manifest)
    return {
        "spec": "qa/rr-study/2026-10-06-1430-architect-to-qa-spec-nhard-replication.md (branch arch/nhard-replication) section 4, 12",
        "run": RUN,
        "source_dir": f"artefacts/{RUN}_endurance_run-gathered/owsfz/wav",
        "counts": {
            "wav_files": len(stamps), "excluded_window_edge": 2, "excluded_r0_failed": len(r0_failed),
            "included_full_list": len(included), "sample": len(sample_a), "sample_b_reserve": len(sample_b),
            "aa": len(aa), "noise_scored": NOISE_SCORED,
        },
        "rule": {"sample": f"position i (0-based, in the included list) with i mod {SAMPLE_STEP} == {SAMPLE_OFFSET_A}",
                 "sample_b": f"i mod {SAMPLE_STEP} == {SAMPLE_OFFSET_B}", "aa": f"first {AA_CYCLES} of sample"},
        "excluded": {"window_edge": [first, last], "r0_failed": r0_failed},
        "runs": {
            RUN: {"warmup": first, "FULL": included, "SAMPLE": sample_a, "SAMPLE_B": sample_b, "AA": aa},
            "NOISE": {"warmup": ns[0], "ALL": ns[1:]},
        },
        "noise": {"label": NOISE_LABEL, "target_rms": NOISE_TARGET_RMS, "samples": PCM_SAMPLES,
                  "generator": "numpy default_rng(compute_seed(label, 0, index)).standard_normal, normalise_rms, int16 round+clip",
                  "numpy": np.__version__, "wav_sha256": noise_manifest},
    }


def serialise(sel):
    return (json.dumps(sel, indent=1, sort_keys=True) + "\n").encode("utf-8")


def main():
    man = write_noise()
    sel = build(man)
    data = serialise(sel)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SELECTION, "wb") as fh:
        fh.write(data)
    sha = hashlib.sha256(data).hexdigest()
    c = sel["counts"]
    print(f"wrote {SELECTION}")
    print(f"wav files {c['wav_files']}: edge excluded 2, R0 failed {c['excluded_r0_failed']}, full list {c['included_full_list']}, "
          f"sample {c['sample']}, sample_b {c['sample_b_reserve']}, aa {c['aa']}, noise {c['noise_scored']}")
    r = sel["runs"][RUN]
    print(f"sample first {r['SAMPLE'][0]} last {r['SAMPLE'][-1]}  warm-up {r['warmup']}")
    print(f"selection.json sha256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
