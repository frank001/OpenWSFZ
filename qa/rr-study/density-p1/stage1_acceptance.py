#!/usr/bin/env python
"""DENSITY-P1 Stage 1 acceptance -- S1-a / S1-b / S1-c (S1-d is CI, not this script).

================================================================================
PRE-REGISTRATION -- written and committed BEFORE any run (HK-021: mechanical bars)
================================================================================
Build under test : Developer commit 3ad5504e (feat/density-p1-stage1-probe-tap), shim 20260053
                   NEW DLL SHA-256 50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7
                   OLD DLL SHA-256 91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6 (shim 20260051)
Both DLLs are extracted with `git show <ref>:<path>` and SHA-verified IN THE RUN (ROW 0a); the
working-tree DLL is never used. One PROCESS per (DLL, mode, leg) so module thread-locals and the
session-scoped callsign hash table (which persists across calls) start identical.

WHY THIS SET (the spec's "fixed replay set used for the last shim bump" does not exist offline --
the last bump's net was the live S1-S8 battery, so QA defines the set, here, before running):
  SYNTH : DENSITY-MECH's 12 cells (9 primary + 3 strong-victim) x 25 trials, E PRESENT, seeds =
          SR.trial_seed(t, part_index). = 300 calls. Crowded, the exact scene Stage 2 will use.
  REAL  : 200 live cycles from artefacts/20260908_live_run_1827-fp-floor-live-2/cycle-audio,
          sorted, every (len//200)-th. Dense real traffic => many pass-0 decodes => many suppression
          records and an active pass 1, which the synthetic scene cannot exercise.
Decode params set explicitly, identical for every run: k_min_score_pass2=10, osd_corr_threshold=0.10,
osd_nhard_max=40 (the LIVE app's, per spec 2.1), via ft8_set_decode_params.

WHAT IS COMPARED (canonical stream, one line per call, floats as IEEE-754 hex bits, never repr):
  rc, every FT8Result (freq_hz, dt bits, snr, message), pass_counts, candidate_counts, noise_floor,
  llr_stats (mean_abs, prenorm_var, fail_count per pass), snr_terms, hash_table_reject_count and the
  four h12 process-global counters.  Compared BYTE-FOR-BYTE (sha256 of the file + first differing line).

ARM POSITIONS (armed runs only; deterministic functions of the call index i):
  SYNTH: t even -> F's true position (target_freq, 0.16 s); t%10==1 -> OUT OF BAND (50.0 / 5000.0 Hz
         alternating); otherwise arbitrary in-band.   REAL: arbitrary in-band; every 20th out of band.

ROW 0 (any fires => STOP, report, NO re-cut)
  0a  both DLLs' SHA-256 AND ft8_lib_version_check match the pins above.
  0b  determinism: NEW disarmed run #1 == run #2 canonical stream, byte-identical, both legs.
  0c  non-vacuity: REAL leg, NEW disarmed: total decoded results >= 1000; NEW armed: >= 50% of cycles
      have n_supp >= 1 AND sum of pass_counts[1] >= 10 (pass 1 actually decodes something).
  0d  the instrument can say NO: NEW disarmed with k_min_score_pass2=30 (a real pass-1 behaviour
      change) on the REAL leg must produce a canonical stream that DIFFERS from NEW disarmed (>=1 line).
  0e  coverage: SYNTH has 300 calls; REAL has >= 190 calls (files of the wrong length are skipped and
      counted).
VERDICTS (mutually exclusive, predicates are the code below)
  S1-a  canon(OLD disarmed) == canon(NEW disarmed), byte-identical, BOTH legs.        else FAIL => reject build
  S1-b  canon(NEW armed)    == canon(NEW disarmed), byte-identical, BOTH legs.        else FAIL => reject build
  S1-c  for EVERY call: tap pass-0 status == ft8_extract_llrs_at status, and (status==0 => the 174 float
        bit patterns are equal); AND ft8_extract_llrs_at(NEW) == ft8_extract_llrs_at(OLD) bit-for-bit
        on every call (cross-binary).  SYNTH F's-true-position calls must ALL be status 0.  else FAIL.
  S1-e  (spec 1.1 contract, QA-checked) every recorded suppression factor equals 1-clamp((snr+5)/20,0,1)
        within 1e-6 and lies in [0,1]; n_supp == pass_counts[0] whenever pass_counts[0] < 140.
  Reporting only (gates nothing): fraction of SYNTH trials where the pass-1 tap differs from pass-0
  (placement evidence), n_supp distribution, snr_db range, count of records strictly inside the ramp.

NFR-021: REAL leg text contains real callsigns. Every output goes to a gitignored artefacts/ dir; the
script REFUSES to write unless `git check-ignore` confirms it. Only counts and hashes are reported.
"""
import argparse
import ctypes
import glob
import hashlib
import json
import os
import struct
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
QA_RR = os.path.join(REPO_ROOT, "qa", "rr-study")
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "density-p1-stage1-accept")
BIN_DIR = os.path.join(OUT_DIR, "bin")

