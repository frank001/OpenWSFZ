#!/usr/bin/env python
"""S1-SNR-REPLAY (spec 2026-10-09-1025-architect-to-qa-spec-s1-snr-replay.md on arch/osd-fix, amendment 1): audio x BUILD cross-replay of the 30 S1 cycles of five
recorded R&R runs. Offline, CPU only, no station. Numbers only (HK-037): the harness writes no text; S1 rows are joined to truth by cycle stamp and frequency
(within 4 Hz; S1 is one signal per cycle at 1500 Hz) and to each run's live S1 rows by cycle stamp.

BUILDS (two pinned harness binaries; the cross is audio x BUILD because the fix commit also changes managed code and adds P/Invoke exports):
  M = the NHARD-REP harness  (DLL 2fa6d993..., Replay81 4a9cf533...): src/OpenWSFZ.Ft8 is unchanged between 766f9cc2 and be3cc5ac (git diff), so this is 766f9cc2's decoder.
  F = the osd-fix harness    (DLL 2029b080...82bb, Replay81 c2ff1981...): the fix build 3276573b.
AUDIO SETS (daemon cycle-audio, S1 stamps from each run's truth.csv): A0929 (09-29 OFF), A1002, A1003 (the two baseline-194 runs, 0 shared stamps), A04 (10-04 live +0.88),
  A08 (10-08 live +1.48). Fresh process per cell, the cycle before the first S1 cycle is the warm-up (decoded and discarded), 30 cycles in ascending order.

  python qa/rr-study/s1-snr-replay/s1_snr_replay.py select   # write the frozen per-audio selection files (stamps only)
  python qa/rr-study/s1-snr-replay/s1_snr_replay.py plan     # print the cells
  python qa/rr-study/s1-snr-replay/s1_snr_replay.py run      # replay every cell (CPU only; on the Captain's go)
  python qa/rr-study/s1-snr-replay/s1_snr_replay.py rows     # validity rows, verdict, descriptive tables -> s1_snr_replay_result.json

ROWS (predicates as code; the spec's text is the authority):
  SV1 DLL pin equal at start and end of every cell and equal to its build's pin; read-back as intended.
  SV2 A04.M reproduces the 10-04 live S1 OpenWSFZ rows: the same stamps decoded and the SAME integer SNR on every decoded row.
  SV3 A08.F reproduces the 10-08 live S1 OpenWSFZ rows, same predicate.
  SV4 (amendment 1) A04.M run a second time in a fresh process: identical decoded stamps and SNRs; otherwise the 0-rows predicate is WITHHELD.
  SR-BUILD  : validity PASS and in A04 or A08 at least one row decoded by both builds has a different SNR under F than under M.
  SR-AUDIO  : validity PASS, 0 such rows, and bias(A08) - bias(A04) >= 0.40 dB under BOTH builds.
  SR-NEITHER: validity PASS, 0 such rows, and that difference < 0.40 dB under either build (unreachable when SV2/SV3 pass, kept as the spec's third row).
  A validity FAIL => WITHHELD (the differences are reported; the Architect rules).
"""
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ART = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
RES_ROOT = os.path.join(REPO, "qa", "rr-study", "results")
OUT_RES = os.path.join(RES_ROOT, "2026-10-09-s1-snr-replay")
OUT_ART = os.path.join(ART, "rr_2026-10-09_s1_snr_replay")

TOL_HZ = 4.0
BAR_DB = 0.40          # the spec's bar (HK-038: two thirds of the live +0.60 dB difference between today's two runs)
THREADS = "8"

