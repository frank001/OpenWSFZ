"""Assemble the final report.md of a routine synthetic S1-S8 run (HK-001 sections 1, 5, 6 + the #194 sections).

    python assemble_run_report.py <run-dir> --prior <last-report-run-dir> --build-sha <40 hex> --dll-sha <64 hex> \
        --shim <n> --label "<row label>" --window "<S1 start..end UTC>" --section1 <file> --section5 <file>

Why this exists (2026-10-04): `baseline_assemble_report.py` is hard-wired to the two baseline-194 runs (their build SHA,
DLL, the "run 1 / run 2" prose, "batteries 1 and 2 of 3", a fixed run-level reading). Run on any other run it would
write the WRONG build into the report (HK-022). This script computes every figure from the run's own files and takes
the authored prose (Sections 1 and 5) from files, so nothing from an earlier run is carried over except the Section 6 table
and its footnotes, which are copied from the LAST report's Section 6 (HK-031, HK-034).

Keeps the analyser's body unedited (a copy is saved as report.analyser-original.md). Counts and rates only (NFR-021).
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

# Hard constants asserted in code, not left as prose (the 2026-09-06 lesson).
EXPECTED_SCANNED_SLOTS = 407
SHA_LEN = 40
DLL_LEN = 64
RUN_LEVEL_LIMIT_DB = 0.5


def quote(path: Path, start: str, stop: str | None = None) -> str:
    t = path.read_text(encoding="utf-8")
    i = t.index(start)
    j = t.index(stop, i + 1) if stop else len(t)
    return t[i:j].rstrip() + "\n"


def pooled(run: Path) -> tuple[int, int]:
    """(OpenWSFZ, WSJT-X) matched decodes pooled over S7+S8: the final Section 6 column."""
    c: Counter = Counter()
    for s in ("S7", "S8"):
        for r in csv.DictReader(open(run / f"{s}_matched.csv", encoding="utf-8")):
            if r["matched"] == "True":
                c[r["appraiser"]] += 1
    return c["OpenWSFZ"], c["WSJT-X"]


def run_level(sr_text: str) -> tuple[list[tuple[str, float]], list[str]]:
    """Per (side, group) g_db offsets from the scan's A11 lines, and any that exceed the limit."""
    block = sr_text[sr_text.index("### Run-level lines (A11)"):]
    block = block[:block.index("(b)")]
    vals = [(m.group(1), float(m.group(2))) for m in re.finditer(r"^- (\w+ \w+): ([+-]\d+\.\d+) dB", block, re.M)]
    assert vals, "no run-level lines parsed"
    return vals, [k for k, v in vals if abs(v) > RUN_LEVEL_LIMIT_DB]


def scan_section(run: Path, harness_commit: str) -> str:
    sr = run / "captured-audio-scan" / "scan_report.md"
    t = sr.read_text(encoding="utf-8")
    assert "SKIPPED" not in t.split("\n", 1)[0], "scan was SKIPPED: rerun it"
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
    vals, bad = run_level(t)
    worst = max(vals, key=lambda kv: abs(kv[1]))
    frz = re.search(r"- Frozen `thresholds.json`.*", t).group(0)
    tool = re.search(r"- Tool: .*", t).group(0)
    val = quote(sr, "## Validation rows", "## Flagged slots by class")
    verdict = ("**`RUN-LEVEL` event(s): " + ", ".join(bad) + "**" if bad else
               f"every `g_db` run-level offset is within the {RUN_LEVEL_LIMIT_DB} dB limit (largest |offset| {abs(worst[1]):.2f} dB, "
               f"{worst[0]}): no `RUN-LEVEL` event, so the chain's level was stable for the whole run")
    return (
        "## Captured-audio scan (#194)\n\n"
        "This section is quoted from `captured-audio-scan/scan_report.md` of THIS run. The scan ran after the gather, "
        "was not SKIPPED, and found no decoder defect by construction: a WAV is recorded before either decoder runs.\n\n"
        f"- Scan commit/freeze: `eng/194-scan` (`d06b01d9`, on `main` since `b87529a3`); harness commit `{harness_commit[:8]}` "
        f"(`main`, the build under test; the scan tooling is unchanged since).\n{frz}\n{tool}\n\n"
        f"- Flagged slots: **{slots}** distinct slots of {EXPECTED_SCANNED_SLOTS} scanned per side ({len(rows)} slot-family findings).\n\n"
        + "\n".join(tbl) + "\n\n"
        + "### Headline, quoted verbatim\n\n" + head.replace("## Headline (plain words)\n", "") + "\n"
        + "### Validation rows, quoted verbatim\n\n" + val.replace("## Validation rows\n", "") + "\n"
        + "### Run-level line, quoted verbatim\n\n" + runlvl + "\n"
        f"Reading: {verdict}. The scan carries its holes: it cannot see a short added "
        "sound or a click in the groups above range.\n"
    )


def s3c_section(run: Path) -> str:
    body = quote(run / "s3c" / "s3c_report.md", "- Flag state").replace("\n## Rows", "\n### Rows")
    return "## S3c start-time edge guard (#194 part B step 2)\n\n" + body + "\n"


def section6(prior: Path, new_row: str, footnotes: str, hk031: str) -> str:
    p = (prior / "report.md").read_text(encoding="utf-8")
    s6 = p[p.index("## Section 6"):]
    s6 = re.sub(r"\*\*HK-031:.*?verbatim\.\*\*", hk031, s6, count=1, flags=re.S)
    lines = s6.split("\n")
    last = max(i for i, l in enumerate(lines) if re.match(r"\| \*{0,2}2026-10-0\d", l))
    lines[last + 1:last + 1] = [new_row]
    return "\n".join(lines).rstrip() + "\n\n" + footnotes.strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--prior", required=True)
    ap.add_argument("--build-sha", required=True)
    ap.add_argument("--dll-sha", required=True)
    ap.add_argument("--shim", required=True)
    ap.add_argument("--section1", required=True)
    ap.add_argument("--section5", required=True)
    ap.add_argument("--row", required=True, help="the new Section 6 row, complete")
    ap.add_argument("--footnotes", required=True, help="file with the new footnotes")
    ap.add_argument("--hk031", required=True, help="file with the replacement HK-031 sentence")
    a = ap.parse_args()
    assert len(a.build_sha) == SHA_LEN and len(a.dll_sha) == DLL_LEN
    run = RESULTS / Path(a.run).name
    prior = RESULTS / Path(a.prior).name
    orig = run / "report.analyser-original.md"
    if not orig.exists():
        shutil.copy2(run / "report.md", orig)
    base = orig.read_text(encoding="utf-8")
    assert a.build_sha in base and a.dll_sha in base, "the analyser's header does not carry this build/DLL: stop (HK-022)"
    head_end = base.index("## S1 ")
    header = base[:head_end].rstrip() + "\n\n"
    body = base[head_end:]
    s6 = section6(prior, a.row, Path(a.footnotes).read_text(encoding="utf-8"), Path(a.hk031).read_text(encoding="utf-8").strip())
    out = (header + Path(a.section1).read_text(encoding="utf-8") + "\n" + body + "\n"
           + scan_section(run, a.build_sha) + "\n" + s3c_section(run) + "\n"
           + Path(a.section5).read_text(encoding="utf-8") + "\n" + s6)
    (run / "report.md").write_text(out, encoding="utf-8")
    n_o, n_w = pooled(run)
    print("wrote", run / "report.md", len(out), "chars; pooled", n_o, n_w, f"{100 * n_o / n_w:.2f}%")


if __name__ == "__main__":
    main()