NEW_REF = "feat/density-p1-stage1-probe-tap"
OLD_REF = "origin/decoding_improvement"
DLL_REL = "src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll"
PINS = {
    "OLD": ("91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6", 20260051),
    "NEW": ("50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7", 20260053),
}
CORPUS = os.path.join(REPO_ROOT, "artefacts", "20260908_live_run_1827-fp-floor-live-2", "cycle-audio")

N_SYNTH_TRIALS = 25
N_REAL = 200
N_SAMPLES = 180000
MAX_RESULTS = 200
K_MAX_CANDIDATES = 140            # ft8_shim.c:508
LIVE_PASS2, LIVE_OSD, LIVE_NHARD = 10, 0.10, 40
CTL_PASS2 = 30                    # ROW 0d control
RAMP_MIN_DB, RAMP_MAX_DB = -5.0, 15.0   # ft8_shim.c:537-538, written as literals on purpose
OOB_FREQS = (50.0, 5000.0)
N_LLR = 174


def log(m):
    print(m, flush=True)


def fbits(x):
    return struct.pack("<f", float(x)).hex()


# ── DLL wrapper ────────────────────────────────────────────────────────────────
class FT8Result(ctypes.Structure):
    _fields_ = [("freq_hz", ctypes.c_int), ("dt", ctypes.c_float),
                ("snr", ctypes.c_int), ("message", ctypes.c_char * 36)]


class SuppRec(ctypes.Structure):
    _fields_ = [("freq_offset", ctypes.c_int32), ("time_offset", ctypes.c_int32),
                ("freq_sub", ctypes.c_int32), ("time_sub", ctypes.c_int32),
                ("snr_db", ctypes.c_float), ("factor", ctypes.c_float)]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