BUILDS = {
    "M": {"dir": r"D:\Projects\claude\_qa-scratch\nhard-rep\out", "dll": "2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365",
          "harness": "4a9cf5332812cb367e55347664c6ead309eeb81511530f5a68156f4ba02a79a8", "sign_flag": False},
    "F": {"dir": r"D:\Projects\claude\_qa-scratch\osd-fix-harness", "dll": "2029b0804a9abcc378fa037893b28236e4e5dec4459ba443d31c2027a58d82bb",
          "harness": "c2ff19815438cde60c6c019ba0e1b6e53abcaf802b26c7192a89a221113e5843", "sign_flag": True},
}
# audio key -> (daemon output folder under artefacts, the run's results folder holding truth.csv and S1_matched.csv, live S1_matched exists)
AUDIO = {
    "A0929": ("_rr_subfeas_off_daemon_output", "2026-09-29-0d6b193-OFF", False),
    "A1002": ("_rr_baseline194_daemon_output", "2026-10-02-96077a0", True),
    "A1003": ("_rr_baseline194_daemon_output", "2026-10-03-96077a0", True),
    "A04": ("_rr_main766f9cc2_daemon_output", "2026-10-04-766f9cc", True),
    "A08": ("_rr_fix3276573b_daemon_output", "2026-10-08-0a1ff63", True),
}
# cell -> (audio, build, nhard)
CELLS = {
    "A04.M": ("A04", "M", 40), "A08.F": ("A08", "F", 40), "A04.F": ("A04", "F", 40), "A08.M": ("A08", "M", 40),
    "A04.M.rep": ("A04", "M", 40),
    "A0929.M": ("A0929", "M", 40), "A0929.F": ("A0929", "F", 40), "A1002.M": ("A1002", "M", 40), "A1002.F": ("A1002", "F", 40),
    "A1003.M": ("A1003", "M", 40), "A1003.F": ("A1003", "F", 40), "A08.F24": ("A08", "F", 24),
}
READBACK_RE = re.compile(r"# readback (start|end) .*?nhard=(\d+)")


# ---------- pure functions (tested) ----------
def stamp_of(cycle_utc):
    d, t = cycle_utc.rstrip("Z").split("T")
    return d[2:4] + d[5:7] + d[8:10] + "_" + t.replace(":", "")


def prev_stamp(stamp):
    import datetime as dt
    t = dt.datetime.strptime(stamp, "%y%m%d_%H%M%S") - dt.timedelta(seconds=15)
    return t.strftime("%y%m%d_%H%M%S")


def s1_truth(rows):
    """rows: dicts of a truth.csv. -> ordered list of (stamp, true_freq, true_snr) for scenario S1."""
    out = {}
    for r in rows:
        if r["scenario_id"] == "S1":
            out[stamp_of(r["cycle_utc"])] = (float(r["true_freq_hz"]), float(r["true_snr_db"]))
    return [(s, f, n) for s, (f, n) in sorted(out.items())]


def parse_outcomes(lines):
    """outcomes.csv lines (stamp,batch,index,freq,dt,snr) -> {stamp: [(freq, snr)]}; numeric only."""
    out = {}
    for ln in lines:
        p = ln.split(",")
        if len(p) < 6 or not p[0]:
            continue
        out.setdefault(p[0], []).append((float(p[3]), int(round(float(p[5])))))
    return out


def match_rows(outcomes, truth):
    """-> {stamp: {'decoded': bool, 'snr': int|None, 'extra': int}}. The decode nearest to the true frequency within TOL_HZ is the row's decode; others are extra."""
    res = {}
    for s, f, _n in truth:
        dec = outcomes.get(s, [])
        near = sorted((abs(fr - f), snr) for fr, snr in dec if abs(fr - f) <= TOL_HZ)
        res[s] = {"decoded": bool(near), "snr": near[0][1] if near else None, "extra": len(dec) - (1 if near else 0)}
    return res


def live_rows(matched_rows):
    """S1_matched.csv dict rows -> {stamp: {'decoded': bool, 'snr': int|None}} for appraiser OpenWSFZ, scenario S1."""
    out = {}
    for r in matched_rows:
        if r["scenario_id"] == "S1" and r["appraiser"] == "OpenWSFZ":
            ok = r["matched"] == "True"
            out[stamp_of(r["cycle_utc"])] = {"decoded": ok, "snr": int(round(float(r["reported_snr_db"]))) if ok and r["reported_snr_db"] != "" else None}
    return out


def same_rows(a, b):
    """exact equality of decoded sets and SNRs on the stamps both define. -> (equal, [differing stamps])."""
    diff = [s for s in sorted(set(a) | set(b)) if (a.get(s, {}).get("decoded"), a.get(s, {}).get("snr")) != (b.get(s, {}).get("decoded"), b.get(s, {}).get("snr"))]
    return (not diff), diff


def bias(rows, truth):
    tn = {s: n for s, _f, n in truth}
    v = [rows[s]["snr"] - tn[s] for s in rows if rows[s]["decoded"]]
    return (sum(v) / len(v)) if v else None


def build_diff(m, f):
    """rows decoded by both builds with a different SNR -> list of stamps."""
    return [s for s in sorted(m) if m[s]["decoded"] and f.get(s, {}).get("decoded") and m[s]["snr"] != f[s]["snr"]]


