#!/usr/bin/env python3
"""Generate `qa/ARTEFACT_INVENTORY.md` -- the "what have we already collected?" lookup.

WHY THIS EXISTS
---------------
HK-018 says "check the data already gathered before concluding". It is a
disposition, not an address: it says to check, not where. Across ~30 GB and 40+
run folders that is an open-ended search, and open-ended searches get skipped
under momentum -- four times in the 2026-08-02 session alone, most expensively
by recommending a multi-day capture run for a corpus that had been sitting in
`artefacts/` for two days.

This turns the rule into a lookup. One table, one row per run, answer in
seconds.

MECHANICAL vs INTERPRETIVE
--------------------------
Every column except `notes` is measured from disk on each run, so it cannot go
stale silently. `notes` is hand-written, lives in NOTES below (version
controlled, survives regeneration), and is rendered in a separate column marked
as interpretive -- so a stale note looks like a note, not like a fact.

A hand-maintained inventory would drift, and a stale inventory is worse than
none: it produces confident false negatives ("we don't have that"), which is
the same failure with the sign flipped.

USAGE
-----
    python qa/artefact_inventory.py            # regenerate qa/ARTEFACT_INVENTORY.md
    python qa/artefact_inventory.py --check    # exit 1 if the file is out of date

`ALL.TXT` files are stat'd (for hardlink detection); WAVs are counted by name via
os.scandir, and (since G1, 2026-08-10) their inode is read from that same scan too, for
hardlink detection on the wav/ side -- a real defect (1 968 duplicated WAVs on the
2026-08-09 80m leg) was invisible here until then, because only ALL.TXT was ever checked.
Still seconds, not the minutes `du` takes -- no extra per-file stat call is added.
Output is ASCII-only (HK-009). NFR-021: counts and paths only, no callsigns.
"""

from __future__ import annotations

import argparse
import datetime
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # HK-009
except AttributeError:  # pragma: no cover
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTEFACTS = os.path.join(REPO, "artefacts")
# NOT inside artefacts/ -- that directory is git-ignored (.gitignore:105), so an
# inventory written there would be invisible to QA and to review. It lives in
# qa/ so drift is caught in a diff like any other tracked file.
OUTPUT = os.path.join(REPO, "qa", "ARTEFACT_INVENTORY.md")

_TS = re.compile(r"^(\d{6}_\d{6})")

# G1 (qa/cycleframer-alignment-replay/2026-08-10-1559-architect-to-qa-spec-g1-gather-tool-
# reference-provenance-guard.md §3.6): kept byte-identical to
# tools/gather_live_run_artefacts.py's SHARED_INSTALL_ASSERTION_MARKER -- that script writes
# this literal phrase into a run's contents.md when --wsjtx-shared-install was passed; this
# script greps for it to tell an intentional shared install apart from an unverified
# duplicate. If one copy changes, change the other.
SHARED_INSTALL_ASSERTION_MARKER = "operator asserted --wsjtx-shared-install"
PROVENANCE_HEADER = "## WSJT-X / OpenWSFZ provenance (G1)"

