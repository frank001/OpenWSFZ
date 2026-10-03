"""#122 gate 4a diagnostics D1 (arm F on P) then D2 (arm T on P), POST-REGISTRATION, fresh process each, same child list and order.
D3 (booleans and counts for stamp 261001_112700) is computed inside both. Needs EXCLUSIVE PC time and the Captain's slot:
D1 is about 10 min, D2 about 65 min. Do not start without both.

  python qa/rr-study/trunc-replay/run_diag.py [F|T]      # default: F then T; pass F to run D1 only
  then: python qa/rr-study/trunc-replay/compare_diag.py

Outputs under _out/diag/p/ (gitignored): trunc_<arm>.csv, outcomes_<arm>.csv, diag_<arm>.csv, log_<arm>.txt, exit_<arm>.txt.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEL = REPO / "qa/rr-study/results/2026-10-03-122-gate4a-truncation-replay/selection_p.json"
OUT = HERE / "_out" / "diag" / "p"
EXE = HERE / "_out" / "bin" / "Replay81.exe"
FOLDER = REPO / "artefacts" / "20260930_1930_endurance_run-gathered"
DIAG_STAMP, DIAG_FREQ = "261001_112700", "1731"


def main() -> int:
    arms = sys.argv[1:] or ["F", "T"]
    shas = json.loads((SEL.parent / "selection_shas.json").read_text(encoding="utf-8"))
    if hashlib.sha256(SEL.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != shas["p"]:
        print("selection SHA mismatch"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    run = json.loads(SEL.read_text(encoding="utf-8"))["run"]
    for arm in arms:
        cmd = [str(EXE), "--selection", str(SEL), "--run", run, "--stratum", "ALL", "--mode", "trunc", "--arm", arm,
               "--wav-root", str(REPO / "artefacts"), "--wav-dir", str(FOLDER / "owsfz/wav"),
               "--out", str(OUT / f"harness_{arm}.csv"), "--log", str(OUT / f"log_{arm}.txt"),
               "--trunc-out", str(OUT / f"trunc_{arm}.csv"), "--outcomes", str(OUT / f"outcomes_{arm}.csv"),
               "--ws-alltxt", str(FOLDER / "wsjt-x/ALL.TXT"), "--early-outcomes", "true",
               "--diag-stamp", DIAG_STAMP, "--diag-freq", DIAG_FREQ, "--diag-out", str(OUT / f"diag_{arm}.csv"),
               "--label", f"gate4a-diag-{arm}"]
        print("RUN diag", arm, flush=True)
        rc = subprocess.run(cmd).returncode
        (OUT / f"exit_{arm}.txt").write_text(f"{rc}\n")
        print("EXIT diag", arm, rc, flush=True)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
