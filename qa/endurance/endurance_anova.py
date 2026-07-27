#!/usr/bin/env python3
"""Endurance-session ANOVA: matched-decode SNR agreement between OpenWSFZ and jt9.

Built as a standard step for every unattended endurance session (Captain's
instruction, 2026-07-27 -- "I want the ANOVA analysis built in for every unattended
durance session"). Run this against a session's ALL.TXT + cycle-audio-archive WAVs
once the session closes; it produces anova_report.md as a standard artefact.

DESIGN, AND WHY IT DIFFERS FROM THE EXISTING qa/rr-study ANOVA
----------------------------------------------------------------
qa/rr-study/harness/anova_compute.py runs a two-way ANOVA WITH replication (3 trials
per Part x Appraiser cell), because its synthetic corpus could construct repeated
independent draws of "the same nominal condition". A live off-air session cannot do
that -- each real transmission happens once. There is no trial axis.

This script instead uses a two-way ANOVA WITHOUT replication (a randomized complete
block design): Part = one matched decode instance (paired by cycle + normalised
message text, so both appraisers are being scored on the identical real signal),
Appraiser = {OpenWSFZ, jt9}, response = reported SNR (dB). Blocking on Part removes
part-to-part variance from the Appraiser comparison without needing repeat trials.

CONSEQUENCE, STATED PLAINLY: with exactly one observation per Part x Appraiser cell,
the Part x Appraiser interaction and the residual/error term are mathematically
confounded (a standard, well-known property of unreplicated factorial designs, not a
defect in this script). This table can say whether the two appraisers' *mean*
reported SNR differs, after removing part-to-part variation (the Appraiser row). It
cannot separately test whether that difference itself varies signal-to-signal.

What any of this MEANS for D-001, row 4/5, or any cross-run/cross-session
comparison is explicitly not this script's business -- per the Captain's own
instruction, that reading is Architect/Captain territory. This script only produces
the numbers.

NFR-021: message text (real third-party callsigns) is read only to build the match
key; it is never printed to stdout/stderr and never written to any output file.
Only aggregate counts and statistics reach anova_report.md.
ASCII-only console output (HK-009).

PARALLELISM: jt9 is invoked once per batch (batched only to stay under Windows'
command-line length limit, see JT9_BATCH_SIZE below). Each invocation is an external
process that spends nearly all its time inside jt9 itself, not inside the Python
interpreter, so Python's GIL is not a bottleneck -- batches are run concurrently with
a plain ThreadPoolExecutor rather than multiprocessing (simpler, no pickling, no
Windows spawn-guard concerns). Original default was every logical CPU the machine
reports (Captain's instruction, 2026-07-27 -- "use the maximum available resources");
REVISED 2026-07-28 after an unattended run at that default saturated a live 16-core
machine and required manually killing several still-running jt9.exe processes --
default now reserves DEFAULT_CPU_HEADROOM logical CPUs so the machine stays usable
during an unattended run. Pass --max-workers explicitly (e.g. --max-workers
$(nproc)) for a genuine full-throttle run when the machine is confirmed idle.

Usage:
    python endurance_anova.py --all-txt ALL.TXT --wav-dir <cycle-audio dir> \\
        --out anova_report.md [--jt9-exe PATH] [--jt9-depth 3] [--limit N] \\
        [--max-workers N] [--jt9-batch-size N] [--run-label "2026-07-27 80m endurance"]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import os
import re
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    # line_buffering=True: this script's progress prints (batch N/M starting/done)
    # are the only visibility into a run that can take the better part of an hour --
    # without it, output sits in Python's block buffer and a background/redirected
    # run looks stalled even while working (seen live, 2026-07-27).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

DEFAULT_JT9_EXE = r"D:\WSJT\wsjtx\bin\jt9.exe"

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")
_TS6_RE = re.compile(r"^\d{6}$")
_NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def normalize_hash_tokens(message: str) -> str:
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def parse_all_txt(path: str) -> list[dict]:
    """This repo's ALL.TXT writer format: ts dial Rx MODE snr dt freq message..."""
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                continue
            try:
                snr = float(tok[4])
            except ValueError:
                continue
            rows.append({"ts": tok[0], "snr": snr, "message": " ".join(tok[7:])})
    return rows