# ---------------------------------------------------------------------------
# INTERPRETIVE. Hand-written, one line each. Keyed by run folder name.
# Say what question the run can answer and what has already consumed it.
# Leave a run out rather than guess -- a blank cell is honest, a wrong note
# is the failure this file exists to prevent.
# ---------------------------------------------------------------------------
NOTES: dict[str, str] = {
    "20260803_live_run_1713":
        "**D-001 replication corpus -- DO NOT PROPOSE A CAPTURE RUN FOR D-001.** "
        "Answers project-state-2026-07-31 S5.4, which named the WSJT-X same-family "
        "control 'the single most decision-relevant unknown for the menu' and "
        "assumed the capture had not been run. It had -- two days later, into this "
        "folder. 20m (14.074), ONE contiguous 18.96h decisive epoch from "
        "260803_185914, drift screen ROW 5 PASS (+0.0 ppm), post-be5960a. Both "
        "decoders on ONE verified audio path (median |r|=0.987 over 8 WAV pairs, "
        "lags <=34ms) -- unlike the split -8080/-8081 runs, so re-verify per corpus "
        "rather than inheriting either way. Density contrast 6.54x. Consumed by "
        "Tasks 1/3/5 and by Arm R.D (specced 2026-08-05, not run, not authorised).",
    "20260731_live_run_2004-8080":
        "**D-001 Angle 1 corpus.** One WSJT-X instance (hardlinked into the -8081 "
        "folder too -- one capture, not two). Feeds legs A/B/C and null N3, which "
        "needs exactly this: jt9 over WSJT-X's own WAVs vs its own live count. "
        "N3 runnable offline, no capture needed. T4 unauthorised as of 2026-08-02.",
    "20260731_live_run_2004-8081":
        "Same WSJT-X capture as -8080 (hardlinked ALL.TXT + wav/). The owsfz leg "
        "IS distinct. Do not treat the two wsjt-x legs as independent captures.",
    "20260729_live_run_1831-8080":
        "Pre-drift-fix. Superseded by the 07-31 run for D-001 work.",
    "d001_wav_source_cross_decode_2026-07-30":
        "Capture-chain cross-decode; source of the ~10-13% capture-chain effect.",
    "d001_b1b_second_corpus":
        "Second corpus for the B.3 costed menu (2026-07-27). Menu decision still open.",
}

SKIP_DIRS = {".git"}


def cycle_stats(path: str) -> tuple[int, str, str]:
    """(distinct cycle count, first ts, last ts) from an ALL.TXT."""
    seen: set[str] = set()
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _TS.match(line)
                if m:
                    seen.add(m.group(1))
    except OSError:
        return 0, "", ""
    if not seen:
        return 0, "", ""
    s = sorted(seen)
    return len(seen), s[0], s[-1]


def count_wavs(root: str) -> int:
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        n += sum(1 for f in filenames if f.lower().endswith(".wav"))
    return n


def wav_inode_map(wav_dir: str) -> dict[str, int]:
    """filename -> inode for one wav/ directory, read from the same os.scandir pass
    count_wavs would otherwise use for names only -- no extra per-file stat call, since
    DirEntry.inode() is served from the directory-entry data already fetched."""
    out: dict[str, int] = {}
    try:
        with os.scandir(wav_dir) as it:
            for entry in it:
                if entry.name.lower().endswith(".wav"):
                    try:
                        if entry.is_file():
                            out[entry.name] = entry.inode()
                    except OSError:
                        pass
    except OSError:
        pass
    return out


