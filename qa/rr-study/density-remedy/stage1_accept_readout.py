#!/usr/bin/env python
"""DENSITY-REMEDY Stage 1 acceptance -- change `decoder-param-readout`, shim 20260054.
Gates S1-a, S1-b, S1-c, S1-d, S1-f(i), S1-f(ii, mechanical part), S1-g.  (S1-e = CI, S1-h = Playwright: not this script.)

================================================================================
PRE-REGISTRATION -- written and committed BEFORE any verdict run (HK-021: mechanical bars)
================================================================================
Build under test : Developer commit 257070d8707e4aa4e3a95362b5b8a674d862262a  (feat/decoder-param-readout), UNPUSHED
                   NEW DLL SHA-256 38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba, shim 20260054
                   OLD DLL SHA-256 50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7, shim 20260053
                   (= origin/decoding_improvement 6cb98c52d7f0c8b150e32c254f9740a97c909d00)
Both DLLs are extracted with `git show <COMMIT>:<path>` (commit SHAs, never branch names) and SHA-verified IN THE RUN
(ROW 0a). The working-tree DLL is never used.  One PROCESS per (DLL, tag, leg) so module thread-locals and the
session-scoped callsign hash table (which persists across calls) start identical.
Test filter: NONE. This is a Python/ctypes harness, not `dotnet test`; nothing can be filtered out silently (HK-022).
Instrument: the DENSITY-P1 Stage 1 instrument that QA already accepted (density-p1/stage1_acceptance.py), RE-PINNED here
by rebinding its PINS/OUT_DIR/refs; its decode_canonical / extract_at / calls generators are reused verbatim.

--------------------------------------------------------------------------------------------------------------------
S1-a  REGRESSION.  Replay set = DENSITY-P1 Stage 1's, unchanged: SYNTH 300 calls (DENSITY-MECH 12 cells x 25 trials, E present)
      + REAL 200 live cycles (artefacts/20260908_live_run_1827-fp-floor-live-2/cycle-audio, sorted, every 27th).
      Decode params set explicitly: (k_min_score_pass2, osd_corr_threshold, osd_nhard_max) = (10, 0.10, 40) = the LIVE app's.
      Canonical stream per call = rc, every FT8Result (dt as IEEE-754 bits), pass_counts, candidate_counts, noise_floor,
      llr_stats, snr_terms, hash/h12 counters; plus ft8_extract_llrs_at's 174 float bits at the call's arm position.
      Compared BYTE-FOR-BYTE (sha256 of the file; first differing line reported).
   S1-a.1  canon(OLD @ nh40) == canon(NEW @ nh40), BOTH legs.
   S1-a.2  ext(OLD @ nh40)   == ext(NEW @ nh40),   BOTH legs   (ft8_extract_llrs_at: reaches the SECOND passband site).
   S1-a.3  canon(OLD @ nh60) == canon(NEW @ nh60), BOTH legs   (the shim's own compiled default nhard, params otherwise as above).
   S1-a.4  canon(OLD @ nh40) == canon(NEW @ nh40 with ft8_set_supp_params(-5, 15, 1.0) called EXPLICITLY), BOTH legs.
   S1-a PASS <=> S1-a.1 .. S1-a.4 all hold.  Any FAIL => reject the build.
   ROW 0 (any fires => STOP, report, NO re-cut of the set or the bars)
     0a  both DLLs' SHA-256 AND ft8_lib_version_check match the pins; every run's JSON records them.
     0b  determinism: NEW nh40 run #1 == run #2, byte-identical, both legs.
     0c  non-vacuity: REAL, NEW nh40: total decoded results >= 1000; NEW ARMED REAL: >= 50 % of cycles have >= 1 suppression
         record AND sum(pass_counts[1]) >= 10 (pass 1 actually decodes).  So the regressed code (suppress_candidate_tiles,
         the ramp, the footprint loop) is executed with output that depends on it.
     0d  the instrument can say NO (a): NEW nh40 with k_min_score_pass2 = 30 (a real pass-1 change), REAL: stream DIFFERS.
     0d2 the instrument can say NO (b) -- sensitivity to the REGRESSED REGION ITSELF, HK-022 "what could this NOT have detected":
         NEW nh40 with ft8_set_supp_params(-5, 15, 0.0) on REAL: stream DIFFERS from NEW default; AND
         NEW nh40 with ft8_set_supp_params(-25, 15, 1.0) on REAL: stream DIFFERS from NEW default.
         (If the replay set could not tell a changed side weight / a changed floor from the default, S1-a would be decorative.)
     0e  coverage: SYNTH 300 calls in every run; REAL >= 190 in every run.

S1-b  SET/GET (unit, fresh process).
      Valid triples read back with EXACT float32 bit equality: (-25,15,1), (-10,15,0.5), (-5,1000,0), (0,0.5,1),
        (-5, 3.0e38, 0.5) [no upper bound on snr_max beyond > snr_min and finite].  Each returns 0.
      Invalid: with the prior triple set to (-10, 20, 0.5), EVERY one of the following returns -1 AND get returns the SAME
      triple bit-for-bit afterwards:
        class 1 non-finite: NaN or +/-Inf in each of the three argument positions (others valid)   [9 calls]
        class 2 snr_min >= snr_max: min == max ; min > max ; (-5,-5,.) ; (15,-5,.)                     [4 calls]
        class 3 side_weight < 0: -0.001, -1.0                                                          [2 calls]
        class 4 side_weight > 1: 1.0001, 2.0                                                           [2 calls]
      get(NULL) returns -1.  Fresh-process defaults read (-5, 15, 1) exactly.
      S1-b PASS <=> all of the above.

S1-c  FLOOR PLUMBED.  DENSITY-P1 primary cell delta 12 Hz, X = +3 dB, E at -5 dB (exactly one such cell in build_cells()),
      N = 20 trials t = 0..19, seeds SR.trial_seed(t, part_index), armed at F's true position, live params.
      Runs: `default` (setter never called) and `floor` (ft8_set_supp_params(-25, 15, 1)).
      Q = trials where E's suppression record exists in BOTH runs.  ROW 0: |Q| >= 15 and E's snr_db is bit-identical between
      the two runs for every t in Q (pass 0 cannot depend on the ramp).
      S1-c PASS <=> for EVERY t in Q: |factor_floor - (1 - clamp((snr_db + 25)/40, 0, 1))| <= 1e-6, AND for every t in Q
      with snr_db in (-24, 14): |factor_floor - factor_default| > 1e-3, AND that inner set has >= 15 trials.

S1-d  SIDE WEIGHT PLUMBED.  DENSITY-P1's E +15 dB, F +12 dB, delta 6.25 Hz cell (group "e15"), N = 20, armed at F's position.
      Runs: `default` (never called), `explicit` (-5, 15, 1.0), `side0` (-5, 15, 0.0).
      ROW 0: E's suppression record exists in >= 15/20 default trials with median factor <= 0.05 (E is really suppressed).
      (i)  F's pass-1 probe LLR vector differs BITWISE between `explicit` (s = 1) and `side0` (s = 0) in >= 19/20 trials
           (probe status 0 in both).
      (ii) NULL: `explicit` is bit-identical to `default` in 20/20 trials: canonical decode line, P0 bits, P1 bits, and the
           whole suppression-record list.
      (iii) QA-ADDED, STRICTER ONLY: P0 (pass 0, before any suppression) is bit-identical between `explicit` and `side0` in
           20/20 -- the setter must not reach pass 0.  Disclosed here, not in the dev-task.
      S1-d PASS <=> (i) and (ii) and (iii).

S1-f(i) COMPLETENESS, #define side (unit).  Source read from git at the pinned commit.
      (1) every `#define K_[A-Z0-9_]+` in ft8_shim.c, plus FT8_AP_LLR_HARD and HASH_TABLE_SIZE, and decode.c's OSD_DEPTH,
          OSD_SEARCH_K_MAX, LLR_NORM_TARGET_VARIANCE, CAND_TIME_OFFSET_MIN, CAND_TIME_OFFSET_END, is a table name; the table
          value equals the #define EVALUATED FROM SOURCE TEXT (float32-widened for float macros).
      (2) every `ft8_set_*` function defined in ft8_shim.c is either mapped (its parameters are runtime table rows) or on the
          NON-PARAMETER list {ft8_set_ap_bits, ft8_set_probe}; an unmapped setter FAILS.
      (3) the table has exactly 30 rows: 6 runtime + 24 compile-time (inherited count, asserted -- the Developer's stated figure).
S1-f(ii) COMPLETENESS, bare-literal side -- MECHANICAL PART ONLY (unit).  QA's own unfiltered lister (qa/rr-study/density-remedy/qalit.py,
      committed alongside; it filters NOTHING, 0 and 1 included) is independent of the Developer's litscan.py; this script embeds only
      the comment-stripper `strip_c` and the file:line claim checks.  Mechanical checks: every file:line the page's "Not included" list
      cites, at the pinned commit, actually contains the literal it claims; no `3.125` literal exists in any
      of the four files (the "derived: none" claim).  🔴 WHETHER A LITERAL IS A *TUNING* LITERAL IS NOT DECIDED HERE: QA-flagged
      lines the page does not cite are LISTED (not adjudicated) and go to the Architect.
S1-g  ROUND-TRIP (unit, fresh process).
      Sizing call ft8_get_decoder_params(NULL, 0) == total; a small capacity writes exactly that many entries, returns the total,
      and leaves a 0xEE canary beyond it untouched; capacity 0 / -1 with a non-NULL buffer writes nothing.  Names unique, NUL
      terminated, kind in {0,1}, reserved == 0.  Fresh process: every row value == default_value.
      After ft8_set_decode_params(7, 0.15, 50) and ft8_set_supp_params(-10, 15, 0.5) the six runtime rows report EXACTLY
      (7, float32(0.15), 50, -10, 15, 0.5), default_value unchanged, all 24 compile-time rows unchanged; after
      ft8_set_decode_params(10, 0.10, 60) and ft8_set_supp_params(-5, 15, 1) the runtime rows equal their defaults again.
      Reading the table does not change decode output: ONE fixed REAL cycle (the median-index file of the sorted corpus) decoded 3x in
      each of TWO FRESH PROCESSES, [decode]x3 vs ([decode, table-read x3])x3 -> the three canonical-line sha256 prefixes equal pairwise
      (paired processes because the canonical line carries cumulative process-global counters).

REPORTING ONLY (gates nothing): fraction of calls differing under the 0d2 controls; SYNTH/REAL result totals; supp-record counts.

WHAT THIS CANNOT SEE (stated in advance): Windows DLL only (Linux/macOS = S1-e CI); one thread; the 140-record cap (busiest cycle
27 pass-0 decodes, inherited from Stage 1); a replay set is evidence, not proof; the table's TRUTHFULNESS for a value the decode
path reads but that the table names by a *mirror* (decode.c's five `ftx_tune_*` consts) is checked by value here, not by
construction; managed-side (C#) behaviour is the Developer's tests + S1-h.

NFR-021: REAL leg text holds real callsigns.  Every output goes to gitignored artefacts/, and the script REFUSES to write unless
`git check-ignore` confirms it and `git ls-files` shows it untracked.  Only counts and hashes are reported.
"""
import argparse
import ctypes
import json
import math
import os
import re
import struct
import subprocess
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
QA_RR = os.path.join(REPO_ROOT, "qa", "rr-study")
for _p in (os.path.join(QA_RR, "density-p1"), os.path.join(QA_RR, "density-mech"), QA_RR, os.path.join(QA_RR, "f-nbr-a"),
           os.path.join(QA_RR, "n1-extract-llrs-at-position"), os.path.join(QA_RR, "r2-coherent-llr-instrument")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage1_acceptance as S1  # noqa: E402  (the accepted DENSITY-P1 Stage 1 instrument)
import density_mech as DM  # noqa: E402
import density_p1 as DP  # noqa: E402

SR = DM.SR

OLD_COMMIT = "6cb98c52d7f0c8b150e32c254f9740a97c909d00"
NEW_COMMIT = "257070d8707e4aa4e3a95362b5b8a674d862262a"
OLD_SHA, OLD_VER = "50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7", 20260053
NEW_SHA, NEW_VER = "38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba", 20260054
OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "density-remedy-stage1-accept")
BIN_DIR = os.path.join(OUT_DIR, "bin")

