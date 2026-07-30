#!/usr/bin/env python3
"""Endurance-session ANOVA: OpenWSFZ vs jt9 (re-decodes archived WAVs).

USE THIS SCRIPT ONLY WHEN THERE IS NO LIVE THIRD-PARTY DECODE LOG ALREADY COVERING THE
SAME FEED -- e.g. an SDR-fed instance (SDR Uno, etc.) with no WSJT-X application running
against it. If a real WSJT-X application has been running the whole session on the SAME
physical/audio feed as the OpenWSFZ instance you're analysing (true for the 40m instance
in this repo's live-run setup), use endurance_anova_wsjtx.py instead -- WSJT-X's own
ALL.TXT is already a complete decode log, and re-decoding hours of archived WAVs through
jt9 to reproduce data that already exists on disk is pure waste (Captain, 2026-07-30).

Split 2026-07-30 from a single endurance_anova.py that did both jobs; see
anova_common.py's module docstring for the full rationale and the shared ANOVA/matching/
chart/report machinery both scripts use. This file keeps only what's specific to
obtaining the second appraiser's decodes by actually re-running the decoder: batching WAVs
to jt9, parsing its stdout, and resolving its bare HHMMSS timestamps back to full cycle
IDs.

Originally built as a standard step for every unattended endurance session (Captain's
instruction, 2026-07-27 -- "I want the ANOVA analysis built in for every unattended
durance session"). Run this against a session's ALL.TXT + cycle-audio-archive WAVs once
the session closes; it produces anova_report.md as a standard artefact. For a multiband
instance whose corpus has been band-split by tools/gather_live_run_artefacts.py's
--split-owsfz-by-band, run this once per band (point --all-txt/--wav-dir at each
owsfz/<band>/ subfolder in turn) -- this script has no notion of "band" itself, it just
processes whatever ALL.TXT + WAV directory you give it.

PARALLELISM: jt9 is invoked once per batch (batched only to stay under Windows' command-
line length limit, see JT9_BATCH_SIZE below). Each invocation is an external process that
spends nearly all its time inside jt9 itself, not inside the Python interpreter, so
Python's GIL is not a bottleneck -- batches are run concurrently with a plain
ThreadPoolExecutor rather than multiprocessing (simpler, no pickling, no Windows spawn-
guard concerns). Default reserves DEFAULT_CPU_HEADROOM logical CPUs so the machine stays
usable during an unattended run (2026-07-28, after a full-throttle default saturated a
live 16-core machine). Pass --max-workers explicitly (e.g. --max-workers $(nproc)) for a
genuine full-throttle run when the machine is confirmed idle.

Usage:
    python endurance_anova_jt9.py --all-txt ALL.TXT --wav-dir <cycle-audio dir> \\
        --out anova_report.md [--jt9-exe PATH] [--jt9-depth 3] [--limit N] \\
        [--max-workers N] [--jt9-batch-size N] [--run-label "2026-07-30 10m endurance"]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import os
import re
import subprocess
import sys

import anova_common as ac

if hasattr(sys.stdout, "reconfigure"):
    # line_buffering=True: this script's progress prints (batch N/M starting/done) are
    # the only visibility into a run that can take the better part of an hour -- without
    # it, output sits in Python's block buffer and a background/redirected run looks
    # stalled even while working (seen live, 2026-07-27).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

DEFAULT_JT9_EXE = r"D:\WSJT\wsjtx\bin\jt9.exe"

_TS6_RE = re.compile(r"^\d{6}$")
_NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def parse_jt9_stdout(text: str, hhmmss_to_ts: dict[str, str]) -> tuple[list[dict], int]:
    """jt9 -8 stdout format: HHMMSS SNR DT FREQ MARKER MESSAGE...

    jt9's own stdout carries only a bare HHMMSS, not a date -- it does not know what
    calendar date the WAV it just decoded came from. `hhmmss_to_ts` resolves each row's
    HHMMSS back to the *specific source WAV's own* "YYMMDD_HHMMSS" stem (built from the
    actual filenames fed to this run, across the whole corpus, not just the current
    batch). This matters: an endurance session commonly spans UTC midnight (e.g. a
    21:06->08:52 overnight run), and naively prepending one assumed date to every line in
    a batch would silently mislabel every post-midnight decode with the wrong date --
    corrupting the cycle-matching key without raising any error. Returns (rows,
    unmatched_count) -- unmatched HHMMSS values are dropped, not guessed at.

    Each row also captures dt (tok[2], time offset s) and freq_hz (tok[3], reported
    frequency offset Hz) alongside snr -- the same three paired metrics parse_all_txt
    captures from our own side, so all three can be compared.
    """
    rows = []
    unmatched = 0
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        tok = line.split()
        if len(tok) < 6:
            continue
        if not _TS6_RE.match(tok[0]):
            continue
        if not _NUM_RE.match(tok[1]) or not _NUM_RE.match(tok[2]) or not _NUM_RE.match(tok[3]):
            continue
        ts = hhmmss_to_ts.get(tok[0])
        if ts is None:
            unmatched += 1
            continue
        try:
            snr = float(tok[1])
            dt = float(tok[2])
            freq_hz = float(tok[3])
        except ValueError:
            continue
        rows.append({"ts": ts, "snr": snr, "dt": dt, "freq_hz": freq_hz,
                    "message": " ".join(tok[5:])})
    return rows, unmatched


# Logical CPUs reserved (never handed to jt9 workers) when --max-workers isn't given
# explicitly, so an unattended run leaves the machine usable rather than saturating every
# core (see PARALLELISM note above; found live, 2026-07-28). Floored at 1 worker
# regardless of how small os.cpu_count() is.
DEFAULT_CPU_HEADROOM = 4

# Conservative per-invocation batch size: Windows' CreateProcess command-line limit is
# ~32767 chars. Repo-tree WAV paths run well under 150 chars each in practice; 150
# files/batch keeps the joined argv comfortably under that limit regardless of exactly
# how deep a given checkout path is, without needing to measure it per run. Overridable
# via --jt9-batch-size (mainly useful for testing the parallel path against a small
# corpus, where the default would only ever produce one batch).
JT9_BATCH_SIZE = 150


def _run_one_jt9_batch(jt9_exe: str, batch: list[str], depth: int,
                        hhmmss_to_ts: dict[str, str], timeout_secs: int,
                        batch_num: int, total_batches: int) -> tuple[list[dict], int]:
    """Runs a single jt9 batch to completion. Designed to be called from a thread pool --
    everything it touches (its own TemporaryDirectory, its own subprocess) is local to
    this call, so concurrent invocations don't share mutable state."""
    print(f"  jt9 batch {batch_num}/{total_batches} starting ({len(batch)} files)...")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="endurance_anova_jt9_") as scratch:
        # subprocess cwd is `scratch`, not the caller's cwd -- WAV paths must be absolute
        # or jt9 can't find its own input files against the new cwd (found live,
        # 2026-07-27: relative paths silently produced jt9 exit 2 / zero decodes with no
        # other diagnostic).
        abs_batch = [os.path.abspath(p) for p in batch]
        cmd = [jt9_exe, "-8", "-d", str(depth), "-p", "15", "-a", scratch, "-t", scratch] + abs_batch
        result = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=timeout_secs)
        if result.returncode != 0:
            print(f"[WARN] jt9 exited {result.returncode} on batch {batch_num}/{total_batches}",
                  file=sys.stderr)
        rows, unmatched = parse_jt9_stdout(result.stdout, hhmmss_to_ts)
    print(f"  jt9 batch {batch_num}/{total_batches} done ({len(rows)} decode lines).")
    return rows, unmatched


