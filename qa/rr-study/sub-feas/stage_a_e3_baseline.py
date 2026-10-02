#!/usr/bin/env python
"""SUB-FEAS Stage B: the Stage A E3 baseline (tasks.md 15.2), measured BEFORE any Stage B build.

E3 (Architect spec, Stage B rows): total residualDecodes(B) >= 0.98 x residualDecodes(A) on the E1 cycles, no
deadline. This script produces the (A) side: the Stage A candidate (ca0bcd9b, libft8.dll ee00d118...) run through the
section 8.1 harness on the 161 E1 cycles (e1_selection.json, frozen c40fc850) at the DEFAULT thread count (auto = 14 on
this machine), flag ON. "No deadline" is established the only way it can be here: the decoder's own 13 s budget still
applies, so the run ASSERTS that 0 of the 161 residual passes were deadline-abandoned; a pass that finished inside its
budget equals the unbounded result. Any abandon invalidates the baseline and the affected cycles must be re-run.

Method: the harness selects cycles by stratum name from a selection file, so a derived selection is written with the
161 E1 cycles as one stratum "E1" per run (plus the frozen warm-up stamp). The derived file is a gitignored artefact
and is fully reproducible from the two frozen inputs, whose SHA-256 are asserted.

HK-037 / NFR-021: stamps, integers and timings only. WSJT-X must be closed (asserted). Output paths untracked (asserted).
"""
import collections
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_run as R
import replay81_rows as B

REPO = R.REPO
ART = R.ART
OUT = os.path.join(ART, "sub_feas_stage_a_e3_baseline")
SEL81 = R.SELECTION
SEL81_SHA = R.SELECTION_SHA256
E1SEL = os.path.join(REPO, "qa", "rr-study", "results", "2026-09-30-sub-feas-speed-e1", "e1_selection.json")
E1SEL_SHA = "f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2"
CAND_OUT = r"C:\Users\Frank\w-speed-out-ca0bcd9b"
CAND_DLL_SHA = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"
RUNS = R.RUNS
RESULTS_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-09-30-sub-feas-stage-b-baseline")


def sha(path):
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    assert subprocess.run(["git", "check-ignore", "-q", os.path.join(OUT, "x")], cwd=REPO).returncode == 0
    assert subprocess.run(["git", "ls-files", "--", OUT], cwd=REPO, capture_output=True, text=True).stdout.strip() == ""
    assert R.sha256(SEL81) == SEL81_SHA, "section 8.1 selection.json changed"
    assert sha(E1SEL) == E1SEL_SHA or R.sha256(E1SEL) == E1SEL_SHA, "e1_selection.json changed"
    assert R.sha256(os.path.join(CAND_OUT, "libft8.dll")) == CAND_DLL_SHA, "candidate DLL pin mismatch"
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "qa/rr-study/sub-feas/stage_a_e3_baseline.py",
                            "qa/rr-study/sub-feas/replay81"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert dirty == "", "script/harness not committed"
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "(Get-Process | Where-Object { $_.ProcessName -match '^(wsjtx|jt9|OpenWSFZ)' } | "
                         "Select-Object -ExpandProperty ProcessName) -join ','"], capture_output=True, text=True).stdout.strip()
    assert ps == "", ("WSJT-X / jt9 / OpenWSFZ is running", ps)

    sel = json.load(open(SEL81, encoding="utf-8"))
    e1 = json.load(open(E1SEL, encoding="utf-8"))
    derived = {"runs": {}}
    per_run = collections.defaultdict(list)
    for c in e1["cycles"]:
        per_run[c["run"]].append(c["stamp"])
    for run in RUNS:
        derived["runs"][run] = {"warmup": sel["runs"][run]["warmup"], "E1": sorted(per_run[run])}
    assert sum(len(v["E1"]) for v in derived["runs"].values()) == 161
    dsel = os.path.join(OUT, "e1_derived_selection.json")
    json.dump(derived, open(dsel, "w"), indent=1, sort_keys=True)

    log = open(os.path.join(OUT, "orchestrator.log"), "a", encoding="utf-8")
    result = {"e1_selection_sha256": E1SEL_SHA, "selection81_sha256": SEL81_SHA, "cand_dll_sha256": CAND_DLL_SHA,
              "harness_dll_sha256": R.sha256(os.path.join(CAND_OUT, "Replay81.dll")),
              "script_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
              "runs": {}}
    tot_res = tot_lines = tot_ab = tot_cont = tot_av = 0
    per_cycle = {}
    for run in RUNS:
        tag = f"e3_{run}"
        csvp = os.path.join(OUT, tag + ".csv")
        logp = os.path.join(OUT, tag + ".log")
        for p in (csvp, logp):
            if os.path.exists(p):
                os.remove(p)  # a fresh baseline: never resume into a stale file
        cmd = ["dotnet", os.path.join(CAND_OUT, "Replay81.dll"), "--selection", dsel, "--run", run, "--stratum", "E1",
               "--wav-root", ART, "--out", csvp, "--log", logp, "--mode", "alt", "--label", f"ca0bcd9b:{tag}"]
        rc = subprocess.run(cmd, capture_output=True, text=True).returncode
        line = f"{R.now()} {tag} rc={rc}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
        assert rc == 0, f"harness {tag} rc={rc}"
        rows = B.read_rows(csvp)
        sub, av, cw, other = B.parse_log(logp)
        on = sorted([r for r in rows if r["flag"] == "ON"], key=lambda r: r["seq"])
        assert len(on) == len(derived["runs"][run]["E1"]), (run, len(on))
        assert len(sub) == len(on), ("Sub-feas log lines != ON cycles", run, len(sub), len(on))
        for o, s in zip(on, sub):
            per_cycle[f"{run}|{o['stamp']}"] = {"residual": s["residual"], "abandoned": s["abandoned"],
                                                "contained": s["contained"], "fitted": s["fitted"], "on_ms": o["elapsed_ms"]}
        res = sum(s["residual"] for s in sub)
        ab = sum(1 for s in sub if s["abandoned"])
        co = sum(1 for s in sub if s["contained"])
        result["runs"][run] = {"cycles": len(on), "residualDecodes_total": res, "abandoned": ab, "contained_lines": co,
                               "av_warnings": av, "contained_warnings": cw, "rows_with_exception": sum(1 for r in rows if r["exception"]),
                               "on_ms_max": max(r["elapsed_ms"] for r in on), "other_warning_templates": dict(other)}
        tot_res += res
        tot_lines += len(sub)
        tot_ab += ab
        tot_cont += co
        tot_av += av
    result["total"] = {"cycles": tot_lines, "residualDecodes_total": tot_res, "abandoned": tot_ab,
                       "contained_lines": tot_cont, "av_warnings": tot_av}
    result["valid_as_no_deadline_baseline"] = (tot_lines == 161 and tot_ab == 0 and tot_cont == 0 and tot_av == 0)
    result["per_cycle"] = per_cycle
    json.dump(result, open(os.path.join(OUT, "e3_baseline.json"), "w"), indent=1, sort_keys=True)
    json.dump(result, open(os.path.join(RESULTS_DIR, "e3_baseline.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in result.items() if k != "per_cycle"}, indent=1))
    return 0 if result["valid_as_no_deadline_baseline"] else 1


if __name__ == "__main__":
    sys.exit(main())
