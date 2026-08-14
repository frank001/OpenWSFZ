#!/usr/bin/env python3
"""M0 -- preserve the evidence. Implements
`2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md` SS2 verbatim.

No playback, no `src/` touch, no CPU load -- pure file copy plus an inventory refresh. The
Architect flagged this as the one step worth doing "regardless", before any decision on
M1-M4, since the WSJT-X per-decode record for all five of tonight's runs lives in exactly
one place outside the repo (`WSJT-X - FT991A\\ALL.TXT`, an all-time accumulating log) and a
clear/rotate/profile-reset of that file would make the experiment unreproducible.

NFR-021: this script only ever touches whole files (copy) or file metadata (size, mtime) --
it never opens, greps, or parses ALL.TXT content, so no message text or callsign is ever
read into this process.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # HK-009
except AttributeError:
    pass

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay"
WSJTX_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
OUT_DIR = REPO_ROOT / "artefacts" / "20260806_cross_decode_replay_2009"
RUN_INDICES = [1, 2, 3, 4, 5]
SPEC_COMMIT = "98db57b"


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] M0: {msg}", flush=True)


def git_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=10, check=True)
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def run() -> dict:
    if not WSJTX_ALL_TXT.exists():
        raise RuntimeError(f"M0 FATAL: {WSJTX_ALL_TXT} does not exist -- cannot preserve "
                            f"evidence that isn't there. Nothing was copied.")

    missing = []
    for i in RUN_INDICES:
        for fname in ("our_ALL.TXT", "pass_windows.json", "daemon_stdout.log"):
            p = SRC_DIR / "_work" / f"run{i}" / fname
            if not p.exists():
                missing.append(str(p))
    for fname in [f"summary_run{i}.json" for i in RUN_INDICES] + ["full_anova_summary.json"]:
        p = SRC_DIR / fname
        if not p.exists():
            missing.append(str(p))
    if missing:
        raise RuntimeError("M0 FATAL: expected source file(s) missing, nothing copied:\n  "
                            + "\n  ".join(missing))

    st = WSJTX_ALL_TXT.stat()
    src_size = st.st_size
    src_mtime_utc = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)  # idempotent -- a re-run overwrites in place
    (OUT_DIR / "wsjtx-all-time").mkdir(parents=True, exist_ok=True)
    shutil.copy2(WSJTX_ALL_TXT, OUT_DIR / "wsjtx-all-time" / "ALL.TXT")
    log(f"copied {WSJTX_ALL_TXT} ({src_size} bytes, mtime {src_mtime_utc.isoformat()}) "
        f"-> {OUT_DIR / 'wsjtx-all-time' / 'ALL.TXT'}")

    run_windows = {}
    for i in RUN_INDICES:
        src_run = SRC_DIR / "_work" / f"run{i}"
        dst_run = OUT_DIR / f"run{i}"
        dst_run.mkdir(parents=True, exist_ok=True)
        for fname in ("our_ALL.TXT", "pass_windows.json", "daemon_stdout.log"):
            shutil.copy2(src_run / fname, dst_run / fname)
        import json
        pw = json.loads((dst_run / "pass_windows.json").read_text(encoding="utf-8"))
        run_windows[f"run{i}"] = pw
        log(f"copied run{i}/{{our_ALL.TXT, pass_windows.json, daemon_stdout.log}}")

    for fname in [f"summary_run{i}.json" for i in RUN_INDICES] + ["full_anova_summary.json"]:
        shutil.copy2(SRC_DIR / fname, OUT_DIR / fname)
    log("copied summary_run1..5.json + full_anova_summary.json")

    readme = OUT_DIR / "README.md"
    lines = [
        "# 20260806 cross-decode replay -- preserved evidence (M0)",
        "",
        f"**Preserved:** {utc_stamp()} (`date -u` equivalent, per HK-017).",
        f"**Repo `main` at spec time:** `{SPEC_COMMIT}` "
        f"(`2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`). "
        f"**Repo `main` at preservation time:** `{git_head()}`.",
        "",
        "Implements SS2 of the reference-suppression M0-M4 spec verbatim. This directory is "
        "a point-in-time snapshot of tonight's (2026-08-06) five-run live cross-decode "
        "replay ANOVA series, taken because every per-decode WSJT-X record from all five "
        "runs lived in exactly one place outside the repo before this copy existed.",
        "",
        "## Source paths",
        "",
        f"- `{WSJTX_ALL_TXT}` -- **WSJT-X's all-time accumulating ALL.TXT, NOT a per-session "
        f"log.** It carries every decode WSJT-X has ever logged under the FT991A profile, "
        f"not just tonight's five runs. Size at preservation: **{src_size} bytes**. "
        f"`LastWriteTimeUtc` at preservation: **{src_mtime_utc.isoformat()}**. A later "
        f"divergence in either figure means this file kept growing (or was touched) after "
        f"this snapshot was taken -- compare against those two numbers before trusting a "
        f"fresh read of the live file for anything M1/M2 already concluded from this copy.",
        f"- `{SRC_DIR.relative_to(REPO_ROOT)}/_work/run{{1..5}}/` -- each run's own "
        f"`our_ALL.TXT` (OpenWSFZ), `pass_windows.json` (pass1/pass2 UTC start/end), "
        f"`daemon_stdout.log`.",
        f"- `{SRC_DIR.relative_to(REPO_ROOT)}/summary_run{{1..5}}.json`, "
        f"`full_anova_summary.json` -- committed, aggregate-only (counts, mean/median "
        f"deltas; no per-decode rows, verified before this script was written).",
        "",
        "## Five runs' pass-1 (WSJT-X-source) windows, UTC",
        "",
        "| run | pass1 start | pass1 end |",
        "|---|---|---|",
    ]
    for i in RUN_INDICES:
        p1 = run_windows[f"run{i}"].get("pass1_wsjtx_source", [None, None])
        lines.append(f"| {i} | {p1[0]} | {p1[1]} |")
    lines += [
        "",
        "## Privacy (NFR-021)",
        "",
        "`wsjtx-all-time/ALL.TXT` and every `run*/our_ALL.TXT` contain real callsigns. This "
        "directory lives under `artefacts/`, which is git-ignored (`.gitignore:105`) -- "
        "verified before this script ran. Nothing in this directory is to be committed.",
        "",
        "## Regenerated by",
        "",
        f"`{Path(__file__).relative_to(REPO_ROOT)}` "
        f"(`qa/cycleframer-alignment-replay/2026-08-07-reference-suppression-m0-m4/`).",
        "",
    ]
    readme.write_text("\n".join(lines), encoding="utf-8")
    log(f"wrote {readme}")

    return {
        "out_dir": str(OUT_DIR),
        "wsjtx_all_txt_src_size": src_size,
        "wsjtx_all_txt_src_mtime_utc": src_mtime_utc.isoformat(),
        "run_windows": run_windows,
    }


def regenerate_inventory() -> None:
    log("regenerating qa/ARTEFACT_INVENTORY.md")
    subprocess.run([sys.executable, str(REPO_ROOT / "qa" / "artefact_inventory.py")],
                    cwd=REPO_ROOT, check=True)
    check = subprocess.run([sys.executable, str(REPO_ROOT / "qa" / "artefact_inventory.py"),
                             "--check"], cwd=REPO_ROOT)
    if check.returncode != 0:
        raise RuntimeError("M0 FATAL: qa/ARTEFACT_INVENTORY.md is stale immediately after "
                            "regeneration -- artefact_inventory.py itself may be broken.")
    log("inventory regenerated and confirmed fresh (--check passed)")


def main() -> int:
    result = run()
    regenerate_inventory()
    log(f"M0 COMPLETE. Evidence preserved at {result['out_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