def parse_jt9_stdout(text: str, hhmmss_to_ts: dict[str, str]) -> tuple[list[dict], int]:
    """jt9 -8 stdout format: HHMMSS SNR DT FREQ MARKER MESSAGE...

    jt9's own stdout carries only a bare HHMMSS, not a date -- it does not know what
    calendar date the WAV it just decoded came from. `hhmmss_to_ts` resolves each
    row's HHMMSS back to the *specific source WAV's own* "YYMMDD_HHMMSS" stem (built
    from the actual filenames fed to this run, across the whole corpus, not just the
    current batch). This matters: an endurance session commonly spans UTC midnight
    (e.g. a 21:06->08:52 overnight run), and naively prepending one assumed date to
    every line in a batch would silently mislabel every post-midnight decode with the
    wrong date -- corrupting the cycle-matching key without raising any error. Returns
    (rows, unmatched_count) -- unmatched HHMMSS values are dropped, not guessed at.
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
        except ValueError:
            continue
        rows.append({"ts": ts, "snr": snr, "message": " ".join(tok[5:])})
    return rows, unmatched


# Logical CPUs reserved (never handed to jt9 workers) when --max-workers isn't given
# explicitly, so an unattended run leaves the machine usable rather than saturating
# every core (see PARALLELISM note above; found live, 2026-07-28). Floored at 1 worker
# regardless of how small os.cpu_count() is.
DEFAULT_CPU_HEADROOM = 4

# Conservative per-invocation batch size: Windows' CreateProcess command-line limit is
# ~32767 chars. Repo-tree WAV paths run well under 150 chars each in practice; 150
# files/batch keeps the joined argv comfortably under that limit regardless of exactly
# how deep a given checkout path is, without needing to measure it per run.
# Overridable via --jt9-batch-size (mainly useful for testing the parallel path
# against a small corpus, where the default would only ever produce one batch).
JT9_BATCH_SIZE = 150


def _run_one_jt9_batch(jt9_exe: str, batch: list[str], depth: int,
                        hhmmss_to_ts: dict[str, str], timeout_secs: int,
                        batch_num: int, total_batches: int) -> tuple[list[dict], int]:
    """Runs a single jt9 batch to completion. Designed to be called from a thread
    pool -- everything it touches (its own TemporaryDirectory, its own subprocess)
    is local to this call, so concurrent invocations don't share mutable state."""
    print(f"  jt9 batch {batch_num}/{total_batches} starting ({len(batch)} files)...")
    with tempfile.TemporaryDirectory(prefix="endurance_anova_jt9_") as scratch:
        # subprocess cwd is `scratch`, not the caller's cwd -- WAV paths must be
        # absolute or jt9 can't find its own input files against the new cwd
        # (found live, 2026-07-27: relative paths silently produced jt9 exit 2 /
        # zero decodes with no other diagnostic).
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
    # Measured ~1s/file wall time (2026-07-27 timing probe, this machine). 5s/file
    # per batch gives generous headroom without needing a hand-tuned timeout per run.
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
        # thread pool achieves real OS-level parallelism here despite Python's GIL --
        # no multiprocessing/pickling needed, since each worker's actual work happens
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


def match_pairs(ours_rows: list[dict], jt9_rows: list[dict]) -> list[tuple]:
    """Pair matched decodes (same cycle, same normalised message text) between the
    two appraisers. Returns list of (part_key, ours_snr, jt9_snr). Never returns or
    logs the message text itself -- only the paired SNR values survive past this
    function (NFR-021)."""
    ours_by_key: dict[tuple, list[float]] = {}
    for r in ours_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        ours_by_key.setdefault(key, []).append(r["snr"])
    jt9_by_key: dict[tuple, list[float]] = {}
    for r in jt9_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        jt9_by_key.setdefault(key, []).append(r["snr"])

    pairs = []
    part_index = 0
    for key in sorted(set(ours_by_key) & set(jt9_by_key)):
        o_snrs = ours_by_key[key]
        j_snrs = jt9_by_key[key]
        for o, j in zip(o_snrs, j_snrs):
            part_index += 1
            pairs.append((part_index, o, j))
    return pairs


