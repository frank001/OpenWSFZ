"""#122 gate 4a -- freeze the four cycle lists BEFORE any decode (spec section 3).

Run once, commit the output, then never change it except by a dated amendment.

  P   : parent 10-01 selection.json (SHA-256 over LF-normalised bytes pinned below), keep index % 4 == 0.
  R   : 2026-09-22 night, every R0-passing WAV except the first and last stamps, ascending, then index % 4 == 0.
  X17 : 2026-08-08 17 m (8080 folder), same rule as R.
  X80 : 2026-08-09 80 m (8080 folder), same rule as R.

R0 per file (header only): 12 kHz, mono, 16-bit, 180 000 samples. No cycle is excluded on its content.
Prints stamps' COUNTS only. Run from the repository root.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

PARENT = Path("qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/selection.json")
PARENT_SHA = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"
OUT = Path("qa/rr-study/results/2026-10-03-122-gate4a-truncation-replay")
ART = Path("artefacts")
STEP = 4
CORPORA = {
    "r": ("20260922_2056_endurance_run-gathered", "owsfz/wav", "wsjt-x/ALL.TXT"),
    "x17": ("20260808_live_run_1154-8080-17m", "owsfz/wav", "wsjt-x/ALL.TXT"),
    "x80": ("20260809_live_run_0155-8080-80m", "owsfz/wav", "wsjt-x/ALL.TXT"),
}
PCM_SAMPLES, RATE = 180_000, 12_000
SHAS: dict[str, str] = {}


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def r0_ok(path: Path) -> bool:
    b = path.read_bytes()
    if len(b) < 44 or b[0:4] != b"RIFF" or b[8:12] != b"WAVE":
        return False
    pos, ch, rate, bits, data_len = 12, 0, 0, 0, -1
    while pos + 8 <= len(b):
        cid, ln = b[pos:pos + 4], struct.unpack_from("<i", b, pos + 4)[0]
        if cid == b"fmt ":
            ch, rate, bits = struct.unpack_from("<h", b, pos + 10)[0], struct.unpack_from("<i", b, pos + 12)[0], struct.unpack_from("<h", b, pos + 22)[0]
        elif cid == b"data":
            data_len = ln
            break
        pos += 8 + ln + (ln & 1)
    return ch == 1 and rate == RATE and bits == 16 and data_len // 2 == PCM_SAMPLES


def write(name: str, run: str, stamps: list[str], warmup: str, extra: dict) -> None:
    doc = {"spec": "qa/rr-study/2026-10-03-1015-architect-to-qa-spec-122-gate4a-truncation-replay.md section 3",
           "run": run, "step": STEP, "runs": {run: {"ALL": stamps, "warmup": warmup}}, **extra}
    p = OUT / name
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    SHAS[name[len("selection_"):-len(".json")]] = lf_sha(p)
    print(f"{name}: {len(stamps)} cycles, SHA-256(LF) {lf_sha(p)}")


def main() -> int:
    if lf_sha(PARENT) != PARENT_SHA:
        print("PARENT SHA MISMATCH", lf_sha(PARENT)); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    par = json.loads(PARENT.read_text(encoding="utf-8"))
    run = par["run"]
    allc = par["runs"][run]["ALL"]
    missing = [s for s in allc[::STEP] if not (ART / "20260930_1930_endurance_run-gathered/owsfz/wav" / f"{s}.wav").exists()]
    if missing:
        print("P: WAVs missing:", len(missing)); return 2
    write("selection_p.json", run, allc[::STEP], par["runs"][run]["warmup"], {"parent_sha256_lf": PARENT_SHA, "parent_count": len(allc)})
    for key, (folder, wavdir, _) in CORPORA.items():
        d = ART / folder / wavdir
        files = sorted(d.glob("*.wav"))
        ok = [f.stem for f in files if r0_ok(f)]
        failed = len(files) - len(ok)
        trimmed = ok[1:-1]
        write(f"selection_{key}.json", folder, trimmed[::STEP], ok[0],
              {"wav_files": len(files), "r0_failed": failed, "first_stamp_excluded": ok[0], "last_stamp_excluded": ok[-1], "trimmed_count": len(trimmed)})
    (OUT / "selection_shas.json").write_text(json.dumps(SHAS, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