# Re-pin the accepted instrument. (S1.Shim / S1.cmd_run / S1.same read these module globals at call time.)
S1.PINS = {"OLD": (OLD_SHA, OLD_VER), "NEW": (NEW_SHA, NEW_VER)}
S1.OUT_DIR, S1.BIN_DIR = OUT_DIR, BIN_DIR
S1.OLD_REF, S1.NEW_REF = OLD_COMMIT, NEW_COMMIT

CFG = {"supp": None}
_ORIG_SET_PARAMS = S1.Shim.set_params


def _set_params_with_supp(self, pass2):
    _ORIG_SET_PARAMS(self, pass2)
    if CFG["supp"] is not None:
        f = self.dll.ft8_set_supp_params
        f.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
        f.restype = ctypes.c_int
        rc = f(*[ctypes.c_float(x) for x in CFG["supp"]])
        if rc != 0:
            raise RuntimeError("ft8_set_supp_params%r returned %d" % (CFG["supp"], rc))


S1.Shim.set_params = _set_params_with_supp

SHIM_C = "src/OpenWSFZ.Ft8/Native/ft8_shim.c"
DECODE_C = "native/ft8_lib_build/patched/ft8/decode.c"
MONITOR_C = "native/ft8_lib_build/patched/common/monitor.c"
LDPC_C = "native/ft8_lib_vendor/ft8/ldpc.c"
PAGE = "web/decoder-params.html"