def read_contents_md(run_dir: str) -> str:
    try:
        with io.open(os.path.join(run_dir, "contents.md"), "r",
                     encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def provenance_status(contents_text: str) -> str:
    """One of 'not_recorded' (gathered before the G1 fix -- no provenance section at all),
    'asserted_shared' (operator passed --wsjtx-shared-install, recorded verbatim), or
    'guarded' (a provenance section exists and the §3.3 guard was active, i.e. the tool itself
    verified at gather time that no ambiguity existed)."""
    if PROVENANCE_HEADER not in contents_text:
        return "not_recorded"
    if SHARED_INSTALL_ASSERTION_MARKER in contents_text:
        return "asserted_shared"
    return "guarded"


def find_all_txt(root: str) -> dict[str, str]:
    """Map leg name -> ALL.TXT path, for legs that have one."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.upper() == "ALL.TXT":
                leg = os.path.relpath(dirpath, root).replace("\\", "/")
                out["(root)" if leg == "." else leg] = os.path.join(dirpath, f)
    return out


def scan() -> list[dict]:
    rows: list[dict] = []
    # inode -> [(run, leg), ...] across ALL runs. A shared inode means one
    # capture gathered into several folders. This MUST be mechanical: the
    # 2026-08-02 session lost an afternoon to a cross-folder hardlink that was
    # only ever recorded in prose.
    global_inodes: dict[int, list[tuple[str, str]]] = {}
    # G1 §3.6: the WAV-side equivalent. inode -> [(run, leg, filename), ...]. Filename
    # matters here (unlike ALL.TXT, a leg has many WAVs) -- a shared inode always implies a
    # shared filename (you cannot hardlink two different names to prove anything about a
    # THIRD name), but keeping it lets the annotation say which/how-many, not just that some
    # sharing exists.
    global_wav_inodes: dict[int, list[tuple[str, str, str]]] = {}
    for name in sorted(os.listdir(ARTEFACTS)):
        run = os.path.join(ARTEFACTS, name)
        if not os.path.isdir(run):
            continue
        legs = find_all_txt(run)
        wavs = {}
        for sub in sorted(os.listdir(run)):
            p = os.path.join(run, sub)
            if os.path.isdir(p):
                c = count_wavs(p)
                if c:
                    wavs[sub] = c
        leg_info = {}
        inodes = {}
        leg_wav_inodes: dict[str, dict[str, int]] = {}
        for leg, path in sorted(legs.items()):
            n, first, last = cycle_stats(path)
            leg_info[leg] = n
            try:
                ino = os.stat(path).st_ino
                inodes[leg] = ino
                global_inodes.setdefault(ino, []).append((name, leg))
            except OSError:
                pass
            wav_dir = os.path.join(os.path.dirname(path), "wav")
            if os.path.isdir(wav_dir):
                wmap = wav_inode_map(wav_dir)
                if wmap:
                    leg_wav_inodes[leg] = wmap
                    for filename, wino in wmap.items():
                        global_wav_inodes.setdefault(wino, []).append((name, leg, filename))
        span = ("", "")
        for leg, path in sorted(legs.items()):
            n, first, last = cycle_stats(path)
            if n:
                span = (first, last)
                break
        if not legs and not wavs:
            continue
        prov = provenance_status(read_contents_md(run))
        rows.append(dict(name=name, legs=leg_info, wavs=wavs, span=span,
                         inodes=inodes, hardlinked=[], wav_hardlinked=[],
                         leg_wav_inodes=leg_wav_inodes, provenance=prov,
                         total_wavs=sum(wavs.values())))

    # second pass: annotate every leg whose ALL.TXT inode is shared with another leg, in this
    # run or any other -- and, separately, every leg whose wav/ directory has WAVs sharing an
    # inode with another leg's wav/ directory (G1 §3.6 -- this is the check that would have
    # caught the 2026-08-09 80m defect on the WAV side; the ALL.TXT-only version above did
    # correctly report the annotation gone once X0 repaired ALL.TXT while 1 968 duplicated
    # WAVs silently remained).
    prov_suffix = {
        "not_recorded": " *(provenance not recorded -- gathered before the G1 fix)*",
        "asserted_shared": " *(intentional -- operator asserted shared install)*",
        "guarded": " *(unverified duplicate -- the G1 guard was not asked to allow this)*",
    }
    for r in rows:
        shared = []
        for leg, ino in r["inodes"].items():
            others = [(n, l) for (n, l) in global_inodes.get(ino, [])
                      if not (n == r["name"] and l == leg)]
            if others:
                shared.append("`%s` = %s%s" % (
                    leg, ", ".join("`%s`/`%s`" % o for o in others),
                    prov_suffix[r["provenance"]]))
        r["hardlinked"] = shared

        wav_shared = []
        for leg, wmap in r["leg_wav_inodes"].items():
            total = len(wmap)
            other_pairs: dict[tuple[str, str], int] = {}
            for filename, wino in wmap.items():
                for (n, l, f) in global_wav_inodes.get(wino, []):
                    if n == r["name"] and l == leg:
                        continue
                    other_pairs[(n, l)] = other_pairs.get((n, l), 0) + 1
            if other_pairs:
                detail = ", ".join(
                    "`%s`/`%s` (%d)" % (n, l, c) for (n, l), c in sorted(other_pairs.items())
                )
                shared_count = max(other_pairs.values())
                wav_shared.append("`%s/wav` %d/%d shared with %s%s" % (
                    leg, shared_count, total, detail, prov_suffix[r["provenance"]]))
        r["wav_hardlinked"] = wav_shared
    return rows


def find_wsjtx_pairs(rows: list[dict]) -> list[tuple[dict, dict]]:
    """G1 §5.1/§5.2 retro-audit, made a standing mechanical check rather than a one-time
    prose note: every pair of runs whose names differ only by an -8080/-8081 (or other port)
    swap, where BOTH sides gathered a leg literally named 'wsjt-x'. This is the only shape in
    which the G1-style two-instance duplication defect can occur at all -- if only one side
    of a pair ever gathers a wsjt-x leg (true of e.g. the 2026-07-28/07-29 pairs, checked by
    hand 2026-08-10 and confirmed one-sided), there is nothing on the other side for it to
    have silently duplicated. Re-running this against a future new pair costs nothing -- it
    falls out of the next `python qa/artefact_inventory.py` for free."""
    by_name = {r["name"]: r for r in rows}
    pairs: list[tuple[dict, dict]] = []
    seen: set[frozenset] = set()
    for name, r in by_name.items():
        if "wsjt-x" not in r["legs"]:
            continue
        for a, b in (("8080", "8081"), ("8081", "8080")):
            if a not in name:
                continue
            candidate = name.replace(a, b, 1)
            other = by_name.get(candidate)
            if other is None or candidate == name or "wsjt-x" not in other["legs"]:
                continue
            key = frozenset((name, candidate))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((r, other))
    return sorted(pairs, key=lambda p: p[0]["name"])


def render(rows: list[dict]) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out: list[str] = []
    out.append("# Artefact inventory -- what has already been collected")
    out.append("")
    out.append("**GENERATED FILE -- do not hand-edit.** Regenerate with")
    out.append("`python qa/artefact_inventory.py`. Hand-written notes live in that")
    out.append("script's `NOTES` dict and survive regeneration.")
    out.append("")
    out.append("Read this **before** concluding that data for a question does not")
    out.append("exist, and before proposing any capture run (HK-018, HK-004).")
    out.append("")
    out.append("Every column except **notes** is measured from disk on each run and")
    out.append("cannot go stale silently. **notes** is interpretive and hand-written --")
    out.append("treat it as a claim to verify, not a fact.")
    out.append("")
    out.append("Scanned: %s | %d runs | %s total WAVs"
               % (now, len(rows), f"{sum(r['total_wavs'] for r in rows):,}"))
    out.append("")
    out.append("| run | UTC span | legs (distinct cycles) | WAVs | notes *(interpretive)* |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        span = "%s -> %s" % r["span"] if r["span"][0] else "-"
        legs = "<br>".join("`%s` %s" % (k, f"{v:,}") for k, v in r["legs"].items()) or "-"
        if r["hardlinked"]:
            legs += "<br>**HARDLINKED** " + "; ".join(r["hardlinked"])
        wavs = "<br>".join("`%s` %s" % (k, f"{v:,}") for k, v in r["wavs"].items()) or "-"
        if r["wav_hardlinked"]:
            wavs += "<br>**HARDLINKED** " + "; ".join(r["wav_hardlinked"])
        note = NOTES.get(r["name"], "")
        out.append("| `%s` | %s | %s | %s | %s |" % (r["name"], span, legs, wavs, note))
    out.append("")
    out.append("## How to read the `legs` and `WAVs` columns")
    out.append("")
    out.append("`owsfz` is our daemon's `ALL.TXT`; `wsjt-x` is the comparison decoder's.")
    out.append("**HARDLINKED** means two paths resolve to the same inode -- one capture")
    out.append("gathered into two folders, not two independent captures. That is fine for")
    out.append("anything needing a single instrument and fatal for anything assuming two.")
    out.append("")
    out.append("**Since G1 (2026-08-10) the WAVs column carries its OWN, separate")
    out.append("HARDLINKED check** -- a run's `ALL.TXT` can be repaired (independent, no")
    out.append("longer shared) while its `wav/` files are still hardlinked to another leg,")
    out.append("exactly what happened on the 2026-08-09 80m leg (1 968 WAVs, invisible to")
    out.append("the ALL.TXT-only check for a full day). Always read both columns; a clean")
    out.append("`legs` column does not imply a clean `WAVs` column.")
    out.append("")
    out.append("Every **HARDLINKED** annotation (either column) also carries a provenance")
    out.append("tag, read from the run's own `contents.md` (written by")
    out.append("`tools/gather_live_run_artefacts.py` since G1):")
    out.append("")
    out.append("- *(intentional -- operator asserted shared install)* -- the operator")
    out.append("  passed `--wsjtx-shared-install`, on the record, because only one live")
    out.append("  WSJT-X instance actually existed this session. Fine.")
    out.append("- *(unverified duplicate -- the G1 guard was not asked to allow this)* --")
    out.append("  `contents.md` has a provenance section (so this run post-dates the G1")
    out.append("  fix) but no shared-install assertion. Needs a human look.")
    out.append("- *(provenance not recorded -- gathered before the G1 fix)* -- no")
    out.append("  provenance section exists at all. Cannot mechanically tell an")
    out.append("  intentional share from an accidental duplicate; use the instance-identity")
    out.append("  method in the G1 spec's §5.1 if it matters for a citation.")
    out.append("")
    out.append("## G1 §5.1/§5.2 retro-audit -- two-instance `wsjt-x` pairs")
    out.append("")
    out.append("Mechanical, regenerated every run (not a one-time prose note): every pair of")
    out.append("run folders differing only by an `-8080`/`-8081` swap where BOTH sides")
    out.append("gathered a leg literally named `wsjt-x`. This is the only shape the G1 defect")
    out.append("can occur in -- a side that never gathers a `wsjt-x` leg has nothing for the")
    out.append("other side to have silently duplicated.")
    out.append("")
    pairs = find_wsjtx_pairs(rows)
    if pairs:
        out.append("| pair | ALL.TXT hardlink | wav/ hardlink |")
        out.append("|---|---|---|")
        for a, b in pairs:
            status_txt = "clean" if not a["hardlinked"] and not b["hardlinked"] else "**FLAGGED above**"
            status_wav = "clean" if not a["wav_hardlinked"] and not b["wav_hardlinked"] else "**FLAGGED above**"
            out.append("| `%s` <-> `%s` | %s | %s |" % (a["name"], b["name"], status_txt, status_wav))
        out.append("")
    else:
        out.append("No such pairs currently on disk.")
        out.append("")
    out.append("Runs with only ONE side gathering a `wsjt-x` leg (checked by hand, "
                "2026-08-10: the `20260728_live_run_2354` and `20260729_live_run_1831` "
                "-8080/-8081 pairs) are excluded above by construction -- they are not at "
                "risk of this defect and do not need the deeper instance-identity check.")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if ARTEFACT_INVENTORY.md is out of date")
    args = ap.parse_args()

    if not os.path.isdir(ARTEFACTS):
        print("no artefacts/ directory at %s" % ARTEFACTS)
        return 2

    text = render(scan())

    if args.check:
        try:
            cur = io.open(OUTPUT, "r", encoding="utf-8").read()
        except OSError:
            print("ARTEFACT_INVENTORY.md missing")
            return 1
        strip = lambda s: "\n".join(l for l in s.splitlines()
                                    if not l.startswith("Scanned:"))
        if strip(cur) != strip(text):
            print("ARTEFACT_INVENTORY.md is out of date -- run: python qa/artefact_inventory.py")
            return 1
        print("ARTEFACT_INVENTORY.md up to date")
        return 0

    with io.open(OUTPUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s" % OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