def verdict(validity_ok, sv4_ok, diff_a04, diff_a08, gap_m, gap_f):
    """pure (tested). validity_ok: SV1-SV3 all pass; sv4_ok: SV4 pass."""
    if not validity_ok:
        return "WITHHELD (SV1-SV3 failed; the differences are reported, the Architect rules)"
    if not sv4_ok:
        return "WITHHELD (SV4: a same-build repeat differs, so the 0-rows predicate cannot be read)"
    if diff_a04 or diff_a08:
        return "SR-BUILD"
    if gap_m is not None and gap_f is not None and gap_m >= BAR_DB and gap_f >= BAR_DB:
        return "SR-AUDIO"
    return "SR-NEITHER"


# ---------- I/O ----------
def lf_sha(path):
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def truth_of(audio):
    run = AUDIO[audio][1]
    return s1_truth(csv.DictReader(open(os.path.join(RES_ROOT, run, "truth.csv"), encoding="utf-8")))


def wav_dir(audio):
    return os.path.join(ART, AUDIO[audio][0], "cycle-audio")


def selection_path(audio):
    return os.path.join(OUT_RES, f"selection_{audio}.json")


def render(obj):
    return (json.dumps(obj, sort_keys=True, indent=1) + "\n").encode("utf-8")


def select():
    os.makedirs(OUT_RES, exist_ok=True)
    manifest = {}
    for audio in AUDIO:
        t = truth_of(audio)
        assert len(t) == 30, (audio, len(t))
        stamps = [s for s, _f, _n in t]
        warm = prev_stamp(stamps[0])
        have = set(f[:-4] for f in os.listdir(wav_dir(audio)) if f.endswith(".wav"))
        assert warm in have and all(s in have for s in stamps), f"{audio}: a WAV is missing"
        assert warm not in stamps
        data = render({"note": f"S1-SNR-REPLAY audio set {audio}", "run": audio, "runs": {audio: {"warmup": warm, "A": stamps}}})
        with open(selection_path(audio), "wb") as fh:
            fh.write(data)
        manifest[audio] = {"file": os.path.basename(selection_path(audio)), "sha256_lf": hashlib.sha256(data).hexdigest(), "cycles": len(stamps), "warmup": warm}
    with open(os.path.join(OUT_RES, "selection_manifest.json"), "wb") as fh:
        fh.write(render(manifest))
    print(json.dumps(manifest, indent=1, sort_keys=True))
    return 0


def cell_dir(cell):
    return os.path.join(OUT_ART, cell)