# Inherited constants, asserted in code (the Developer's stated table shape).
RUNTIME_NAMES = ["k_min_score_pass2", "osd_corr_threshold", "osd_nhard_max",
                 "supp_snr_min_db", "supp_snr_max_db", "supp_side_weight"]
N_ROWS_TOTAL, N_ROWS_RUNTIME, N_ROWS_COMPILE = 30, 6, 24
KIND_COMPILE, KIND_RUNTIME = 0, 1
DEF_SUPP = (-5.0, 15.0, 1.0)
PLUMB_N = 20
FACTOR_TOL = 1e-6


def log(m):
    print(m, flush=True)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def fbits(x):
    return struct.pack("<f", float(x)).hex()


def git_show(commit, path):
    return subprocess.run(["git", "-C", REPO_ROOT, "show", "%s:%s" % (commit, path)], capture_output=True, check=True).stdout.decode("utf-8", "replace")


# ── native table wrapper ───────────────────────────────────────────────────────
class Entry(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char * 48), ("value", ctypes.c_double), ("default_value", ctypes.c_double),
                ("kind", ctypes.c_int32), ("reserved", ctypes.c_int32)]


assert ctypes.sizeof(Entry) == 72


def load_new_dll():
    path = os.path.join(BIN_DIR, "libft8_NEW.dll")
    sha = S1.sha256_file(path)
    if sha != NEW_SHA:
        raise RuntimeError("ROW 0a STOP: NEW SHA %s != pin" % sha)
    d = ctypes.CDLL(path)
    d.ft8_lib_version_check.restype = ctypes.c_int
    if d.ft8_lib_version_check() != NEW_VER:
        raise RuntimeError("ROW 0a STOP: NEW version != pin")
    P = ctypes.POINTER
    d.ft8_get_decoder_params.argtypes = [P(Entry), ctypes.c_int]
    d.ft8_get_decoder_params.restype = ctypes.c_int
    d.ft8_set_supp_params.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
    d.ft8_set_supp_params.restype = ctypes.c_int
    d.ft8_get_supp_params.argtypes = [P(ctypes.c_float)]
    d.ft8_get_supp_params.restype = ctypes.c_int
    d.ft8_set_decode_params.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int]
    d.ft8_set_decode_params.restype = None
    return d, sha


def read_table(d):
    n = d.ft8_get_decoder_params(None, 0)
    buf = (Entry * n)()
    m = d.ft8_get_decoder_params(buf, n)
    assert m == n
    return [{"name": e.name.decode("ascii"), "value": e.value, "default": e.default_value, "kind": e.kind, "reserved": e.reserved,
             "raw_name": bytes(e)[:48]} for e in buf]


def get_supp(d):
    out = (ctypes.c_float * 3)()
    rc = d.ft8_get_supp_params(out)
    return rc, tuple(out)


def set_supp(d, a, b, c):
    return d.ft8_set_supp_params(ctypes.c_float(a), ctypes.c_float(b), ctypes.c_float(c))


def bits3(t):
    return tuple(fbits(x) for x in t)


# ── mini C constant evaluator (for S1-f(i)) ────────────────────────────────────
def strip_c(src):
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append("".join("\n" if c == "\n" else " " for c in src[i:j])); i = j
        elif src.startswith("//", i):
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif src[i] in "\"'":
            q = src[i]; j = i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            out.append(q + " " * (j - i - 1) + q); i = j + 1
        else:
            out.append(src[i]); i += 1
    return "".join(out)


