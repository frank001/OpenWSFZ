"""#122 gate 4a driver: runs the eight arms in the spec's order (P-F, P-T, R-F, R-T, X17-F, X17-T, X80-F, X80-T),
ONE process at a time, each a fresh process. Needs ~3 h of EXCLUSIVE PC time: do not start it without the Captain's go
and QA's confirmation of the slot (decode times are measured; no suites, builds or daemons meanwhile).

Build (once, before the slot, from the checkout whose SHA is recorded in the report):
  dotnet build qa/rr-study/sub-feas/replay81/Replay81.csproj -c Release -p:HasSubfeas=true -p:HasTwoStage=true \
      -p:HasMaxThreads=true -o qa/rr-study/trunc-replay/_out/bin

Run detached (HK-023) and tail the log (HK-019: afterwards run the orphan check at the bottom of this docstring):
  nohup python qa/rr-study/trunc-replay/run_trunc.py > qa/rr-study/trunc-replay/_out/driver.log 2>&1 & disown
Orphan check: no Replay81 process may remain (Get-Process Replay81).

Resumable: a cycle is done only once its 'final' row exists, so re-running continues an interrupted arm.
Writes, per corpus under _out/<corpus>/: trunc_<arm>.csv, outcomes_<arm>.csv, log_<arm>.txt, exit_<arm>.txt,
selection_sha_<arm>.txt (the SHA of the list the arm actually read). Counts and numbers only (HK-037).
"""
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEL = REPO / "qa/rr-study/results/2026-10-03-122-gate4a-truncation-replay"
OUT = HERE / "_out"
EXE = OUT / "bin" / "Replay81.exe"
ART = REPO / "artefacts"
WAVS = {  # corpus -> (artefact folder)
    "p": "20260930_1930_endurance_run-gathered",
    "r": "20260922_2056_endurance_run-gathered",
    "x17": "20260808_live_run_1154-8080-17m",
    "x80": "20260809_live_run_0155-8080-80m",
}


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    if not EXE.exists():
        print("build first:", EXE); return 2
    for c, folder in WAVS.items():
        d = OUT / c
        d.mkdir(parents=True, exist_ok=True)
        sel = SEL / f"selection_{c}.json"
        import json
        run = json.loads(sel.read_text(encoding="utf-8"))["run"]
        for arm in ("F", "T"):
            (d / f"selection_sha_{arm}.txt").write_text(lf_sha(sel) + "\n")
            cmd = [str(EXE), "--selection", str(sel), "--run", run, "--stratum", "ALL", "--mode", "trunc", "--arm", arm,
                   "--wav-root", str(ART), "--wav-dir", str(ART / folder / "owsfz/wav"), "--out", str(d / f"harness_{arm}.csv"),
                   "--log", str(d / f"log_{arm}.txt"), "--trunc-out", str(d / f"trunc_{arm}.csv"),
                   "--outcomes", str(d / f"outcomes_{arm}.csv"), "--ws-alltxt", str(ART / folder / "wsjt-x/ALL.TXT"),
                   "--label", f"gate4a-{c}-{arm}"]
            print("RUN", c, arm, flush=True)
            rc = subprocess.run(cmd).returncode
            (d / f"exit_{arm}.txt").write_text(f"{rc}\n")
            print("EXIT", c, arm, rc, flush=True)
            if rc != 0:
                return rc   # stop at the first failure; the report names the row (spec section 5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
