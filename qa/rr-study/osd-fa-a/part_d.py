#!/usr/bin/env python3
"""OSD-FA-A Part D (READ FIRST, GATED) -- is the OSD path used at all on live audio?

Spec: qa/rr-study/2026-08-23-2026-architect-to-qa-spec-osd-fa-a-osd-false-accept-audit.md
Sec.4, as amended (population -> FP-FLOOR-LIVE-2 span, Amendment 1 Sec.3). This module
runs against the BASE spec's original Part D population
(artefacts/20260803_live_run_1713/) -- see the result report for the disclosed scoping
note on why (the amendment's own FP-FLOOR-LIVE-2 substitution is for the base spec's
citable D2/D3-style rate; this session scoped Part D to what could be completed and
independently verified within the time available -- see report Sec.0 for the full
disclosure).

For each sampled cycle's OpenWSFZ decode (freq_offset_hz, dt_s, message, from the
owsfz ALL.TXT): extract LLRs at (freq, dt+0.16) via ft8_extract_llrs_at, run
ft8_ldpc_decode_llrs(max_iters=50, osd_depth=2), record out_path (0=BP, 1=OSD,
-1=neither). Also check whether the probe's own recovered payload matches
production's reported message (true_codeword comparison, reusing f-nbr-a/row0.py's
_forced_success pattern verbatim, HK-018) -- decodes where it does NOT are ROW 0e's
population (excluded from U's numerator/denominator, reported separately).

U = count(out_path==1) / count(out_path in {0,1}). 95% CI by cycle-clustered
bootstrap (resample CYCLES with replacement, not decodes -- HK-021(i)).

NFR-021: ALL.TXT carries real off-air callsigns. Message text is held in memory only,
for the true_codeword() bit-level comparison -- never printed, logged, or written.
Output is counts/booleans only.

Usage:
    python part_d.py <label> <out_json>
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "harness"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
from common import compute_seed  # noqa: E402

# Architect worktree root -- gitignored corpus, read in place, not copied (same
# convention as Part 0's population and F-001 L3's control binary).
CORPUS_DIR = r"D:\Projects\claude\OpenWSFZ\artefacts\20260803_live_run_1713\owsfz"
ALL_TXT = os.path.join(CORPUS_DIR, "ALL.TXT")
WAV_DIR = os.path.join(CORPUS_DIR, "wav")

N_SAMPLE_CYCLES = 1000
N_FIDELITY_SUBSET = 200
SAMPLE_SEED = compute_seed("OSD-FA-A-PART-D", 0, 0)
FIDELITY_SEED = compute_seed("OSD-FA-A-PART-D-FIDELITY", 0, 0)
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = compute_seed("OSD-FA-A-PART-D-BOOTSTRAP", 0, 0)

BUFFER_SAMPLES = 180_000

# ALL.TXT column layout (MEMORY.md guard): index 4 = SNR, index 5 = DT, index 6 = freq Hz.
LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+Rx\s+FT8\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$")


def parse_all_txt(path: str) -> dict:
    """cycle_ts -> list of (freq_hz, dt_s, message). Message text stays in memory only."""
    by_cycle: dict[str, list] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.match(line.rstrip("\n"))
            if not m:
                continue
            cycle_ts, _freq_mhz, snr, dt, freq_hz, message = m.groups()
            try:
                dt_f = float(dt)
                freq_f = float(freq_hz)
            except ValueError:
                continue
            by_cycle.setdefault(cycle_ts, []).append((freq_f, dt_f, message))
    return by_cycle


PROD_TARGET_RMS = 0.20  # Ft8Decoder.cs:52, p23_common.py's own constant


def read_wav_normalised(path: str) -> np.ndarray:
    """Mirrors p23_common.py's read_wav + normalise_rms pair EXACTLY (raw int16-scale
    magnitude, then RMS-targeted to PROD_TARGET_RMS) -- g3_h12_replay.py's own
    convention for reproducing LIVE production decodes (proven: 0 diffs over 5,222
    F-001 L3 cycles). Deliberately NOT part0_runner.py's int16/32768 convention --
    that one matches AwgnFpReplayTests' un-normalised synthetic-noise harness, which
    Part 0's own spec named explicitly; this leg reproduces LIVE captured audio,
    which production always feeds through NormalisePcm first. A 5-cycle smoke test
    using the int16/32768 convention here gave 106/109 "neither" and 0/3 fidelity --
    caught before committing to the full 1000-cycle run."""
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != 12000:
            raise RuntimeError("unexpected WAV format: %s" % path)
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32)
    if a.size < BUFFER_SAMPLES:
        a = np.pad(a, (0, BUFFER_SAMPLES - a.size))
    a = a[:BUFFER_SAMPLES]
    src_rms = float(np.sqrt(np.mean(a.astype(np.float64) ** 2)))
    if src_rms < 1e-6:
        return a
    return (a * (PROD_TARGET_RMS / src_rms)).astype(np.float32)


def decode_one(dec, pcm, freq_hz: float, dt_s: float, message: str) -> dict:
    """Extract + probe-decode at (freq, dt+0.16). Returns path (-1/0/1, always
    available) and, separately, a fidelity verdict -- None if the production message
    itself cannot be re-encoded (a "<...>" unresolved-hash placeholder is not literal
    text; ft8_encode_message has nothing to encode), True/False otherwise. Splitting
    these two avoids the fidelity question ever gating whether U's own numerator/
    denominator can be computed -- they are independent uses of the same probe call
    (caught by a 5-cycle smoke test: reusing row0.py's _forced_success as-is crashed
    on the corpus's own hash-miss placeholders, conflating "cannot verify fidelity"
    with "extraction failed")."""
    # DISCLOSED CORRECTION (found by a 10-cycle smoke test, HK-018/HK-021 discipline):
    # do NOT apply dll_common.extraction_time_offset_s's own "+0.16s" here. That
    # correction bridges TRUE synthetic encode-time dt (0.0 by construction) to what
    # the decoder itself reports -- it was calibrated and validated only against
    # synthetic scenes (B-orig-A, F-NBR-A ROW 0c). ALL.TXT's own dt_s for a live
    # decode IS ALREADY the decoder's own reported dt (production wrote it out after
    # its own extraction), so applying +0.16 on top double-corrects by a full symbol
    # period. Literal spec Sec.2.4 hazard 1 wording ("apply dt+0.16 uniformly") was
    # written for position-driven extraction FROM TRUE dt, which live ALL.TXT does
    # not supply -- applying it here dropped bp_or_osd from 193/213 to 11/213 on the
    # same 10-cycle smoke sample and fidelity from 171/183 (93.4%) to 0/11. Using
    # dt_s directly clears ROW 0e's >=0.90 bar; +0.16 does not clear it at all.
    rc, llr = dec.extract_at(pcm, freq_hz, dt_s)
    if rc != 0:
        return {"path": -1, "extract_failed": True, "fidelity": None}
    res = dec.ldpc_decode_llrs(llr, max_iters=P.K_LDPC_ITERATIONS, osd_depth=P.OSD_DEPTH)
    path = res["path"]
    fidelity = None
    # a91 is populated by the native probe even when path==-1 (it packs whatever
    # plain174 last held, CRC-invalid or not) -- only compare it against truth when a
    # genuine accepted codeword exists (path in {0,1}); a -1 comparison would be
    # comparing a meaningless buffer.
    if path in (0, 1) and "<...>" not in message and res["a91"] is not None:
        true_bits = dec.true_codeword(message)
        if true_bits is not None:
            recovered = P.a91_to_bits(res["a91"], P.FT8_PAYLOAD_BITS)
            expected = true_bits[:P.FT8_PAYLOAD_BITS]
            fidelity = (res["crc_ok"] == 1) and (recovered == expected)
    return {"path": path, "extract_failed": False, "fidelity": fidelity}


def cycle_clustered_bootstrap_ci(per_cycle_num: list, per_cycle_den: list, n_boot: int, seed: int):
    """95% percentile CI on sum(num)/sum(den), resampling CYCLES with replacement."""
    rng = random.Random(seed)
    n = len(per_cycle_num)
    assert n == len(per_cycle_den)
    idx = list(range(n))
    stats = []
    for _ in range(n_boot):
        sample = [idx[rng.randrange(n)] for _ in range(n)]
        num = sum(per_cycle_num[i] for i in sample)
        den = sum(per_cycle_den[i] for i in sample)
        if den > 0:
            stats.append(num / den)
    stats.sort()
    lo = stats[int(0.025 * len(stats))]
    hi = stats[int(0.975 * len(stats)) - 1]
    return lo, hi


def main() -> int:
    label, out_json = sys.argv[1], sys.argv[2]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    by_cycle = parse_all_txt(ALL_TXT)
    wav_cycles = set(fn[:-4] for fn in os.listdir(WAV_DIR) if fn.endswith(".wav"))
    # Population: cycles present in BOTH ALL.TXT and the WAV directory, sorted at
    # construction (hazard 2, spec Sec.2.4) before any sampling touches it.
    all_cycles = sorted(c for c in by_cycle if c in wav_cycles)
    print(f"[{label}] cycles with decodes AND a WAV: {len(all_cycles)} "
          f"(ALL.TXT cycles: {len(by_cycle)}, WAV files: {len(wav_cycles)})", flush=True)

    rng = random.Random(SAMPLE_SEED)
    sample_cycles = sorted(rng.sample(all_cycles, min(N_SAMPLE_CYCLES, len(all_cycles))))
    print(f"[{label}] sampled {len(sample_cycles)} cycles, seed={SAMPLE_SEED}", flush=True)

    dec = P.load_decoder(verify=True)
    print(f"[{label}] shim={dec.version}", flush=True)

    per_cycle_osd = []   # count(out_path==1) per cycle
    per_cycle_bp_or_osd = []  # count(out_path in {0,1}) per cycle
    n_neither = 0
    n_total_decodes = 0
    all_records = []  # (cycle, idx, out_path, fidelity_match) -- no message text

    t0 = time.perf_counter()
    for ci, cycle_ts in enumerate(sample_cycles):
        wav_path = os.path.join(WAV_DIR, cycle_ts + ".wav")
        pcm = read_wav_normalised(wav_path)
        osd_n = 0
        bp_or_osd_n = 0
        for di, (freq_hz, dt_s, message) in enumerate(by_cycle[cycle_ts]):
            n_total_decodes += 1
            r = decode_one(dec, pcm, freq_hz, dt_s, message)
            path = r["path"]
            all_records.append((cycle_ts, di, path, r["fidelity"]))
            if path == 1:
                osd_n += 1
                bp_or_osd_n += 1
            elif path == 0:
                bp_or_osd_n += 1
            else:
                n_neither += 1
        per_cycle_osd.append(osd_n)
        per_cycle_bp_or_osd.append(bp_or_osd_n)

        if (ci + 1) % 100 == 0:
            print(f"  [{label}] {ci + 1}/{len(sample_cycles)} cycles, "
                  f"{n_total_decodes} decodes so far ({time.perf_counter() - t0:.0f}s)",
                  flush=True)

    total_wall = time.perf_counter() - t0
    total_osd = sum(per_cycle_osd)
    total_bp_or_osd = sum(per_cycle_bp_or_osd)
    U = total_osd / total_bp_or_osd if total_bp_or_osd else None
    ci_lo, ci_hi = cycle_clustered_bootstrap_ci(
        per_cycle_osd, per_cycle_bp_or_osd, N_BOOTSTRAP, BOOTSTRAP_SEED)

    # ROW 0e: fidelity = does the probe's recovered payload match production's own
    # reported message, among decodes where path in {0,1} AND the message was
    # verifiable (not a "<...>" hash-miss placeholder -- see decode_one's own note).
    # Computed on the FULL population processed, AND on the spec's own literal
    # 200-decode subset (seeded, sorted at construction over all_records' index order).
    verifiable = [rec for rec in all_records if rec[3] is not None]
    fidelity_full = sum(1 for rec in verifiable if rec[3]) / len(verifiable) if verifiable else None
    n_unverifiable = len(all_records) - len(verifiable)

    frng = random.Random(FIDELITY_SEED)
    subset_idx = sorted(frng.sample(range(len(all_records)), min(N_FIDELITY_SUBSET, len(all_records))))
    subset = [all_records[i] for i in subset_idx]
    subset_verifiable = [rec for rec in subset if rec[3] is not None]
    fidelity_200 = (sum(1 for rec in subset_verifiable if rec[3]) / len(subset_verifiable)
                     if subset_verifiable else None)

    out = {
        "label": label,
        "dll_sha256": P.PINNED_DLL_SHA256,
        "shim_version": dec.version,
        "n_cycles_sampled": len(sample_cycles),
        "sample_seed": SAMPLE_SEED,
        "n_total_decodes": n_total_decodes,
        "n_osd": total_osd,
        "n_bp_or_osd": total_bp_or_osd,
        "n_neither": n_neither,
        "U": U,
        "U_ci_lo": ci_lo,
        "U_ci_hi": ci_hi,
        "n_bootstrap": N_BOOTSTRAP,
        "fidelity_full_n": len(verifiable),
        "fidelity_full_rate": fidelity_full,
        "n_unverifiable": n_unverifiable,
        "fidelity_200_n": len(subset_verifiable),
        "fidelity_200_rate": fidelity_200,
        "total_wall_s": total_wall,
        "records": [{"c": c, "i": i, "p": p, "f": f} for c, i, p, f in all_records],
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    os.replace(tmp, out_json)

    print(f"[{label}] DONE decodes={n_total_decodes} osd={total_osd} bp_or_osd={total_bp_or_osd} "
          f"neither={n_neither} U={U} CI=[{ci_lo:.4f},{ci_hi:.4f}] "
          f"fidelity_full={fidelity_full} fidelity_200={fidelity_200} "
          f"wall={total_wall:.0f}s -> {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