def parse_defines(src):
    """{NAME: expr-string} for object-like #defines, continuation lines joined, comments stripped."""
    clean = strip_c(src).replace("\\\n", " ")
    out = {}
    for m in re.finditer(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+(.+)$", clean, re.M):
        out[m.group(1)] = m.group(2).strip()
    return out


def eval_c(expr, defs, seen=()):
    """Evaluates a C constant expression built from numbers, names, + - * / < > ( ) and one ?: ternary. Returns (value, is_float)."""
    e = expr.strip()
    is_float = bool(re.search(r"\d\.\d*[fF]?|\.\d+[fF]?", e))
    tern = re.fullmatch(r"\((.+?)\s*\?\s*(.+?)\s*:\s*(.+?)\)", e) or re.fullmatch(r"(.+?)\s*\?\s*(.+?)\s*:\s*(.+?)", e)
    if tern:
        e = "((%s) if (%s) else (%s))" % (tern.group(2), tern.group(1), tern.group(3))

    def sub_name(m):
        nm = m.group(0)
        if nm in ("if", "else"):
            return nm
        if nm in seen or nm not in defs:
            raise ValueError("unresolved name %s in %r" % (nm, expr))
        v, _ = eval_c(defs[nm], defs, seen + (nm,))
        return "(%r)" % v
    e = re.sub(r"\b([A-Za-z_]\w*)\b", sub_name, e)
    e = re.sub(r"(\d*\.\d+|\d+\.\d*|\d+)[fFuUlL]+\b", r"\1", e)
    if not re.fullmatch(r"[\d\s.+\-*/()<>=eE,ifsl]*", e.replace("if", "").replace("else", "")):
        raise ValueError("unsafe expression %r" % e)
    v = eval(e, {"__builtins__": {}}, {})
    return v, is_float


# ── DLL-run wrapper (S1-a) ─────────────────────────────────────────────────────
def cmd_extract(a):
    S1.cmd_extract(a)


def cmd_run(a):
    CFG["supp"] = tuple(float(x) for x in a.supp.split(",")) if a.supp else None
    S1.LIVE_NHARD = int(a.nhard)
    ns = types.SimpleNamespace(dll=a.dll, tag=a.tag, leg=a.leg, armed=a.armed, pass2=a.pass2)
    S1.cmd_run(ns)
    # annotate the JSON with the config actually applied (audit trail)
    p = os.path.join(OUT_DIR, "%s_%s.json" % (a.tag, a.leg))
    with open(p) as f:
        j = json.load(f)
    j.update({"nhard": int(a.nhard), "supp_explicit": CFG["supp"], "commit": NEW_COMMIT if a.dll == "NEW" else OLD_COMMIT})
    with open(p, "w") as f:
        json.dump(j, f, indent=1)


def cmd_tablecheck(a):
    import hashlib
    import wave
    d, _sha = load_new_dll()
    files = sorted(f for f in os.listdir(S1.CORPUS) if f.endswith(".wav"))
    with wave.open(os.path.join(S1.CORPUS, files[len(files) // 2])) as w:
        pcm = np.frombuffer(w.readframes(S1.N_SAMPLES), dtype="<i2").astype(np.float32) / 32768.0
    sh = S1.Shim(os.path.join(BIN_DIR, "libft8_NEW.dll"), "NEW", has_probe=True)
    sh.set_params(S1.LIVE_PASS2)
    lines = []
    for _ in range(3):
        _rc, ln, _pcl = sh.decode_canonical(pcm, 0)
        lines.append(hashlib.sha256(ln.encode("latin-1")).hexdigest()[:16])
        for _k in range(a.reads):
            read_table(d)
    print(json.dumps({"reads": a.reads, "lines": lines}))


# ── S1-b / S1-f / S1-g (unit) ──────────────────────────────────────────────────
def cmd_unit(a):
    d, sha = load_new_dll()
    R = {"sha": sha, "version": NEW_VER, "S1-b": {}, "S1-g": {}, "S1-f(i)": {}, "S1-f(ii)": {}}
    fails = []

    def chk(cond, msg):
        if not cond:
            fails.append(msg)
        return bool(cond)

    # ---------------- fresh-process state ----------------
    tbl0 = read_table(d)
    rc, sp0 = get_supp(d)
    chk(rc == 0 and bits3(sp0) == bits3(DEF_SUPP), "fresh-process supp defaults != (-5,15,1): %r" % (sp0,))

    # ---------------- S1-b ----------------
    ok = True
    valid = [(-25.0, 15.0, 1.0), (-10.0, 15.0, 0.5), (-5.0, 1000.0, 0.0), (0.0, 0.5, 1.0), (-5.0, 3.0e38, 0.5)]
    vres = []
    for t in valid:
        r = set_supp(d, *t)
        rc2, g = get_supp(d)
        good = (r == 0 and rc2 == 0 and bits3(g) == bits3(t))
        vres.append({"triple": t, "set_rc": r, "get_bits_equal": bits3(g) == bits3(t)})
        ok &= chk(good, "valid triple %r: set rc %d, readback %r" % (t, r, g))
    prior = (-10.0, 20.0, 0.5)
    assert set_supp(d, *prior) == 0
    nan, inf = float("nan"), float("inf")
    invalid = []
    for pos in range(3):
        for bad in (nan, inf, -inf):
            t = list(prior); t[pos] = bad
            invalid.append(("nonfinite", tuple(t)))
    invalid += [("min>=max", (-5.0, -5.0, 0.5)), ("min>=max", (5.0, 5.0, 0.5)), ("min>=max", (15.0, -5.0, 0.5)), ("min>=max", (30.0, 15.0, 0.5))]
    invalid += [("side<0", (-5.0, 15.0, -0.001)), ("side<0", (-5.0, 15.0, -1.0))]
    invalid += [("side>1", (-5.0, 15.0, 1.0001)), ("side>1", (-5.0, 15.0, 2.0))]
    ires = []
    for cls, t in invalid:
        r = set_supp(d, *t)
        rc2, g = get_supp(d)
        good = (r == -1 and rc2 == 0 and bits3(g) == bits3(prior))
        ires.append({"class": cls, "args": [repr(x) for x in t], "rc": r, "prior_unchanged": bits3(g) == bits3(prior)})
        ok &= chk(good, "invalid %s %r: rc %d, triple now %r" % (cls, t, r, g))
    ok &= chk(d.ft8_get_supp_params(None) == -1, "get(NULL) != -1")
    R["S1-b"] = {"pass": ok and len(invalid) == 17, "n_valid": len(valid), "n_invalid": len(invalid), "valid": vres, "invalid": ires}
    chk(len(invalid) == 17, "invalid-call count %d != 17 (9+4+2+2)" % len(invalid))
    set_supp(d, *DEF_SUPP)

    # ---------------- S1-g ----------------
    n = d.ft8_get_decoder_params(None, 0)
    g = {}
    g["total"] = n
    ok = chk(n == N_ROWS_TOTAL, "row count %d != %d" % (n, N_ROWS_TOTAL))
    names = [e["name"] for e in tbl0]
    ok &= chk(len(set(names)) == len(names), "duplicate names")
    ok &= chk(sum(1 for e in tbl0 if e["kind"] == KIND_RUNTIME) == N_ROWS_RUNTIME and sum(1 for e in tbl0 if e["kind"] == KIND_COMPILE) == N_ROWS_COMPILE,
              "kind split != 6/24")
    ok &= chk(all(e["kind"] in (KIND_COMPILE, KIND_RUNTIME) and e["reserved"] == 0 for e in tbl0), "kind/reserved out of contract")
    ok &= chk([e["name"] for e in tbl0 if e["kind"] == KIND_RUNTIME] == RUNTIME_NAMES, "runtime rows/order != expected")
    ok &= chk(all(len(e["raw_name"]) == 48 and e["raw_name"][-1:] == b"\x00" and e["raw_name"].rstrip(b"\x00").count(b"\x00") == 0 for e in tbl0),
              "names not NUL-terminated / zero-padded")
    ok &= chk(all(e["value"] == e["default"] for e in tbl0), "fresh process: some value != default")
    # capacity semantics
    CAP = 5
    buf = (Entry * n)()
    ctypes.memset(buf, 0xEE, ctypes.sizeof(buf))
    ret = d.ft8_get_decoder_params(buf, CAP)
    raw = bytes(buf)
    esz = ctypes.sizeof(Entry)
    tail_untouched = all(b == 0xEE for b in raw[CAP * esz:])
    full = (Entry * n)(); d.ft8_get_decoder_params(full, n)
    head_ok = bytes(full)[:CAP * esz] == raw[:CAP * esz]
    ok &= chk(ret == n and tail_untouched and head_ok, "small-capacity semantics: ret %d tail_untouched %s head_ok %s" % (ret, tail_untouched, head_ok))
    for capv in (0, -1):
        b2 = (Entry * n)(); ctypes.memset(b2, 0xEE, ctypes.sizeof(b2))
        r2 = d.ft8_get_decoder_params(b2, capv)
        ok &= chk(r2 == n and all(x == 0xEE for x in bytes(b2)), "capacity %d wrote or returned %d" % (capv, r2))
    # round-trip
    snap_ct = {e["name"]: (e["value"], e["default"]) for e in tbl0 if e["kind"] == KIND_COMPILE}
    d.ft8_set_decode_params(7, ctypes.c_float(0.15), 50)
    assert set_supp(d, -10.0, 15.0, 0.5) == 0
    t1 = {e["name"]: e for e in read_table(d)}
    want = {"k_min_score_pass2": 7.0, "osd_corr_threshold": f32(0.15), "osd_nhard_max": 50.0,
            "supp_snr_min_db": -10.0, "supp_snr_max_db": 15.0, "supp_side_weight": 0.5}
    rt_ok = all(t1[k]["value"] == v for k, v in want.items())
    ok &= chk(rt_ok, "round-trip set values not reported: %r" % {k: t1[k]["value"] for k in want})
    dflt0 = {e["name"]: e["default"] for e in tbl0 if e["kind"] == KIND_RUNTIME}
    ok &= chk(all(t1[k]["default"] == dflt0[k] for k in want), "default_value moved after set")
    ok &= chk(all((t1[k]["value"], t1[k]["default"]) == v for k, v in snap_ct.items()), "compile-time row moved after set")
    d.ft8_set_decode_params(10, ctypes.c_float(0.10), 60)
    assert set_supp(d, *DEF_SUPP) == 0
    t2 = {e["name"]: e for e in read_table(d)}
    ok &= chk(all(t2[k]["value"] == t2[k]["default"] for k in want), "after reset: value != default: %r" % {k: (t2[k]["value"], t2[k]["default"]) for k in want})
    ok &= chk(all(t2[k]["value"] == dflt0[k] for k in want), "after reset: value != fresh default")
    g.update({"round_trip_ok": rt_ok, "small_capacity_ok": bool(ret == n and tail_untouched and head_ok)})
    # table read does not change decode output. The canonical line carries CUMULATIVE process-global counters, so the two
    # sequences run in TWO FRESH PROCESSES with identical call counts: [decode x3] vs [decode, read x3] x3.
    def tablecheck(reads):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "tablecheck", "--reads", str(reads)], capture_output=True, check=True)
        return json.loads(r.stdout.decode().strip().splitlines()[-1])
    t_a, t_b = tablecheck(0), tablecheck(3)
    ok &= chk(t_a["lines"] == t_b["lines"] and len(t_a["lines"]) == 3, "decode output changed by table reads")
    g["decode_unchanged_by_table_read"] = bool(t_a["lines"] == t_b["lines"])
    g["tablecheck_line_hashes"] = t_a["lines"]
    R["S1-g"] = {"pass": bool(ok), **g}

    # ---------------- S1-f(i) ----------------
    shim_src, dec_src = git_show(NEW_COMMIT, SHIM_C), git_show(NEW_COMMIT, DECODE_C)
    sdefs, ddefs = parse_defines(shim_src), parse_defines(dec_src)
    k_names = sorted(k for k in sdefs if re.fullmatch(r"K_[A-Z0-9_]+", k))
    want_names = k_names + ["FT8_AP_LLR_HARD", "HASH_TABLE_SIZE"]
    dec_names = ["OSD_DEPTH", "OSD_SEARCH_K_MAX", "LLR_NORM_TARGET_VARIANCE", "CAND_TIME_OFFSET_MIN", "CAND_TIME_OFFSET_END"]
    tab = {e["name"]: e for e in tbl0}
    fi = {"k_defines_found": len(k_names), "rows": []}
    ok = True
    for nm in want_names + dec_names:
        defs = sdefs if nm in want_names else ddefs
        if not chk(nm in tab, "S1-f(i): %s not in table" % nm):
            ok = False; continue
        v, is_f = eval_c(defs[nm], defs)
        exp = f32(v) if is_f else float(v)
        good = (tab[nm]["value"] == exp and tab[nm]["default"] == exp and tab[nm]["kind"] == KIND_COMPILE)
        fi["rows"].append({"name": nm, "src_expr": defs[nm], "src_value": exp, "table_value": tab[nm]["value"], "ok": good})
        ok &= chk(good, "S1-f(i): %s table %r != source %r" % (nm, tab[nm]["value"], exp))
    ok &= chk(len(k_names) == 17, "K_ define count %d != 17" % len(k_names))
    # setters
    sigs = re.findall(r"^\s*(?:int|void)\s+(ft8_set_\w+)\s*\(([^)]*)\)", strip_c(shim_src), re.M)
    MAPPED = {"ft8_set_decode_params": ["k_min_score_pass2", "osd_corr_threshold", "osd_nhard_max"],
              "ft8_set_supp_params": ["supp_snr_min_db", "supp_snr_max_db", "supp_side_weight"]}
    NONPARAM = {"ft8_set_ap_bits", "ft8_set_probe"}
    setters = []
    for nm, args in sigs:
        pn = [re.split(r"[\s*]+", x.strip())[-1] for x in args.replace("\n", " ").split(",") if x.strip()]
        if nm in MAPPED:
            good = all(t in tab and tab[t]["kind"] == KIND_RUNTIME for t in MAPPED[nm]) and len(pn) == len(MAPPED[nm])
        else:
            good = nm in NONPARAM
        setters.append({"setter": nm, "params": pn, "mapped_or_nonparam": bool(good), "class": ("mapped" if nm in MAPPED else "non-parameter")})
        ok &= chk(good, "S1-f(i): setter %s is neither mapped nor on the non-parameter list" % nm)
    fi["setters"] = setters
    ok &= chk({s["setter"] for s in setters} == set(MAPPED) | NONPARAM, "setter set != expected")
    R["S1-f(i)"] = {"pass": bool(ok), **fi}

    # ---------------- S1-f(ii) mechanical ----------------
    page = git_show(NEW_COMMIT, PAGE)
    src = {SHIM_C: git_show(NEW_COMMIT, SHIM_C), DECODE_C: dec_src, MONITOR_C: git_show(NEW_COMMIT, MONITOR_C), LDPC_C: git_show(NEW_COMMIT, LDPC_C)}
    clean = {k: strip_c(v).split("\n") for k, v in src.items()}
    # (file, [lines], substring that must be on that line, page literal id)
    CLAIMS = [(SHIM_C, [1148, 1394, 1984], "0.5f", "wf-db-quantisation"), (SHIM_C, [1148, 1394], "120.0f", "wf-db-quantisation"),
              (MONITOR_C, [192], "240", "wf-db-quantisation"), (MONITOR_C, [182], "1E-12f", "wf-db-quantisation"),
              (SHIM_C, [682, 711, 783], "* 23", "hash-probe-multiplier"), (SHIM_C, [730, 859, 1912, 1925], ">= 2", "hash-ambiguity-rule"),
              (DECODE_C, [223, 229, 238], "1", "sync-neighbourhood"), (MONITOR_C, [75], "2.0f", "waterfall-frontend"),
              (LDPC_C, [223, 227], "4.97f", "bp-tanh-approximation"), (LDPC_C, [236, 237, 248, 249], "945.0f", "bp-tanh-approximation")]
    ref_ok, ref_res = True, []
    for f, lines, sub, lit in CLAIMS:
        for ln in lines:
            hit = sub in clean[f][ln - 1]
            ref_res.append({"file": f.split("/")[-1], "line": ln, "expect": sub, "literal_id": lit, "on_line": bool(hit)})
            ref_ok &= chk(hit, "S1-f(ii): page cites %s:%d for %r but the line does not contain it" % (f, ln, sub))
    ids = re.findall(r'data-literal="([^"]+)"', page)
    # count <li> ELEMENTS only: the page's explanatory HTML comment also quotes the attribute text (line 85), which a bare
    # attribute count double-counted on the first unit run (plumbing fix, bar unchanged: 6 entries).
    n_notinc = len(re.findall(r'<li\s[^>]*data-status="not-included"', page))
    derived_none = ("derived-none" in ids)
    no_derived_lit = all(not re.search(r"\b3\.125\b", "\n".join(v)) for v in clean.values())
    ref_ok &= chk(no_derived_lit, "S1-f(ii): a `3.125` literal exists in the decode-path sources but the page says none")
    ref_ok &= chk(n_notinc == 6, "page 'Not included' <li> count %d != 6" % n_notinc)
    # QA-flagged, page-uncited (LISTED, not adjudicated)
    flagged = []
    for f, ln, pat, why in [(SHIM_C, 1146, r"cum \* 2 >=", "noise-floor MEDIAN (global) -- percentile 50 via `cum*2 >= total`; feeds noise_raw (the value suppression writes back) and noise_floor_db"),
                            (SHIM_C, 1392, r"cum \* 2 >=", "noise-floor MEDIAN (local) -- feeds the reported SNR AND the suppression ramp's input (all_supp_snrs)")]:
        line = clean[f][ln - 1]
        on_page = (":%d" % ln in page) or (str(ln) in re.sub(r"<[^>]+>", " ", page))
        flagged.append({"file": f.split("/")[-1], "line": ln, "matches": bool(re.search(pat, line)), "page_cites_it": bool(on_page), "why": why})
        chk(bool(re.search(pat, line)), "flagged line %s:%d moved" % (f, ln))
    R["S1-f(ii)"] = {"mechanical_pass": bool(ref_ok), "page_cites_checked": len(ref_res), "page_not_included_items": n_notinc,
                     "page_literal_ids": ids, "derived_none_present": derived_none, "no_3125_literal_in_sources": no_derived_lit,
                     "QA_flagged_uncited_for_Architect": flagged, "cite_results": ref_res}
    R["failures"] = fails
    R["pass_all"] = (not fails)
    out = os.path.join(OUT_DIR, "unit.json")
    S1.ensure_ignored(out)
    with open(out, "w") as f:
        json.dump(R, f, indent=1, default=str)
    log("unit: %s  (%d failures)" % ("PASS" if not fails else "FAIL", len(fails)))
    for m in fails:
        log("  FAIL: " + m)


# ── S1-c / S1-d plumbing ───────────────────────────────────────────────────────
def pick_cells():
    prim = [c for c in DM.build_cells() if abs(c["delta_hz"] - 12.0) < 1e-9 and abs(c["x_db"] - 3.0) < 1e-9 and c["e_snr_db"] == -5.0]
    e15 = [c for c in DP.build_cells() if c["group"] == "e15" and abs(c["delta_hz"] - 6.25) < 1e-9]
    assert len(prim) == 1 and len(e15) == 1, (len(prim), len(e15))
    return {"c": prim[0], "d": e15[0]}


MODES = {"default": None, "floor": (-25.0, 15.0, 1.0), "explicit": (-5.0, 15.0, 1.0), "side0": (-5.0, 15.0, 0.0)}


def cmd_plumb(a):
    cell = pick_cells()[a.cell]
    out = os.path.join(OUT_DIR, "plumb_%s_%s.jsonl" % (a.cell, a.mode))
    S1.ensure_ignored(out)
    d, sha = load_new_dll()
    CFG["supp"] = MODES[a.mode]
    sh = S1.Shim(os.path.join(BIN_DIR, "libft8_NEW.dll"), "NEW", has_probe=True)
    S1.LIVE_NHARD = 40
    sh.set_params(S1.LIVE_PASS2)
    full, _abl, target = DM.cell_signals(cell)
    with open(out, "w", newline="\n") as fo:
        for t in range(PLUMB_N):
            seed = SR.trial_seed(t, cell["part_index"])
            pcm = SR.render_scene(full, seed)
            n, rows, pcl, canon = DP.decode(sh, pcm, arm=(float(target), float(DM.F_TIME_OFFSET_S)))
            r0, l0 = DP.read_probe(sh, 0)
            r1, l1 = DP.read_probe(sh, 1)
            ns, supp = DP.read_supp(sh)
            e_i = DP.find_msg(rows, SR.E_FREQ_HZ, DP.E_MESSAGE)
            n_p0 = pcl[0] if pcl else 0
            e_rec = supp[e_i] if (e_i is not None and e_i < n_p0 and e_i < len(supp)) else None
            pk = lambda l: (struct.pack("<174f", *l).hex() if l is not None else None)
            fo.write(json.dumps({"t": t, "mode": a.mode, "sha": sha, "canon": canon, "pc": pcl, "rc0": r0, "rc1": r1, "P0": pk(l0), "P1": pk(l1),
                                 "supp_n": ns, "supp": [[x[0], x[1], x[2], x[3], fbits(x[4]), fbits(x[5])] for x in supp],
                                 "e_i": e_i, "e_rec": ([e_rec[0], e_rec[1], e_rec[2], e_rec[3], fbits(e_rec[4]), fbits(e_rec[5]), e_rec[4], e_rec[5]] if e_rec else None)}) + "\n")
    log("plumb %s/%s done" % (a.cell, a.mode))


def load_plumb(cell, mode):
    with open(os.path.join(OUT_DIR, "plumb_%s_%s.jsonl" % (cell, mode))) as f:
        return [json.loads(x) for x in f]


# ── verdict ─────────────────────────────────────────────────────────────────────
def clamp01(x):
    return max(0.0, min(1.0, x))


def cmd_verdict(a):
    R = {"commit_under_test": NEW_COMMIT, "old_commit": OLD_COMMIT, "pins": {"OLD": [OLD_SHA, OLD_VER], "NEW": [NEW_SHA, NEW_VER]}}
    need = [("old", "synth"), ("old", "real"), ("new", "synth"), ("new", "real"), ("new2", "synth"), ("new2", "real"), ("expl", "synth"), ("expl", "real"),
            ("old60", "synth"), ("old60", "real"), ("new60", "synth"), ("new60", "real"), ("arm", "real"), ("ctl30", "real"), ("supp_w0", "real"), ("supp_m25", "real")]
    for tag, leg in need:
        if not os.path.exists(os.path.join(OUT_DIR, "%s_%s.json" % (tag, leg))):
            log("MISSING run %s_%s -- cannot verdict" % (tag, leg)); sys.exit(3)
    for cell, mode in (("c", "default"), ("c", "floor"), ("d", "default"), ("d", "explicit"), ("d", "side0")):
        if not os.path.exists(os.path.join(OUT_DIR, "plumb_%s_%s.jsonl" % (cell, mode))):
            log("MISSING plumb %s/%s" % (cell, mode)); sys.exit(3)
    if not os.path.exists(os.path.join(OUT_DIR, "unit.json")):
        log("MISSING unit.json"); sys.exit(3)
    L = lambda t, l: S1.load(t, l)
    same = S1.same
    row0 = {}
    row0["0a"] = all(L(t, l)["sha"] == (OLD_SHA if t.startswith("old") else NEW_SHA) and L(t, l)["version"] == (OLD_VER if t.startswith("old") else NEW_VER) for t, l in need)
    row0["0b"] = all(same("new", "new2", l)[0] for l in ("synth", "real"))
    nr, ar = L("new", "real"), L("arm", "real")
    row0["0c"] = bool(nr["results_total"] >= 1000 and ar["n_supp_ge1"] >= 0.5 * ar["calls"] and ar["pass1_decodes"] >= 10)
    row0["0d"] = not same("new", "ctl30", "real")[0]
    row0["0d2"] = bool((not same("new", "supp_w0", "real")[0]) and (not same("new", "supp_m25", "real")[0]))
    row0["0e"] = all((L(t, "synth")["calls"] == 300) for t in ("old", "new", "new2", "expl", "old60", "new60")) and \
        all((L(t, "real")["calls"] >= 190) for t in ("old", "new", "new2", "expl", "old60", "new60", "arm", "ctl30", "supp_w0", "supp_m25"))
    R["row0"] = row0
    R["row0_detail"] = {"real_results_total": nr["results_total"], "real_calls": nr["calls"], "armed_real_n_supp_ge1": ar["n_supp_ge1"],
                        "armed_real_calls": ar["calls"], "armed_real_pass1_decodes": ar["pass1_decodes"], "synth_results_total": L("new", "synth")["results_total"],
                        "ctl30_first_diff_line": same("new", "ctl30", "real")[3], "supp_w0_first_diff_line": same("new", "supp_w0", "real")[3],
                        "supp_m25_first_diff_line": same("new", "supp_m25", "real")[3]}
    # fraction of calls that differ under the 0d2 controls (reporting only)
    def frac_diff(t1, t2, leg):
        with open(os.path.join(OUT_DIR, "%s_%s.canon" % (t1, leg)), "rb") as f, open(os.path.join(OUT_DIR, "%s_%s.canon" % (t2, leg)), "rb") as g:
            A, B = f.read().split(b"\n"), g.read().split(b"\n")
        n = min(len(A), len(B))
        return "%d/%d" % (sum(1 for i in range(n) if A[i] != B[i]), n)
    R["reporting"] = {"0d2_side_weight_0_calls_differing": frac_diff("new", "supp_w0", "real"), "0d2_floor_-25_calls_differing": frac_diff("new", "supp_m25", "real")}

    # --- plumbing ROW 0 and verdicts ---
    cd, cf = load_plumb("c", "default"), load_plumb("c", "floor")
    dd, de, ds = load_plumb("d", "default"), load_plumb("d", "explicit"), load_plumb("d", "side0")
    Q = [i for i in range(PLUMB_N) if cd[i]["e_rec"] and cf[i]["e_rec"]]
    row0["c_Q>=15"] = len(Q) >= 15
    row0["c_pass0_snr_bit_identical"] = all(cd[i]["e_rec"][4] == cf[i]["e_rec"][4] for i in Q)
    fac_d = sorted(r["e_rec"][7] for r in dd if r["e_rec"])
    row0["d_E_suppressed"] = bool(len(fac_d) >= 15 and fac_d[len(fac_d) // 2] <= 0.05)
    R["row0"] = row0
    R["row0_detail"].update({"c_Q": len(Q), "d_E_records": len(fac_d), "d_E_median_factor": (fac_d[len(fac_d) // 2] if fac_d else None)})
    if not all(row0.values()):
        R["verdict"] = "ROW 0 STOP: " + ",".join(k for k, v in row0.items() if not v)
        print(json.dumps(R, indent=1, default=str)); return

    s1a = {"S1-a.1": {l: same("old", "new", l) for l in ("synth", "real")},
           "S1-a.2": {l: same("old", "new", l, ".ext") for l in ("synth", "real")},
           "S1-a.3": {l: same("old60", "new60", l) for l in ("synth", "real")},
           "S1-a.4": {l: same("old", "expl", l) for l in ("synth", "real")}}
    R["S1-a"] = {"pass": all(v[0] for sub in s1a.values() for v in sub.values()), "detail": s1a}

    unit = json.load(open(os.path.join(OUT_DIR, "unit.json")))
    R["S1-b"] = {"pass": unit["S1-b"]["pass"], "n_valid": unit["S1-b"]["n_valid"], "n_invalid": unit["S1-b"]["n_invalid"]}
    inner = [i for i in Q if -24.0 < cf[i]["e_rec"][6] < 14.0]
    c_formula = [abs(cf[i]["e_rec"][7] - (1.0 - clamp01((cf[i]["e_rec"][6] + 25.0) / 40.0))) for i in Q]
    c_diff = [abs(cf[i]["e_rec"][7] - cd[i]["e_rec"][7]) for i in inner]
    R["S1-c"] = {"pass": bool(all(x <= FACTOR_TOL for x in c_formula) and all(x > 1e-3 for x in c_diff) and len(inner) >= 15),
                 "Q": len(Q), "inner": len(inner), "max_formula_err": max(c_formula), "min_factor_delta_vs_default": (min(c_diff) if c_diff else None),
                 "example_snr_default_floor": [cf[Q[0]]["e_rec"][6], cd[Q[0]]["e_rec"][7], cf[Q[0]]["e_rec"][7]]}
    d_i = sum(1 for i in range(PLUMB_N) if de[i]["rc1"] == 0 and ds[i]["rc1"] == 0 and de[i]["P1"] != ds[i]["P1"])
    d_ii = sum(1 for i in range(PLUMB_N) if de[i]["canon"] == dd[i]["canon"] and de[i]["P0"] == dd[i]["P0"] and de[i]["P1"] == dd[i]["P1"]
               and de[i]["supp"] == dd[i]["supp"])
    d_iii = sum(1 for i in range(PLUMB_N) if de[i]["P0"] == ds[i]["P0"])
    R["S1-d"] = {"pass": bool(d_i >= 19 and d_ii == PLUMB_N and d_iii == PLUMB_N), "i_P1_differs_s1_vs_s0": "%d/20 (bar >=19)" % d_i,
                 "ii_null_explicit_eq_default": "%d/20 (bar 20)" % d_ii, "iii_P0_unchanged_by_setter": "%d/20 (bar 20)" % d_iii,
                 "E_factor_median_default": fac_d[len(fac_d) // 2]}
    R["S1-f(i)"] = {"pass": unit["S1-f(i)"]["pass"], "k_defines_found": unit["S1-f(i)"]["k_defines_found"], "setters": unit["S1-f(i)"]["setters"]}
    R["S1-f(ii)_mechanical"] = {"pass": unit["S1-f(ii)"]["mechanical_pass"], "page_cites_checked": unit["S1-f(ii)"]["page_cites_checked"],
                                "QA_flagged_uncited_for_Architect": unit["S1-f(ii)"]["QA_flagged_uncited_for_Architect"]}
    R["S1-g"] = {"pass": unit["S1-g"]["pass"], "total_rows": unit["S1-g"]["total"], "decode_unchanged_by_table_read": unit["S1-g"]["decode_unchanged_by_table_read"]}
    gates = ("S1-a", "S1-b", "S1-c", "S1-d", "S1-f(i)", "S1-f(ii)_mechanical", "S1-g")
    R["verdict"] = "ALL EXECUTABLE GATES PASS" if all(R[k]["pass"] for k in gates) else "FAIL: " + ",".join(k for k in gates if not R[k]["pass"])
    out = os.path.join(OUT_DIR, "verdict.json")
    S1.ensure_ignored(out)
    with open(out, "w") as f:
        json.dump(R, f, indent=1, default=str)
    print(json.dumps(R, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extract").set_defaults(fn=cmd_extract)
    r = sub.add_parser("run")
    r.add_argument("--dll", choices=["OLD", "NEW"], required=True)
    r.add_argument("--tag", required=True)
    r.add_argument("--leg", choices=["synth", "real"], required=True)
    r.add_argument("--armed", action="store_true")
    r.add_argument("--pass2", type=int, default=S1.LIVE_PASS2)
    r.add_argument("--nhard", type=int, default=40)
    r.add_argument("--supp", default=None, help="min,max,side (NEW only)")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("unit").set_defaults(fn=cmd_unit)
    tcp = sub.add_parser("tablecheck")
    tcp.add_argument("--reads", type=int, required=True)
    tcp.set_defaults(fn=cmd_tablecheck)
    p = sub.add_parser("plumb")
    p.add_argument("--cell", choices=["c", "d"], required=True)
    p.add_argument("--mode", choices=sorted(MODES), required=True)
    p.set_defaults(fn=cmd_plumb)
    sub.add_parser("verdict").set_defaults(fn=cmd_verdict)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