def run_cell(cell):
    audio, build, nhard = CELLS[cell]
    b = BUILDS[build]
    d = cell_dir(cell)
    os.makedirs(d, exist_ok=True)
    f = {k: os.path.join(d, f"{k}.{e}") for k, e in (("run", "csv"), ("log", "log"), ("outcomes", "csv"), ("abandon", "csv"))}
    for p in f.values():
        if os.path.exists(p):
            os.remove(p)
    dll = os.path.join(b["dir"], "libft8.dll")
    harness = os.path.join(b["dir"], "Replay81.dll")
    start = (sha(dll), sha(harness))
    cmd = ["dotnet", harness, "--selection", selection_path(audio), "--run", audio, "--stratum", "A", "--wav-root", ART, "--wav-dir", wav_dir(audio),
           "--out", f["run"], "--log", f["log"], "--mode", "two1", "--threads", THREADS, "--nhard", str(nhard)]
    if b["sign_flag"]:
        cmd += ["--osd-sign-fix", "1"]
    cmd += ["--label", f"s1snr:{cell}", "--outcomes", f["outcomes"], "--abandon-out", f["abandon"]]
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True).returncode
    end = (sha(dll), sha(harness))
    log = open(f["log"], encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(f["log"]) else []
    rb = [(m.group(1), int(m.group(2))) for ln in log for m in [READBACK_RE.search(ln)] if m]
    rec = {"cell": cell, "audio": audio, "build": build, "nhard": nhard, "rc": rc, "dll_start": start[0], "dll_end": end[0], "harness_start": start[1], "harness_end": end[1],
           "readbacks": rb, "pins_ok": start == end == (b["dll"], b["harness"])}
    json.dump(rec, open(os.path.join(d, "process.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(rec, sort_keys=True), flush=True)
    return rec


def run_all():
    os.makedirs(OUT_ART, exist_ok=True)
    for audio in AUDIO:
        assert lf_sha(selection_path(audio)) == json.load(open(os.path.join(OUT_RES, "selection_manifest.json")))[audio]["sha256_lf"], f"{audio}: selection differs from its manifest"
    for cell in CELLS:
        if os.path.exists(os.path.join(cell_dir(cell), "process.json")):
            continue
        rec = run_cell(cell)
        if rec["rc"] != 0 or not rec["pins_ok"]:
            print("STOP: a cell failed validity", cell)
            return 3
    return 0


def load_cell(cell):
    audio = CELLS[cell][0]
    d = cell_dir(cell)
    out = parse_outcomes(open(os.path.join(d, "outcomes.csv"), encoding="utf-8").read().splitlines()) if os.path.exists(os.path.join(d, "outcomes.csv")) else {}
    return match_rows(out, truth_of(audio)), json.load(open(os.path.join(d, "process.json")))


def rows():
    cells, procs, truth = {}, {}, {a: truth_of(a) for a in AUDIO}
    for c in CELLS:
        if not os.path.exists(os.path.join(cell_dir(c), "process.json")):
            print("not all cells have run:", c)
            return 1
        cells[c], procs[c] = load_cell(c)
    res = {"cells": CELLS, "validity": {}}
    v = res["validity"]
    v["SV1"] = {"ok": all(procs[c]["rc"] == 0 and procs[c]["pins_ok"] and all(nh == CELLS[c][2] for _w, nh in procs[c]["readbacks"]) and len(procs[c]["readbacks"]) >= 2 for c in CELLS)}
    for name, cell, audio in (("SV2", "A04.M", "A04"), ("SV3", "A08.F", "A08")):
        live = live_rows(csv.DictReader(open(os.path.join(RES_ROOT, AUDIO[audio][1], "S1_matched.csv"), encoding="utf-8")))
        eq, diff = same_rows(cells[cell], live)
        v[name] = {"ok": eq, "differing_stamps": diff, "live_decoded": sum(1 for x in live.values() if x["decoded"]), "replay_decoded": sum(1 for x in cells[cell].values() if x["decoded"])}
    eq4, d4 = same_rows(cells["A04.M"], cells["A04.M.rep"])
    v["SV4"] = {"ok": eq4, "differing_stamps": d4}
    t04, t08 = truth["A04"], truth["A08"]
    b = {c: bias(cells[c], truth[CELLS[c][0]]) for c in CELLS}
    res["bias_db"] = b
    diff04, diff08 = build_diff(cells["A04.M"], cells["A04.F"]), build_diff(cells["A08.M"], cells["A08.F"])
    res["rows_with_different_snr_between_builds"] = {"A04": diff04, "A08": diff08}
    gap_m = None if b["A08.M"] is None or b["A04.M"] is None else b["A08.M"] - b["A04.M"]
    gap_f = None if b["A08.F"] is None or b["A04.F"] is None else b["A08.F"] - b["A04.F"]
    res["gap_A08_minus_A04_db"] = {"M": gap_m, "F": gap_f}
    validity_ok = v["SV1"]["ok"] and v["SV2"]["ok"] and v["SV3"]["ok"]
    res["verdict"] = verdict(validity_ok, v["SV4"]["ok"], diff04, diff08, gap_m, gap_f)
    res["decode_differences_between_builds"] = {a: [s for s in cells[f"{a}.M"] if cells[f"{a}.M"][s]["decoded"] != cells[f"{a}.F"][s]["decoded"]] for a in ("A04", "A08", "A0929", "A1002", "A1003")}
    res["extra_decodes_per_cell"] = {c: sum(r["extra"] for r in cells[c].values()) for c in CELLS}
    dist = {}
    for c in CELLS:
        tn = {s: n for s, _f, n in truth[CELLS[c][0]]}
        sh = [r["snr"] - tn[s] for s, r in cells[c].items() if r["decoded"]]
        dist[c] = {"decoded": len(sh), "min": min(sh) if sh else None, "median": statistics.median(sh) if sh else None, "max": max(sh) if sh else None,
                   "mean": (sum(sh) / len(sh)) if sh else None}
    res["reported_minus_true_db"] = dist
    os.makedirs(OUT_RES, exist_ok=True)
    json.dump(res, open(os.path.join(OUT_RES, "s1_snr_replay_result.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: res[k] for k in ("validity", "bias_db", "rows_with_different_snr_between_builds", "gap_A08_minus_A04_db", "verdict")}, indent=1, sort_keys=True))
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "select":
        return select()
    if cmd == "plan":
        print("\n".join(f"{c}: audio {a}, build {b}, nhard {n}" for c, (a, b, n) in CELLS.items()))
        return 0
    if cmd == "run":
        return run_all()
    if cmd == "rows":
        return rows()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