class Shim:
    def __init__(self, path, which, has_probe):
        exp_sha, exp_ver = PINS[which]
        self.sha = sha256_file(path)
        if self.sha != exp_sha:
            raise RuntimeError("ROW 0a STOP: %s SHA %s != pin %s" % (which, self.sha, exp_sha))
        d = self.dll = ctypes.CDLL(path)
        d.ft8_lib_version_check.restype = ctypes.c_int
        self.version = d.ft8_lib_version_check()
        if self.version != exp_ver:
            raise RuntimeError("ROW 0a STOP: %s version %d != pin %d" % (which, self.version, exp_ver))
        P = ctypes.POINTER
        d.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
        d.ft8_set_decode_params.restype = None
        d.ft8_decode_all.argtypes = [P(ctypes.c_float), ctypes.c_int, P(FT8Result), ctypes.c_int]
        d.ft8_decode_all.restype = ctypes.c_int
        d.ft8_get_last_pass_counts.argtypes = [P(ctypes.c_int), ctypes.c_int]
        d.ft8_get_last_pass_counts.restype = ctypes.c_int
        d.ft8_get_last_candidate_counts.argtypes = [P(ctypes.c_int), ctypes.c_int]
        d.ft8_get_last_candidate_counts.restype = ctypes.c_int
        d.ft8_get_last_noise_floor_db.restype = ctypes.c_float
        d.ft8_get_last_llr_stats.argtypes = [P(ctypes.c_float), P(ctypes.c_float), P(ctypes.c_int), ctypes.c_int]
        d.ft8_get_last_llr_stats.restype = ctypes.c_int
        d.ft8_get_last_snr_terms.argtypes = [P(ctypes.c_float), P(ctypes.c_float), ctypes.c_int]
        d.ft8_get_last_snr_terms.restype = ctypes.c_int
        for n in ("ft8_get_hash_table_reject_count", "ft8_get_h12_displaying_count", "ft8_get_h12_ambiguous_count",
                  "ft8_get_h12_divergent_count", "ft8_get_h12_suppressed_count", "ft8_get_max_passes"):
            getattr(d, n).restype = ctypes.c_int
        d.ft8_extract_llrs_at.argtypes = [P(ctypes.c_float), ctypes.c_int, ctypes.c_float, ctypes.c_float, P(ctypes.c_float)]
        d.ft8_extract_llrs_at.restype = ctypes.c_int
        self.k_passes = d.ft8_get_max_passes()
        self.has_probe = has_probe
        if has_probe:
            d.ft8_set_probe.argtypes = [ctypes.c_float, ctypes.c_float]
            d.ft8_set_probe.restype = None
            d.ft8_clear_probe.restype = None
            d.ft8_get_probe_llrs.argtypes = [ctypes.c_int, P(ctypes.c_float)]
            d.ft8_get_probe_llrs.restype = ctypes.c_int
            d.ft8_get_last_suppression.argtypes = [P(SuppRec), ctypes.c_int]
            d.ft8_get_last_suppression.restype = ctypes.c_int

    def set_params(self, pass2):
        self.dll.ft8_set_decode_params(int(pass2), ctypes.c_float(LIVE_OSD), int(LIVE_NHARD))

    def decode_canonical(self, pcm, idx):
        """decode_all + every read-only diagnostic. Returns (rc, canonical_line, pass_counts)."""
        d = self.dll
        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        res = (FT8Result * MAX_RESULTS)()
        rc = d.ft8_decode_all(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), N_SAMPLES, res, MAX_RESULTS)
        parts = ["i=%d" % idx, "rc=%d" % rc]
        rows = []
        for k in range(max(rc, 0)):
            r = res[k]
            rows.append("%d,%s,%d,%s" % (r.freq_hz, fbits(r.dt), r.snr, r.message.decode("latin-1")))
        parts.append("res=[" + ";".join(rows) + "]")
        K = self.k_passes
        pc = (ctypes.c_int * 8)()
        n = d.ft8_get_last_pass_counts(pc, 8)
        pcl = [pc[k] for k in range(max(0, min(n, 8)))]
        parts.append("pc=%d:%s" % (n, ",".join(map(str, pcl))))
        cc = (ctypes.c_int * 8)()
        n = d.ft8_get_last_candidate_counts(cc, 8)
        parts.append("cc=%d:%s" % (n, ",".join(str(cc[k]) for k in range(max(0, min(n, 8))))))
        parts.append("nf=%s" % fbits(d.ft8_get_last_noise_floor_db()))
        ma = (ctypes.c_float * K)(); pv = (ctypes.c_float * K)(); fc = (ctypes.c_int * K)()
        n = d.ft8_get_last_llr_stats(ma, pv, fc, K)
        parts.append("llr=%d:%s" % (n, ";".join("%s,%s,%d" % (fbits(ma[k]), fbits(pv[k]), fc[k]) for k in range(K))))
        sg = (ctypes.c_float * MAX_RESULTS)(); nz = (ctypes.c_float * MAX_RESULTS)()
        n = d.ft8_get_last_snr_terms(sg, nz, MAX_RESULTS)
        parts.append("snr=%d:%s" % (n, ";".join("%s,%s" % (fbits(sg[k]), fbits(nz[k])) for k in range(max(0, min(n, MAX_RESULTS))))))
        parts.append("h=%d,%d,%d,%d,%d" % (d.ft8_get_hash_table_reject_count(), d.ft8_get_h12_displaying_count(),
                                          d.ft8_get_h12_ambiguous_count(), d.ft8_get_h12_divergent_count(),
                                          d.ft8_get_h12_suppressed_count()))
        return rc, "|".join(parts), pcl

    def extract_at(self, pcm, f, t):
        buf = np.ascontiguousarray(pcm, dtype=np.float32)
        out = (ctypes.c_float * N_LLR)()
        rc = self.dll.ft8_extract_llrs_at(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), N_SAMPLES,
                                          ctypes.c_float(f), ctypes.c_float(t), out)
        return rc, (bytes(out) if rc == 0 else b"")