def two_way_anova_no_replication(pairs: list[tuple]) -> dict:
    """Randomized complete block design, no replication: Part (block, b levels) x
    Appraiser (a=2 levels), response = reported SNR."""
    b = len(pairs)
    a = 2
    N = a * b

    ours_vals = [p[1] for p in pairs]
    jt9_vals = [p[2] for p in pairs]
    all_vals = ours_vals + jt9_vals
    grand_mean = sum(all_vals) / N

    part_means = [(p[1] + p[2]) / 2 for p in pairs]
    appraiser_means = {"ours": sum(ours_vals) / b, "jt9": sum(jt9_vals) / b}

    ss_part = a * sum((pm - grand_mean) ** 2 for pm in part_means)
    ss_appraiser = b * sum((am - grand_mean) ** 2 for am in appraiser_means.values())
    ss_total = sum((v - grand_mean) ** 2 for v in all_vals)
    ss_error = max(0.0, ss_total - ss_part - ss_appraiser)  # confounded w/ interaction, n=1/cell

    df_part = b - 1
    df_appraiser = a - 1
    df_error = df_part * df_appraiser  # = b - 1 when a = 2
    df_total = N - 1

    ms_part = ss_part / df_part if df_part > 0 else float("nan")
    ms_appraiser = ss_appraiser / df_appraiser
    ms_error = ss_error / df_error if df_error > 0 else float("nan")

    from scipy.stats import f as fdist
    if ms_error and ms_error > 0:
        f_appraiser = ms_appraiser / ms_error
        f_part = ms_part / ms_error
        p_appraiser = 1 - fdist.cdf(f_appraiser, df_appraiser, df_error)
        p_part = 1 - fdist.cdf(f_part, df_part, df_error)
    else:
        f_appraiser = f_part = float("nan")
        p_appraiser = p_part = float("nan")

    return {
        "b": b, "a": a, "N": N, "grand_mean": grand_mean,
        "appraiser_means": appraiser_means,
        "ss_part": ss_part, "ss_appraiser": ss_appraiser,
        "ss_error": ss_error, "ss_total": ss_total,
        "df_part": df_part, "df_appraiser": df_appraiser,
        "df_error": df_error, "df_total": df_total,
        "ms_part": ms_part, "ms_appraiser": ms_appraiser, "ms_error": ms_error,
        "f_appraiser": f_appraiser, "f_part": f_part,
        "p_appraiser": p_appraiser, "p_part": p_part,
    }