def run_jt9(jt9_exe: str, wav_paths: list[str], depth: int,
            hhmmss_to_ts: dict[str, str] | None = None,
            timeout_secs: int | None = None,
            max_workers: int | None = None,
            batch_size: int = JT9_BATCH_SIZE) -> list[dict]:
    if not wav_paths:
        return []
    if hhmmss_to_ts is None:
        hhmmss_to_ts = {
            os.path.splitext(os.path.basename(p))[0].split("_", 1)[1]:
                os.path.splitext(os.path.basename(p))[0]
            for p in wav_paths
        }
    # Measured ~1s/file wall time (2026-07-27 timing probe, this machine). 5s/file per
    # batch gives generous headroom without needing a hand-tuned timeout per run.
    if timeout_secs is None:
        timeout_secs = max(600, 5 * batch_size)
    # Default reserves DEFAULT_CPU_HEADROOM logical CPUs so an unattended run doesn't
    # saturate the machine (2026-07-28, after exactly that happened -- see PARALLELISM
    # note above). jt9 itself is a single-process, not-internally-parallel decode per
    # invocation, so one worker roughly costs one core. Pass --max-workers explicitly
    # (e.g. os.cpu_count()) for a genuine full-throttle run on a confirmed-idle machine.
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 1) - DEFAULT_CPU_HEADROOM)

    batches = [wav_paths[i:i + batch_size] for i in range(0, len(wav_paths), batch_size)]
    print(f"running {len(batches)} jt9 batch(es) across up to {max_workers} parallel "
          f"worker(s) ({os.cpu_count()} logical CPUs detected)...")

    all_rows: list[dict] = []
    total_unmatched = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # subprocess.run() releases the GIL while the child process runs, so a plain
        # thread pool achieves real OS-level parallelism here despite Python's GIL -- no
        # multiprocessing/pickling needed, since each worker's actual work happens
        # outside the Python interpreter entirely.
        futures = [
            executor.submit(_run_one_jt9_batch, jt9_exe, batch, depth, hhmmss_to_ts,
                             timeout_secs, i + 1, len(batches))
            for i, batch in enumerate(batches)
        ]
        for future in concurrent.futures.as_completed(futures):
            rows, unmatched = future.result()
            all_rows.extend(rows)
            total_unmatched += unmatched

    if total_unmatched:
        print(f"[WARN] {total_unmatched} jt9 decode lines had an HHMMSS not matching any "
              f"source WAV in this run (dropped, not guessed at)", file=sys.stderr)
    return all_rows


