"""Assemble the final report.md of a baseline run (HK-001 sections 1, 5, 6 + the #194 sections).

    python baseline_assemble_report.py <run-dir> --role baseline|confirmation --other <other-run-dir>

Keeps the analyser's own body unedited (a copy is saved as report.analyser-original.md), corrects the header
(the analyser's 'OpenWSFZ SHA' is the QA tooling HEAD, HK-022), and adds, in this order: Section 1, the
analyser body, the Captured-audio scan (#194) section (quoted verbatim from scan_report.md), the S3c
section (quoted from s3c_report.md + the Architect's required statements), Section 5, Section 6 (the last
report's table carried forward, footnotes 1-18 verbatim, two rows added). Counts and rates only (NFR-021).
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
PRIOR = RESULTS / "2026-09-29-0d6b193-ON" / "report.md"
BUILD = "cddd7e340d922abddefbbe1dc9ff35e76ec93e7d"
DLL = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c"

ROWS = {  # from each run's own files (baseline_row.py + the Study Metrics tables)
    "2026-10-02-96077a0": ("2026-10-02", "run 1 (baseline)", "0.14%", "0.0%", "0.51%", "0.0% / 0.0%", "95.35% / 79.53%",
                           "91.67% / 91.67%", "86.92%"),
    "2026-10-03-96077a0": ("2026-10-03", "run 2 (confirmation)", "0.19%", "0.0%", "0.71%", "0.0% / 0.0%",
                           "99.07% / 82.79%", "93.33% / 91.67%", "86.62%"),
}


def quote(path: Path, start: str, stop: str | None = None) -> str:
    t = path.read_text(encoding="utf-8")
    i = t.index(start)
    j = t.index(stop, i + 1) if stop else len(t)
    return t[i:j].rstrip() + "\n"


def scan_section(run: Path) -> str:
    sr = run / "captured-audio-scan" / "scan_report.md"
    t = sr.read_text(encoding="utf-8")
    head = quote(sr, "## Headline (plain words)", "## Validation rows")
    rows = list(csv.DictReader(open(run / "captured-audio-scan" / "flagged_slots.csv", encoding="utf-8")))
    by = Counter((r["scenario"], r["class"]) for r in rows)
    slots = len({r["slot"] for r in rows})
    scen = sorted({k[0] for k in by})
    cls = ["BOTH", "CROSS", "OWSFZ-ONLY", "WSJTX-ONLY"]
    tbl = ["| scenario | " + " | ".join(cls) + " |", "|---|" + "---:|" * len(cls)]
    for s in scen:
        tbl.append(f"| {s} | " + " | ".join(str(by.get((s, c), 0)) for c in cls) + " |")
    runlvl = quote(sr, "### Run-level lines (A11)", "## Descriptive: run-level timing offset")
    frz = re.search(r"- Frozen `thresholds.json`.*", t).group(0)
    tool = re.search(r"- Tool: .*", t).group(0)
    return (
        "## Captured-audio scan (#194)\n\n"
        "This section is quoted from `captured-audio-scan/scan_report.md` of THIS run. The scan ran after the gather, "
        "was not SKIPPED, and found no decoder defect by construction: a WAV is recorded before either decoder runs.\n\n"
        f"- Scan commit/freeze: `eng/194-scan` (`d06b01d9`, on `main` since `b87529a3`); harness commit `96077a0f` (QA tooling HEAD, "
        f"branch `qa/baseline-194`).\n{frz}\n{tool}\n\n"
        f"- Flagged slots: **{slots}** distinct slots of 407 scanned per side ({len(rows)} slot-family findings).\n\n"
        + "\n".join(tbl) + "\n\n"
        + "### Headline, quoted verbatim\n\n" + head.replace("## Headline (plain words)\n", "") + "\n"
        + "### Run-level line, quoted verbatim\n\n" + runlvl + "\n"
        "Reading: every `g_db` run-level offset is within +-0.05 dB of the calibration median (limit 0.5 dB): no `RUN-LEVEL` "
        "event, so the chain's level was stable for the whole run. The scan carries its holes: it cannot see a short added "
        "sound or a click in the groups above range.\n"
    )


def s3c_section(run: Path) -> str:
    body = quote(run / "s3c" / "s3c_report.md", "- Flag state").replace("\n## Rows", "\n### Rows")
    return (
        "## S3c start-time edge guard (#194 part B step 2)\n\n" + body + "\n"
        "### Statements required by the Architect (ruling 2026-10-02 2225 and message of 2026-10-03)\n\n"
        "- **S3c-E50 (E -2.00) detects a COLLAPSE of the early transition** (14/32 in the edge run down to <= 3/32), "
        "not a shift of one grid step: OpenWSFZ's r_ref there is 0.28, so k* = 4.\n"
        "- **The late side's only live guard is L +2.75** (S3c-L90). The L +3.00 row has r_ref 0 for both decoders, so k* = 0: it "
        "cannot fail and is DESCRIPTIVE.\n"
        "- **Flag direction.** This battery ran with `subtractionEnabled = true`; the reference rates come from a flag-OFF edge "
        "run. Batch 1 equals flag OFF (V4), so ON can only ADD matches, which biases S3c toward PASS. A sync-search regression "
        "could therefore be hidden only if batch 2 recovered the lost signals.\n"
        "- S3C1/S3C2 (the Architect's blind predictions) are scored at the third battery that includes S3c. This report "
        "records batteries 1 and 2 of 3: no S3c-WSJT-X FAIL and no S3c-OWSFZ FAIL in either.\n"
        "- Multiplicity (spec section 4): 4 parts x 2 decoders at 1 % each, about 8 % chance of one false FAIL per battery.\n"
    )


def section6(run_key: str) -> str:
    p = PRIOR.read_text(encoding="utf-8")
    s6 = p[p.index("## Section 6"):]
    s6 = re.sub(r"\*\*HK-031:.*?verbatim\.\*\*",
                "**HK-031: Section 6 of the last report (`2026-09-29-0d6b193-ON`, twenty-nine rows) was read in full before any "
                "analysis above; this section is that table carried forward with this baseline's two rows appended and footnotes "
                "19–22 added. Footnotes 1–18 are copied verbatim.**", s6, count=1, flags=re.S)
    lines = s6.split("\n")
    # table ends at the first blank line after the last '| **2026-09-29**' row
    last = max(i for i, l in enumerate(lines) if l.startswith("| **2026-09-29**"))
    new = []
    for key in ("2026-10-02-96077a0", "2026-10-03-96077a0"):
        d, lab, s1, s2, s3, s5, s7, s8, pooled = ROWS[key]
        mark = "**" if key == run_key else ""
        n = "19" if key.startswith("2026-10-02") else "20"
        new.append(f"| {mark}{d}{mark} | {mark}`main@cddd7e34`, flag ON, {lab}{'' if False else ''}{mark}"
                   f"{'¹⁹' if n == '19' else '²⁰'} | {s1} | {s2} | {s3} | {s5}"
                   f"{'²¹' if n == '19' else ''} | {s7} | {s8} | {pooled}{'²²'} |")
    lines[last + 1:last + 1] = new
    out = "\n".join(lines).rstrip() + "\n\n"
    out += (
        "¹⁹ `main` `cddd7e34` (src identical to `b87529a3`; docs-only commits since), `libft8.dll` SHA-256 `" + DLL[:16] + "...`, "
        "shim 20260056, published with `tools/publish_selfcontained.py`; `subtractionEnabled` true read back, nhard 40, both "
        "migration markers true. **This starts the flag-ON `main` series** (the 2026-09-29 flag-ON row is a different build "
        "lineage, shim 20260055). Never pool with flag-OFF rows. Run 1 is the BASELINE.\n\n"
        "²⁰ Run 2 = the confirmation run, identical build, config, scenario list, seeds and station set-up, 01:16Z to 03:10Z "
        "(run 1: 23:16Z to 01:09Z). S7 moved by +3.7 pp (WSJT-X) and +3.3 pp (OpenWSFZ): S7 is instrument-suspect by "
        "standing rule, and the OpenWSFZ-minus-WSJT-X gap stays inside the known band (about 16 pp in both runs; do not cite a bare S7 mean).\n\n"
        "²¹ Check B (narrowband, parts 2/3): run 1 WSJT-X 1/60 (PASS, FAIL iff >= 2), OpenWSFZ 0/60; run 2 0/60 and 0/60. Gate A-W "
        "0/480 for both runs.\n\n"
        "²² Pooled S7+S8 matched decodes, OpenWSFZ as a percentage of WSJT-X: run 1 226/260, run 2 233/269 (from each run's "
        "own `S7_matched.csv`/`S8_matched.csv`).\n"
    )
    return out


def build(run_key: str, role: str, other_key: str) -> None:
    run = RESULTS / run_key
    orig = run / "report.analyser-original.md"
    if not orig.exists():
        shutil.copy2(run / "report.md", orig)
    base = orig.read_text(encoding="utf-8")
    body = base[base.index("## S1 "):]
    me, ot = ROWS[run_key], ROWS[other_key]
    header = (
        "# OpenWSFZ R&R Study Report\n\n"
        "| Field | Value |\n|---|---|\n"
        f"| Run date | {me[0]} ({me[1]}) |\n"
        f"| OpenWSFZ SHA | `{BUILD}` (the daemon build `main` `cddd7e34`; **corrected by hand, HK-022:** the analyser wrote "
        "`96077a0f4814baeba983bce2bd0ed18221838cfc`, the QA tooling HEAD on `qa/baseline-194`, fourth occurrence of this defect) |\n"
        f"| `libft8.dll` SHA-256 | `{DLL}` (shim 20260056) |\n"
        "| Flag | `decoder.subtractionEnabled = true` (read back over `GET /api/v1/config`), `osdNhardMax` 40, both migration markers true, `subtractionMaxThreads` 0 (auto) |\n"
        "| WSJT-X version | WSJT-X 2.7.0 (inferred from binary date 2025-02-04) |\n"
        f"| This run's role | {role.upper()}; the other run is `{other_key}` |\n\n"
        "> The analyser's body below is its own output, unedited (copy: `report.analyser-original.md`). Sections 1, 5 and 6, the "
        "#194 scan section and the S3c section are authored.\n\n"
    )
    s1 = (
        "## Section 1 — Study hypothesis\n\n"
        "**Purpose.** The Captain ordered a new R&R S1-S8 baseline carrying the #194 improvements: the S3c start-time edge guard "
        "in the battery and the captured-audio scan in the analysis, on `main` with subtraction ON (the flag-ON `main` series starts here), "
        "and a second run on the identical set-up to confirm it. Run 1 is the baseline, run 2 the confirmation.\n\n"
        "**Null hypotheses in scope.**\n"
        "- **H0(no harm):** every gate PASSES, S5 shows no false-positive event on AWGN slots, no daemon exception. \n"
        "- **H0(reproducible):** run 2 differs from run 1 on no headline metric by more than the series' own run-to-run variation "
        "(S1-S3 %GR&R, S5, S8; S7 is instrument-suspect).\n"
        "- **H0(S3c):** no S3c-WSJT-X validity FAIL and no S3c-OWSFZ guard FAIL.\n"
        "- **H0(chain stable):** the scan finds no `RUN-LEVEL` offset and the run has no config drift.\n\n"
        "**What actually happened.** All four hold in both runs. Overall verdict PASS twice; S5 0/120 and 0/480 (Gate A-W); Check B 1/60 "
        "and 0/60 (WSJT-X; PASS); S3c PASS in both; config drift 0 rows; scan completed, not SKIPPED, no `RUN-LEVEL` event. "
        f"Headline run 1 / run 2: S1 {ROWS['2026-10-02-96077a0'][2]} / {ROWS['2026-10-03-96077a0'][2]}, S3 {ROWS['2026-10-02-96077a0'][4]} / "
        f"{ROWS['2026-10-03-96077a0'][4]}, S8 {ROWS['2026-10-02-96077a0'][7]} / {ROWS['2026-10-03-96077a0'][7]} (WSJT-X / OpenWSFZ), pooled "
        f"OpenWSFZ-of-WSJT-X {ROWS['2026-10-02-96077a0'][8]} / {ROWS['2026-10-03-96077a0'][8]}. **The baseline is confirmed.**\n\n"
        "**Provenance.** `main` `cddd7e34`; DLL SHA-256 and shim in the header; flag read back. No `--filter` applies (a battery, not a test run). "
        "Pre-flight before run 1: chain-quiet RMS 0.000 over 12 s on B1 and a warm-up cycle decoded by both apps. Run 2 had no separate pre-flight "
        "(exception E15 of the exceptions log: the launcher starts the daemon itself); checked afterwards, only a handful of non-Q callsign-shaped "
        "tokens in the cumulative logs, consistent with the known noise-floor false positives, never committed (the logs are gitignored).\n\n"
    )
    s5 = (
        "## Section 5 — Recommendations\n\n"
        "No metric FAILED or is MARGINAL in either run, so there is no defect to attribute. Next steps:\n\n"
        "1. **Declare run 1 the new baseline** (flag-ON `main` series, shim 20260056, DLL `ee00d118...`), run 2 as its confirmation. Compare future "
        "sweeps against both rows, never against flag-OFF rows.\n"
        "2. **S7:** both runs fall in the known 16 pp band between the decoders; the +3.7/+3.3 pp movement between the two runs is a "
        "reminder that S7 is instrument-suspect. No finding is drawn from it.\n"
        "3. **S3c:** keep it in the routine battery. Its E -2.00 guard is weak (k* = 4) and its L +3.00 row is descriptive; the Architect scores "
        "S3C1/S3C2 at the third battery.\n"
        "4. **Scan:** 38 (run 1) and 47 (run 2) slots flagged of 407, mostly S5 noise slots and mostly in the shared playback path; none is a decoder "
        "defect by construction. The scan's holes stand (30 descriptive cells). The scan runs after the gather and is quoted above.\n"
        "5. **Procedure (for the Architect):** (a) RUNBOOK 5.4: run the scan BEFORE rendering the HTML and quote it in report.md (done by hand here, "
        "in that order); (b) `analyse.py` should read the build commit from `arm_config.json` instead of `git rev-parse HEAD` (fourth occurrence, "
        "corrected by hand every time); (c) a battery's watchdog silence limit must exceed S5's runtime (about 70 min of silence).\n"
        "6. **Not done here:** the sampler (owner open), DO1-DO3 scoring, the batch-2 auto-QSO choice (parked).\n\n"
    )
    out = header + s1 + body + "\n" + scan_section(run) + "\n" + s3c_section(run) + "\n" + s5 + section6(run_key)
    (run / "report.md").write_text(out, encoding="utf-8")
    print("wrote", run / "report.md", len(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--role", required=True, choices=["baseline", "confirmation"])
    ap.add_argument("--other", required=True)
    a = ap.parse_args()
    build(Path(a.run).name, a.role, Path(a.other).name)


if __name__ == "__main__":
    main()