# ── legs ───────────────────────────────────────────────────────────────────────
def synth_calls():
    """Yields (idx, pcm, arm_pos, is_true_pos_call, cell_key). Rendering is deterministic."""
    for d in (os.path.join(QA_RR, "density-mech"), QA_RR, os.path.join(QA_RR, "f-nbr-a"),
              os.path.join(QA_RR, "n1-extract-llrs-at-position"), os.path.join(QA_RR, "r2-coherent-llr-instrument")):
        if d not in sys.path:
            sys.path.insert(0, d)
    import density_mech as DM
    SR = DM.SR
    i = 0
    for cell in DM.build_cells():
        full, _abl, target = DM.cell_signals(cell)
        key = "%s,%.2f,%.1f" % (cell["group"], cell["delta_hz"], cell["x_db"])
        for t in range(N_SYNTH_TRIALS):
            pcm = SR.render_scene(full, SR.trial_seed(t, cell["part_index"]))
            if t % 2 == 0:
                pos, true_pos = (float(target), float(DM.F_TIME_OFFSET_S)), True
            elif t % 10 == 1:
                pos, true_pos = (OOB_FREQS[(t // 10) % 2], 0.16), False
            else:
                pos, true_pos = (200.0 + ((i * 97) % 2700) + 0.25 * (i % 5), -0.4 + ((i * 31) % 18) * 0.1), False
            yield i, pcm, pos, true_pos, key
            i += 1


def real_calls():
    files = sorted(glob.glob(os.path.join(CORPUS, "*.wav")))
    step = max(1, len(files) // N_REAL)
    chosen = files[::step][:N_REAL]
    i = 0
    skipped = 0
    for f in chosen:
        with wave.open(f) as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) != (1, 2, 12000, N_SAMPLES):
                skipped += 1
                continue
            raw = w.readframes(N_SAMPLES)
        pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if i % 20 == 19:
            pos = (OOB_FREQS[(i // 20) % 2], 0.16)
        else:
            pos = (200.0 + ((i * 137.31) % 2700.0), -0.3 + ((i * 0.37) % 1.8))
        yield i, pcm, pos, False, "real"
        i += 1
    real_calls.skipped = skipped


def formula(snr):
    return 1.0 - max(0.0, min(1.0, (snr - RAMP_MIN_DB) / (RAMP_MAX_DB - RAMP_MIN_DB)))


def ensure_ignored(path):
    r = subprocess.run(["git", "-C", REPO_ROOT, "check-ignore", "-q", path])
    if r.returncode != 0:
        raise RuntimeError("NFR-021 REFUSE: %s is not gitignored" % path)
    t = subprocess.run(["git", "-C", REPO_ROOT, "ls-files", "--error-unmatch", path], capture_output=True)
    if t.returncode == 0:
        raise RuntimeError("NFR-021 REFUSE: %s is tracked" % path)


# ── subcommands ────────────────────────────────────────────────────────────────
def cmd_extract(a):
    os.makedirs(BIN_DIR, exist_ok=True)
    for tag, ref in (("OLD", OLD_REF), ("NEW", NEW_REF)):
        blob = subprocess.run(["git", "-C", REPO_ROOT, "show", "%s:%s" % (ref, DLL_REL)], capture_output=True, check=True).stdout
        p = os.path.join(BIN_DIR, "libft8_%s.dll" % tag)
        with open(p, "wb") as f:
            f.write(blob)
        got = hashlib.sha256(blob).hexdigest()
        log("%s  %s  %s  %s" % (tag, ref, got, "PIN OK" if got == PINS[tag][0] else "PIN MISMATCH"))
        if got != PINS[tag][0]:
            sys.exit(2)


def cmd_run(a):
    os.makedirs(OUT_DIR, exist_ok=True)
    stem = os.path.join(OUT_DIR, "%s_%s" % (a.tag, a.leg))
    for ext in (".canon", ".ext", ".tap", ".json"):
        ensure_ignored(stem + ext)
    which = "OLD" if a.dll == "OLD" else "NEW"
    sh = Shim(os.path.join(BIN_DIR, "libft8_%s.dll" % which), which, has_probe=(which == "NEW"))
    if a.armed and not sh.has_probe:
        raise RuntimeError("armed run needs the NEW DLL")
    sh.set_params(a.pass2)
    gen = synth_calls() if a.leg == "synth" else real_calls()
    canon = open(stem + ".canon", "w", newline="\n")
    extf = open(stem + ".ext", "w", newline="\n")
    tapf = open(stem + ".tap", "w", newline="\n") if a.armed else None
    S = {"tag": a.tag, "dll": which, "sha": sh.sha, "version": sh.version, "armed": a.armed, "leg": a.leg,
         "pass2": a.pass2, "calls": 0, "results_total": 0, "pass1_decodes": 0, "n_supp_ge1": 0,
         "supp_records": 0, "supp_formula_violations": 0, "supp_out_of_range": 0, "supp_in_ramp": 0,
         "n_supp_vs_pc0_violations": 0, "snr_min": None, "snr_max": None,
         "p0_ext_mismatch": 0, "p0_true_pos_nonzero": 0, "p1_differs_from_p0": 0, "p1_compared": 0,
         "true_pos_calls": 0, "bad_rc": 0}
    for idx, pcm, (pf, pt), true_pos, key in gen:
        if a.armed:
            sh.dll.ft8_set_probe(ctypes.c_float(pf), ctypes.c_float(pt))
        rc, line, pcl = sh.decode_canonical(pcm, idx)
        canon.write(line + "\n")
        S["calls"] += 1
        S["results_total"] += max(rc, 0)
        S["bad_rc"] += 1 if rc < 0 else 0
        if len(pcl) > 1:
            S["pass1_decodes"] += pcl[1]
        tap_bits = {}
        if a.armed:
            t_rc = {}
            for p in (0, 1):
                out = (ctypes.c_float * N_LLR)()
                t_rc[p] = sh.dll.ft8_get_probe_llrs(p, out)
                tap_bits[p] = bytes(out) if t_rc[p] == 0 else b""
            recs = (SuppRec * K_MAX_CANDIDATES)()
            n_supp = sh.dll.ft8_get_last_suppression(recs, K_MAX_CANDIDATES)
            dig = hashlib.sha256()
            for k in range(min(n_supp, K_MAX_CANDIDATES)):
                r = recs[k]
                dig.update(struct.pack("<iiiiff", r.freq_offset, r.time_offset, r.freq_sub, r.time_sub, r.snr_db, r.factor))
                S["supp_records"] += 1
                if not (0.0 <= r.factor <= 1.0):
                    S["supp_out_of_range"] += 1
                if abs(r.factor - formula(r.snr_db)) > 1e-6:
                    S["supp_formula_violations"] += 1
                if RAMP_MIN_DB < r.snr_db < RAMP_MAX_DB:
                    S["supp_in_ramp"] += 1
                S["snr_min"] = r.snr_db if S["snr_min"] is None else min(S["snr_min"], r.snr_db)
                S["snr_max"] = r.snr_db if S["snr_max"] is None else max(S["snr_max"], r.snr_db)
            if n_supp >= 1:
                S["n_supp_ge1"] += 1
            if pcl and pcl[0] < K_MAX_CANDIDATES and n_supp != pcl[0]:
                S["n_supp_vs_pc0_violations"] += 1
        e_rc, e_bits = sh.extract_at(pcm, pf, pt)
        extf.write("%d|%d|%s\n" % (idx, e_rc, hashlib.sha256(e_bits).hexdigest() if e_rc == 0 else "-"))
        if a.armed:
            eq = (t_rc[0] == e_rc) and (e_rc != 0 or tap_bits[0] == e_bits)
            if not eq:
                S["p0_ext_mismatch"] += 1
            if true_pos:
                S["true_pos_calls"] += 1
                if t_rc[0] != 0:
                    S["p0_true_pos_nonzero"] += 1
            if t_rc[0] == 0 and t_rc[1] == 0:
                S["p1_compared"] += 1
                if tap_bits[1] != tap_bits[0]:
                    S["p1_differs_from_p0"] += 1
            tapf.write("%d|%d|%d|%s|%s|%d|%s|%s\n" % (
                idx, t_rc[0], t_rc[1],
                hashlib.sha256(tap_bits[0]).hexdigest() if t_rc[0] == 0 else "-",
                hashlib.sha256(tap_bits[1]).hexdigest() if t_rc[1] == 0 else "-",
                n_supp, dig.hexdigest(), "eq" if eq else "NE"))
        if S["calls"] % 50 == 0:
            log("%s: %d calls" % (a.tag + "_" + a.leg, S["calls"]))
    canon.close(); extf.close()
    if tapf:
        tapf.close()
    S["real_skipped"] = getattr(real_calls, "skipped", 0) if a.leg == "real" else 0
    with open(stem + ".json", "w") as f:
        json.dump(S, f, indent=1)
    log("DONE %s_%s: %d calls" % (a.tag, a.leg, S["calls"]))


def first_diff(p, q):
    with open(p, "rb") as f, open(q, "rb") as g:
        A, B = f.read().split(b"\n"), g.read().split(b"\n")
    for i in range(max(len(A), len(B))):
        a = A[i] if i < len(A) else b"<EOF>"
        b = B[i] if i < len(B) else b"<EOF>"
        if a != b:
            return i
    return None


def same(tag_a, tag_b, leg, ext=".canon"):
    p, q = (os.path.join(OUT_DIR, "%s_%s%s" % (t, leg, ext)) for t in (tag_a, tag_b))
    ha, hb = sha256_file(p), sha256_file(q)
    return ha == hb, ha[:16], hb[:16], (None if ha == hb else first_diff(p, q))


def load(tag, leg):
    with open(os.path.join(OUT_DIR, "%s_%s.json" % (tag, leg))) as f:
        return json.load(f)


def cmd_verdict(a):
    R = {}
    for leg in ("synth", "real"):
        for tag in ("old_dis", "new_dis", "new_dis2", "new_arm"):
            if not os.path.exists(os.path.join(OUT_DIR, "%s_%s.json" % (tag, leg))):
                log("MISSING %s_%s -- cannot verdict" % (tag, leg)); sys.exit(3)
    if not os.path.exists(os.path.join(OUT_DIR, "ctl_pass2_real.json")):
        log("MISSING ctl_pass2_real"); sys.exit(3)
    rs, rr = load("new_dis", "synth"), load("new_dis", "real")
    ns, nr = load("new_arm", "synth"), load("new_arm", "real")
    row0 = {}
    row0["0a"] = all(load(t, l)["sha"] == PINS[w][0] and load(t, l)["version"] == PINS[w][1]
                     for t, w in (("old_dis", "OLD"), ("new_dis", "NEW"), ("new_arm", "NEW"))
                     for l in ("synth", "real"))
    row0["0b"] = all(same("new_dis", "new_dis2", l)[0] for l in ("synth", "real"))
    row0["0c"] = (rr["results_total"] >= 1000 and nr["n_supp_ge1"] >= 0.5 * nr["calls"] and nr["pass1_decodes"] >= 10)
    row0["0d"] = not same("new_dis", "ctl_pass2", "real")[0]
    row0["0e"] = (rs["calls"] == 300 and rr["calls"] >= 190 and ns["calls"] == 300 and nr["calls"] >= 190)
    R["row0"] = row0
    R["row0_detail"] = {"real_results_total": rr["results_total"], "real_calls": rr["calls"],
                        "real_skipped": rr["real_skipped"], "armed_real_n_supp_ge1": nr["n_supp_ge1"],
                        "armed_real_pass1_decodes": nr["pass1_decodes"], "synth_calls": rs["calls"],
                        "control_differs_first_line": same("new_dis", "ctl_pass2", "real")[3]}
    if not all(row0.values()):
        R["verdict"] = "ROW 0 STOP: " + ",".join(k for k, v in row0.items() if not v)
        print(json.dumps(R, indent=1)); return
    s1a = {l: same("old_dis", "new_dis", l) for l in ("synth", "real")}
    s1b = {l: same("new_arm", "new_dis", l) for l in ("synth", "real")}
    ext_x = {l: same("old_dis", "new_dis", l, ".ext") for l in ("synth", "real")}
    R["S1-a"] = {"pass": all(v[0] for v in s1a.values()), "detail": s1a}
    R["S1-b"] = {"pass": all(v[0] for v in s1b.values()), "detail": s1b}
    tapok = all(S["p0_ext_mismatch"] == 0 for S in (ns, nr)) and ns["p0_true_pos_nonzero"] == 0 and ns["true_pos_calls"] > 0
    R["S1-c"] = {"pass": bool(tapok and all(v[0] for v in ext_x.values())),
                 "tap_eq_ext_mismatches": {"synth": ns["p0_ext_mismatch"], "real": nr["p0_ext_mismatch"]},
                 "synth_true_pos_calls": ns["true_pos_calls"], "synth_true_pos_nonzero": ns["p0_true_pos_nonzero"],
                 "ext_old_vs_new_identical": {l: v[0] for l, v in ext_x.items()}}
    R["S1-e"] = {"pass": all(S["supp_formula_violations"] == 0 and S["supp_out_of_range"] == 0
                            and S["n_supp_vs_pc0_violations"] == 0 for S in (ns, nr)),
                 "records": {"synth": ns["supp_records"], "real": nr["supp_records"]},
                 "in_ramp": {"synth": ns["supp_in_ramp"], "real": nr["supp_in_ramp"]},
                 "snr_range": {"synth": [ns["snr_min"], ns["snr_max"]], "real": [nr["snr_min"], nr["snr_max"]]},
                 "formula_violations": {"synth": ns["supp_formula_violations"], "real": nr["supp_formula_violations"]},
                 "n_supp_vs_pc0_violations": {"synth": ns["n_supp_vs_pc0_violations"], "real": nr["n_supp_vs_pc0_violations"]}}
    R["reporting"] = {"synth_p1_differs_from_p0": "%d/%d" % (ns["p1_differs_from_p0"], ns["p1_compared"]),
                      "real_p1_differs_from_p0": "%d/%d" % (nr["p1_differs_from_p0"], nr["p1_compared"])}
    R["verdict"] = "S1-a/b/c/e ALL PASS" if all(R[k]["pass"] for k in ("S1-a", "S1-b", "S1-c", "S1-e")) else \
        "FAIL: " + ",".join(k for k in ("S1-a", "S1-b", "S1-c", "S1-e") if not R[k]["pass"])
    out = os.path.join(OUT_DIR, "verdict.json")
    ensure_ignored(out)
    with open(out, "w") as f:
        json.dump(R, f, indent=1)
    print(json.dumps(R, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extract").set_defaults(fn=cmd_extract)
    r = sub.add_parser("run")
    r.add_argument("--dll", choices=["OLD", "NEW"], required=True)
    r.add_argument("--tag", required=True)
    r.add_argument("--leg", choices=["synth", "real"], required=True)
    r.add_argument("--armed", action="store_true")
    r.add_argument("--pass2", type=int, default=LIVE_PASS2)
    r.set_defaults(fn=cmd_run)
    sub.add_parser("verdict").set_defaults(fn=cmd_verdict)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