def extract_dial_mhz(all_txt_path: str) -> str:
    """Reads the dial-frequency field (token 1) off the first parseable line of an
    ALL.TXT-format file. jt9's own stdout has no dial-frequency column at all -- it's a
    property of the WAV/band being fed in, not something jt9 reports per decode -- so this
    borrows the value from the corresponding OpenWSFZ ALL.TXT for the same band, which is
    valid since jt9 decoded the exact same audio. Falls back to 'unknown' if the file has no
    parseable line (never blocks writing the jt9 decode log over a missing dial value)."""
    try:
        with open(all_txt_path, encoding="ascii", errors="replace") as fh:
            for line in fh:
                tok = line.split()
                if len(tok) >= 2:
                    return tok[1]
    except OSError:
        pass
    return "unknown"


def write_jt9_all_txt(jt9_rows: list[dict], dial_mhz: str, out_path: str) -> None:
    """Writes jt9's own raw decode output as an ALL.TXT-format file, one line per decode,
    sorted by cycle timestamp -- the same treatment OpenWSFZ's and WSJT-X's own decode logs
    get. Without this, jt9's per-cycle results only ever existed in memory long enough to
    compute the ANOVA stats and were then discarded, leaving no raw record of what jt9
    actually decoded (Captain, 2026-07-30: 'it should be in the artefacts folder'). Lands
    alongside the OpenWSFZ ALL.TXT it was compared against (same directory as --all-txt),
    not in qa/endurance/ -- this is raw corpus data, not an analysis report."""
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        for row in sorted(jt9_rows, key=lambda r: r["ts"]):
            fh.write(f"{row['ts']}     {dial_mhz} Rx FT8 {row['snr']:>5.0f} "
                     f"{row['dt']:>5.1f} {row['freq_hz']:>5.0f} {row['message']}\n")
    print(f"wrote {out_path} ({len(jt9_rows)} lines)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all-txt", required=True, help="Path to the session's ALL.TXT")
    ap.add_argument("--wav-dir", required=True, help="Path to the session's cycle-audio-archive dir")
    ap.add_argument("--out", required=True, help="Output path for anova_report.md")
    ap.add_argument("--jt9-exe", default=DEFAULT_JT9_EXE)
    ap.add_argument("--jt9-depth", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None,
                     help="Only use the N most recent WAVs (smoke-testing / avoiding "
                          "CPU contention against a still-live daemon)")
    ap.add_argument("--run-label", default=None)
    ap.add_argument("--max-workers", type=int, default=None,
                     help="Parallel jt9 batches to run at once. Defaults to "
                          f"os.cpu_count() minus {DEFAULT_CPU_HEADROOM} (floored at 1), "
                          "reserving headroom so the machine stays usable during an "
                          "unattended run. Pass os.cpu_count() explicitly for a "
                          "full-throttle run on a confirmed-idle machine.")
    ap.add_argument("--jt9-batch-size", type=int, default=JT9_BATCH_SIZE,
                     help=f"WAVs per jt9 invocation (default {JT9_BATCH_SIZE}, sized to "
                          f"stay under Windows' command-line length limit). Lower this "
                          f"to exercise the parallel path against a small corpus.")
    args = ap.parse_args()

    if not os.path.isfile(args.jt9_exe):
        print(f"[ERROR] jt9 not found at {args.jt9_exe}", file=sys.stderr)
        return 2

    wav_names = sorted(f for f in os.listdir(args.wav_dir) if f.lower().endswith(".wav"))
    if args.limit is not None:
        wav_names = wav_names[-args.limit:]
    wav_paths = [os.path.join(args.wav_dir, f) for f in wav_names]
    cycle_set = {os.path.splitext(f)[0] for f in wav_names}

    print(f"WAV cycles: {len(wav_paths)}")
    if not wav_paths:
        print("[ERROR] no WAV files found", file=sys.stderr)
        return 2

    ours_all = ac.parse_all_txt(args.all_txt)
    ours_rows = [r for r in ours_all if r["ts"] in cycle_set]
    print(f"our decodes in window: {len(ours_rows)}")

    print(f"running jt9 (-d {args.jt9_depth}) over {len(wav_paths)} WAVs...")
    jt9_rows = run_jt9(args.jt9_exe, wav_paths, args.jt9_depth,
                        max_workers=args.max_workers, batch_size=args.jt9_batch_size)
    print(f"jt9 decodes in window: {len(jt9_rows)}")

    # Preserve jt9's raw decode output as its own ALL.TXT-format file, alongside the
    # OpenWSFZ ALL.TXT it was compared against -- raw corpus data belongs in the artefacts
    # folder next to everything else it was decoded from, not thrown away once the ANOVA
    # stats are computed (Captain, 2026-07-30).
    dial_mhz = extract_dial_mhz(args.all_txt)
    jt9_all_txt_path = os.path.join(os.path.dirname(os.path.abspath(args.all_txt)), "jt9_ALL.TXT")
    write_jt9_all_txt(jt9_rows, dial_mhz, jt9_all_txt_path)

    pairs = ac.match_pairs(ours_rows, jt9_rows)
    print(f"matched pairs: {len(pairs)}")

    run_label = args.run_label or f"{args.wav_dir} ({len(wav_paths)} cycles)"
    meta = {
        "run_label": run_label,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "a_label": "OpenWSFZ",
        "b_label": "jt9",
        "n_a": len(ours_rows),
        "n_b": len(jt9_rows),
        "n_pairs": len(pairs),
        "n_wavs": len(wav_paths),
        "method_note": (
            "jt9's decodes were obtained by re-running WSJT-X's own decode engine "
            "(jt9.exe) against each archived WAV in this window -- used here because "
            "there is no live third-party decode log already covering this feed (see "
            "endurance_anova_wsjtx.py for the 40m case, where one exists and no "
            "re-decode is needed)."
        ),
    }

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    out_stem = os.path.splitext(os.path.basename(args.out))[0]

    response_results = ac.run_responses(pairs, out_dir, out_stem, "OpenWSFZ", "jt9")

    report = ac.render_report(response_results, meta)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"wrote {args.out}")
    ac.render_markdown_html(args.out)
    for resp, _stats, chart_files in response_results:
        if chart_files[0]:
            print(f"wrote {os.path.join(out_dir, chart_files[0])}")
            print(f"wrote {os.path.join(out_dir, chart_files[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