def render_charts(pairs: list[tuple], stats: dict, out_dir: str, stem: str) -> tuple[str | None, str | None]:
    """Writes <stem>_scatter.png and <stem>_residual.png into out_dir, alongside the
    markdown report (render_report.py displays images by relative path, so they must
    live next to the .md/.html they're referenced from). Returns their basenames, or
    (None, None) if there are too few pairs to plot anything meaningful.

    Only ever touches the numeric (part_index, ours_snr, jt9_snr) tuples match_pairs()
    already produced -- never message text (NFR-021).
    """
    if len(pairs) < 2:
        return None, None

    import matplotlib
    matplotlib.use("Agg")  # headless -- this script commonly runs backgrounded/unattended
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    # Sequential-magnitude ramp, single hue light->dark (dataviz skill, palette.md
    # "Sequential hue": blue, steps 100->700). A flat alpha-blended scatter of tens
    # of thousands of same-hue points was found live (2026-07-28) to make density
    # differences nearly illegible with no scale to read them against -- this ramp
    # plus an explicit colorbar replaces that with a real, explicit encoding.
    _SEQ_BLUE_STEPS = [
        "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
        "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
    ]
    seq_cmap = LinearSegmentedColormap.from_list("seq_blue", _SEQ_BLUE_STEPS)
    SURFACE = "#fcfcfb"
    INK_PRIMARY = "#0b0b0b"
    INK_SECONDARY = "#52514e"
    INK_MUTED = "#898781"

    ours = [p[1] for p in pairs]
    jt9 = [p[2] for p in pairs]
    diffs = [o - j for o, j in zip(ours, jt9)]
    mean_diff = stats["appraiser_means"]["ours"] - stats["appraiser_means"]["jt9"]
    # hexbin's own binning needs a reasonable grid density regardless of n; a small
    # corpus just yields mostly-empty bins with count 1, which is still an honest
    # (if sparse) picture -- no separate small-n code path needed.
    gridsize = min(60, max(10, len(pairs) // 20))

    # -- Scatter: OpenWSFZ vs jt9, one point per matched Part, density-binned -------
    fig, ax = plt.subplots(figsize=(7.5, 7))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    hb = ax.hexbin(jt9, ours, gridsize=gridsize, cmap=seq_cmap, mincnt=1,
                    bins="log", linewidths=0.1)
    lo, hi = min(min(jt9), min(ours)), max(max(jt9), max(ours))
    ax.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1.2, color=INK_SECONDARY,
             label="y = x (perfect agreement)")
    cb = fig.colorbar(hb, ax=ax, shrink=0.8)
    cb.set_label("matched pairs per bin (log scale)", color=INK_SECONDARY, fontsize=9)
    cb.ax.tick_params(labelcolor=INK_MUTED)
    ax.set_xlabel("jt9 reported SNR (dB)", color=INK_SECONDARY)
    ax.set_ylabel("OpenWSFZ reported SNR (dB)", color=INK_SECONDARY)
    ax.set_title(f"Matched-decode SNR: OpenWSFZ vs jt9 (n={len(pairs)} pairs)", color=INK_PRIMARY)
    ax.tick_params(colors=INK_MUTED)
    ax.legend(loc="upper left", fontsize=8, facecolor=SURFACE, edgecolor=INK_MUTED)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    scatter_name = f"{stem}_scatter.png"
    fig.savefig(os.path.join(out_dir, scatter_name), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    # -- Residual/Part-effect: per-pair (ours - jt9) vs jt9 SNR, density-binned -----
    # Answers directly: is the Appraiser gap a flat offset (density hugs the
    # mean-diff line regardless of signal strength) or does it vary with how strong
    # the signal is (visible slope/trend in where the density sits)? This is the
    # closest thing to an interaction check the RCBD-without-replication design can
    # offer -- see the report's own caveat.
    fig, ax = plt.subplots(figsize=(9.5, 5))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    hb = ax.hexbin(jt9, diffs, gridsize=gridsize, cmap=seq_cmap, mincnt=1,
                    bins="log", linewidths=0.1)
    ax.axhline(mean_diff, linestyle="--", linewidth=1.2, color=INK_SECONDARY,
               label=f"mean diff = {mean_diff:+.2f} dB")
    cb = fig.colorbar(hb, ax=ax, shrink=0.8)
    cb.set_label("matched pairs per bin (log scale)", color=INK_SECONDARY, fontsize=9)
    cb.ax.tick_params(labelcolor=INK_MUTED)
    ax.set_xlabel("jt9 reported SNR (dB)", color=INK_SECONDARY)
    ax.set_ylabel("OpenWSFZ - jt9 (dB)", color=INK_SECONDARY)
    ax.set_title("Per-Part residual -- does the Appraiser gap depend on signal strength?",
                 color=INK_PRIMARY)
    ax.tick_params(colors=INK_MUTED)
    ax.legend(loc="best", fontsize=8, facecolor=SURFACE, edgecolor=INK_MUTED)
    fig.tight_layout()
    residual_name = f"{stem}_residual.png"
    fig.savefig(os.path.join(out_dir, residual_name), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    return scatter_name, residual_name


def render_report(stats: dict, meta: dict,
                   chart_files: tuple[str | None, str | None] = (None, None)) -> str:
    L = []
    L.append("# Endurance-session ANOVA -- matched-decode SNR (OpenWSFZ vs jt9)")
    L.append("")
    L.append(f"**Run:** {meta['run_label']}  ")
    L.append(f"**Generated:** {meta['generated_utc']} (`date -u`, HK-017)  ")
    L.append("**Design:** two-way ANOVA without replication (randomized complete block "
              "design) -- Part (matched decode instance) x Appraiser (OpenWSFZ, jt9), "
              "response = reported SNR (dB). See this script's docstring for why this "
              "design applies to single-pass live data, and not the replicated design "
              "in `qa/rr-study/harness/anova_compute.py`.")
    L.append("")
    L.append(f"- WAV cycles fed to jt9: **{meta['n_wavs']}**")
    L.append(f"- Our decodes in window: **{meta['n_ours']}**")
    L.append(f"- jt9 decodes in window: **{meta['n_jt9']}**")
    L.append(f"- Matched pairs (Parts, used below): **{stats['b']}**")
    L.append("")
    if stats["b"] < 2:
        L.append("**Too few matched pairs to compute an ANOVA table (need >= 2).** "
                  "Re-run against a larger window.")
        return "\n".join(L) + "\n"
    scatter_name, residual_name = chart_files
    if scatter_name:
        L.append("## Charts")
        L.append("")
        L.append(f"![Matched-decode SNR scatter: OpenWSFZ vs jt9]({scatter_name})")
        L.append("")
        if residual_name:
            L.append(f"![Per-Part residual vs jt9 SNR]({residual_name})")
            L.append("")
    L.append("## ANOVA table")
    L.append("")
    L.append("| Source | SS | df | MS | F | P |")
    L.append("|---|---:|---:|---:|---:|---:|")
    L.append(f"| Part | {stats['ss_part']:.4f} | {stats['df_part']} | "
              f"{stats['ms_part']:.4f} | {stats['f_part']:.3f} | {stats['p_part']:.4f} |")
    L.append(f"| Appraiser | {stats['ss_appraiser']:.4f} | {stats['df_appraiser']} | "
              f"{stats['ms_appraiser']:.4f} | {stats['f_appraiser']:.3f} | "
              f"{stats['p_appraiser']:.4f} |")
    L.append(f"| Residual (confounded with interaction, n=1/cell) | "
              f"{stats['ss_error']:.4f} | {stats['df_error']} | {stats['ms_error']:.4f} | | |")
    L.append(f"| Total | {stats['ss_total']:.4f} | {stats['df_total']} | | | |")
    L.append("")
    L.append("## Appraiser means (matched-decode SNR, dB)")
    L.append("")
    L.append(f"- OpenWSFZ mean: {stats['appraiser_means']['ours']:.3f} dB")
    L.append(f"- jt9 mean: {stats['appraiser_means']['jt9']:.3f} dB")
    L.append(f"- Grand mean: {stats['grand_mean']:.3f} dB")
    L.append("")
    L.append("## Caveat (structural, not a defect)")
    L.append("")
    L.append("With one observation per Part x Appraiser cell -- a live signal happens "
              "once -- the interaction term and the residual/error term are "
              "mathematically confounded (standard property of an unreplicated "
              "factorial design). This table can say whether the two appraisers' "
              "*mean* reported SNR differs after removing part-to-part variation (the "
              "Appraiser row); it cannot separately test whether that difference "
              "itself varies signal-to-signal.")
    L.append("")
    L.append("Cross-run comparison and interpretation of these numbers is "
              "Architect/Captain territory, not this script's.")
    L.append("")
    return "\n".join(L) + "\n"


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
                     help=f"WAVs per jt9 invocation (default {JT9_BATCH_SIZE}, sized "
                          f"to stay under Windows' command-line length limit). Lower "
                          f"this to exercise the parallel path against a small corpus.")
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

    ours_all = parse_all_txt(args.all_txt)
    ours_rows = [r for r in ours_all if r["ts"] in cycle_set]
    print(f"our decodes in window: {len(ours_rows)}")

    print(f"running jt9 (-d {args.jt9_depth}) over {len(wav_paths)} WAVs...")
    jt9_rows = run_jt9(args.jt9_exe, wav_paths, args.jt9_depth,
                        max_workers=args.max_workers, batch_size=args.jt9_batch_size)
    print(f"jt9 decodes in window: {len(jt9_rows)}")

    pairs = match_pairs(ours_rows, jt9_rows)
    print(f"matched pairs: {len(pairs)}")

    stats = two_way_anova_no_replication(pairs) if len(pairs) >= 2 else {"b": len(pairs)}

    run_label = args.run_label or f"{args.wav_dir} ({len(wav_paths)} cycles)"
    meta = {
        "run_label": run_label,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_wavs": len(wav_paths),
        "n_ours": len(ours_rows),
        "n_jt9": len(jt9_rows),
    }

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    out_stem = os.path.splitext(os.path.basename(args.out))[0]
    chart_files = (None, None)
    if len(pairs) >= 2:
        print("rendering charts...")
        chart_files = render_charts(pairs, stats, out_dir, out_stem)

    report = render_report(stats, meta, chart_files)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"wrote {args.out}")
    if chart_files[0]:
        print(f"wrote {os.path.join(out_dir, chart_files[0])}")
        print(f"wrote {os.path.join(out_dir, chart_files[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
