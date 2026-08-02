#!/usr/bin/env python3
"""Shared matched-decode ANOVA machinery for endurance-session appraiser comparisons.

Split out 2026-07-30 (Captain's instruction) from what was a single `endurance_anova.py`,
after establishing that re-decoding via `jt9` is only necessary when there is no live
third-party decode log already covering the same feed:

  - The 40m instance runs alongside the real WSJT-X application on the same physical radio
    the whole session -- WSJT-X's own ALL.TXT is already a complete decode log once the
    session's artefacts are gathered (tools/gather_live_run_artefacts.py). Re-decoding ~24h
    of archived WAVs through `jt9` to reproduce data that already exists on disk is waste.
  - An SDR-fed instance (e.g. SDR Uno retuned across bands) has no live WSJT-X counterpart
    at all -- the only way to get a second appraiser's opinion is to re-decode the archived
    WAVs, which is exactly what `jt9` (the same decode engine WSJT-X calls internally) is
    for.

This module holds everything that doesn't care how the second appraiser's rows were
obtained: ALL.TXT parsing, Part-matching, the two-way-ANOVA-without-replication design,
chart rendering, and report rendering. See:
  - endurance_anova_jt9.py    -- OpenWSFZ vs jt9 (re-decodes WAVs; for a multiband/no-live-
                                 counterpart instance)
  - endurance_anova_wsjtx.py  -- OpenWSFZ vs the real WSJT-X application's own ALL.TXT (no
                                 re-decode; for the 40m instance)

DESIGN (unchanged from the original script)
--------------------------------------------
qa/rr-study/harness/anova_compute.py runs a two-way ANOVA WITH replication (3 trials per
Part x Appraiser cell), because its synthetic corpus could construct repeated independent
draws of "the same nominal condition". A live off-air session cannot do that -- each real
transmission happens once. There is no trial axis.

This module instead uses a two-way ANOVA WITHOUT replication (a randomized complete block
design): Part = one matched decode instance (paired by cycle + normalised message text, so
both appraisers are being scored on the identical real signal), Appraiser = {OpenWSFZ,
<second appraiser>}. Blocking on Part removes part-to-part variance from the Appraiser
comparison without needing repeat trials.

MULTIPLE RESPONSES: the same matched Parts carry three independently-reported numeric
fields per decode -- SNR (dB), DT (time offset, s), and reported frequency offset (Hz).
Each gets its own ANOVA table run over the identical Part set (see RESPONSES below).

CONSEQUENCE, STATED PLAINLY: with exactly one observation per Part x Appraiser cell, the
Part x Appraiser interaction and the residual/error term are mathematically confounded (a
standard, well-known property of unreplicated factorial designs, not a defect), for every
response above. Each table can say whether the two appraisers' *mean* value differs, after
removing part-to-part variation (the Appraiser row). None of them can separately test
whether that difference itself varies signal-to-signal.

What any of this MEANS for D-001, or any cross-run/cross-session comparison, is explicitly
not this module's business -- that reading is Architect/Captain territory. This module only
produces the numbers.

NFR-021: message text (real third-party callsigns) is read only to build the match key; it
is never printed to stdout/stderr and never written to any output file. Only aggregate
counts and statistics reach the rendered report.
ASCII-only console output (HK-009).

ESTIMATOR CONVENTION -- ratio-of-sums, never mean-of-ratios (T3 item 4, 2026-08-02 hand-off).
Any decode-count ratio in this programme (e.g. one instance's decodes over another's, over a
set of cycles/strata/parts) is computed as SUM(numerator)/SUM(denominator), never as the
average of each part's own numerator/denominator ratio. Mean-of-ratios weights a 2-decode
cycle the same as a 40-decode one, which is wrong whenever cycle-to-cycle decode volume
varies -- exactly the live-corpus case. This was not academic: on 2026-08-02 the Architect's
own +1s-stratum prediction flipped sign (+1.5% under mean-of-ratios vs the correct -2.9% under
ratio-of-sums, see `…-1813-architect-corrections-to-record-drift-controls-and-my-own-errors.md`
§6), which cost part of an argument about whether the drift effect was a gradient or a
threshold. See ratio_of_sums() below for the canonical implementation, and
qa/endurance/drift_stratum_control_ratio.py for a worked example (its Table C sums
decode_count per stratum before dividing, exactly to avoid this).
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")
_TS_RE = re.compile(r"^(\d{6}_\d{6})")
_TS_FMT = "%y%m%d_%H%M%S"


def normalize_hash_tokens(message: str) -> str:
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def parse_cycle_ts(token: str) -> datetime.datetime | None:
    """Parse a WSJT-X/OpenWSFZ cycle timestamp token (`YYMMDD_HHMMSS`)."""
    try:
        return datetime.datetime.strptime(token, _TS_FMT)
    except ValueError:
        return None


# FT8's fixed cycle length -- the grid every cycle timestamp is supposed to land on exactly.
# Added 2026-08-02 per the grid-artefact correction (qa/cycleframer-alignment-replay/2026-08-
# 02-1714-...-correction-cycle-grid-artefact-voids-8080-anova.md): 8080's capture clock
# drifts off this grid at ~0.18 s/h, resetting only on process restart, and match_pairs()'s
# exact-(ts, message) key silently fails to match any decode stamped off-grid -- not because
# the decode was missed, but because its cycle label was wrong. That is a real, measured
# degradation (DT/SNR both track the offset, see the correction's §2.3), not merely cosmetic
# mislabelling, so grid-snapping is an explicit, opt-in, always-labelled step -- never a
# silent default -- see apply_grid_snap()/compute_grid_gate() below.
FT8_CYCLE_SECONDS = 15


def ts_offset_seconds(token: str) -> int | None:
    """How many seconds past the enclosing 15s FT8 grid boundary this timestamp sits (0 =
    exactly on-grid). None if unparseable. This is the per-decode drift-stratification
    factor the 2026-08-02 correction introduced."""
    dt = parse_cycle_ts(token)
    if dt is None:
        return None
    total = dt.hour * 3600 + dt.minute * 60 + dt.second
    return total % FT8_CYCLE_SECONDS


def snap_ts_to_grid(token: str) -> str:
    """Floor a cycle timestamp to its enclosing 15s FT8 grid boundary. FLOOR, not round --
    per the 2026-08-02-1721 spec's §4: the drift is one-directional (late), so rounding would
    walk a heavily-drifted timestamp into the WRONG neighbouring cycle instead of back to the
    cycle it actually belongs to. Returns the token unchanged if unparseable."""
    dt = parse_cycle_ts(token)
    if dt is None:
        return token
    total = dt.hour * 3600 + dt.minute * 60 + dt.second
    snapped_total = total - (total % FT8_CYCLE_SECONDS)
    snapped_dt = (dt.replace(hour=0, minute=0, second=0, microsecond=0) +
                  datetime.timedelta(seconds=snapped_total))
    return snapped_dt.strftime(_TS_FMT)


def apply_grid_snap(rows: list[dict]) -> list[dict]:
    """Returns NEW row dicts (never mutates the input) with `orig_ts` and `offset` recorded
    and `ts` replaced by its grid-snapped value. Strictly opt-in -- callers decide which
    side(s), if any, get this applied before match_pairs() sees them. match_pairs() itself is
    UNCHANGED and still keys on exact (ts, message) -- correct behaviour for its documented
    purpose (2026-08-02 correction §1) -- it simply now sees the snapped ts for whichever rows
    were routed through this function first."""
    out = []
    for r in rows:
        nr = dict(r)
        nr["orig_ts"] = r["ts"]
        nr["offset"] = ts_offset_seconds(r["ts"])
        nr["ts"] = snap_ts_to_grid(r["ts"])
        out.append(nr)
    return out


def compute_grid_gate(rows: list[dict]) -> dict:
    """The mechanical gate from the 2026-08-02 correction's §6 (per HK-021): fraction of this
    log's UNIQUE cycle timestamps that already sit exactly on the 15s FT8 grid, evaluated on
    RAW (pre-snap) rows -- this IS the check for whether snapping/stratification is needed,
    not a result of having applied it already. Rows mutually exclusive, evaluated in order,
    hard threshold 0.99 (not "close to 1"):
        ROW 1: G >= 0.99  -> PASS -- matched-decode analysis may pool freely.
        ROW 2: 0.99 > G   -> VOID -- must not pool; grid-snap and stratify instead.
    """
    unique_ts = sorted(set(r["ts"] for r in rows))
    n = len(unique_ts)
    on_grid = sum(1 for ts in unique_ts if ts_offset_seconds(ts) == 0)
    g = (on_grid / n) if n else float("nan")
    row = 1 if g >= 0.99 else 2
    return {
        "g": g, "n_unique_ts": n, "n_on_grid": on_grid,
        "row": row, "verdict": "PASS" if row == 1 else "VOID",
    }


def parse_time_arg(value: str, date_arg: str | None) -> datetime.datetime:
    """Accept either a full `YYYY-MM-DD HH:MM[:SS]` or a bare `HH:MM[:SS]` combined with a
    date (defaulting to today). Same shape as tools/gather_live_run_artefacts.py's
    parse_datetime_arg -- duplicated rather than imported, since qa/endurance and tools/
    aren't set up as importable packages across each other."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            pass
    base_date = date_arg or datetime.datetime.now().strftime("%Y%m%d")
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.datetime.strptime(value, fmt).time()
            return datetime.datetime.combine(
                datetime.datetime.strptime(base_date, "%Y%m%d").date(), t
            )
        except ValueError:
            pass
    raise SystemExit(
        f"error: could not parse '{value}' as a time -- use HH:MM[:SS] (with --date) "
        f"or 'YYYY-MM-DD HH:MM[:SS]'"
    )


def filter_rows_by_window(
    rows: list[dict], start: datetime.datetime | None, end: datetime.datetime | None
) -> list[dict]:
    """Restrict rows (as returned by parse_all_txt) to [start, end] by their own ts token.
    A None bound is treated as unbounded on that side. No-op if both bounds are None."""
    if start is None and end is None:
        return rows
    out = []
    for r in rows:
        ts = parse_cycle_ts(r["ts"])
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts > end:
            continue
        out.append(r)
    return out


def parse_all_txt(path: str) -> list[dict]:
    """This repo's ALL.TXT writer format: ts dial Rx MODE snr dt freq message...

    Also matches the real WSJT-X application's own ALL.TXT format -- OpenWSFZ's
    AllTxtWriter deliberately mimics it, so this one parser reads both files.

    Captures all three paired numeric metrics this module compares -- snr (dB), dt (time
    offset, s), freq_hz (reported frequency offset, Hz) -- not just snr, so a row that's
    unparseable in any one of the three is skipped entirely rather than silently admitted
    with a missing field (a row failing to parse means genuine corruption, not an optional
    field).
    """
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
                dt = float(tok[5])
                freq_hz = float(tok[6])
            except ValueError:
                continue
            rows.append({"ts": tok[0], "snr": snr, "dt": dt, "freq_hz": freq_hz,
                        "message": " ".join(tok[7:])})
    return rows


#: Metrics compared between the two appraisers, each run as its own ANOVA table over the
#: identical matched Parts. `key` matches the field names parse_all_txt/parse_jt9_stdout
#: populate; `fmt` is the display precision used in the report's appraiser-means bullets.
RESPONSES: list[dict] = [
    {"key": "snr", "label": "SNR", "unit": "dB", "fmt": "{:.3f}"},
    {"key": "dt", "label": "DT (time offset)", "unit": "s", "fmt": "{:.4f}"},
    {"key": "freq_hz", "label": "Frequency offset", "unit": "Hz", "fmt": "{:.1f}"},
]


def match_pairs(a_rows: list[dict], b_rows: list[dict]) -> list[dict]:
    """Pair matched decodes (same cycle, same normalised message text) between the two
    appraisers ('a' = OpenWSFZ always, by convention; 'b' = whichever second appraiser the
    caller is comparing against). Returns one dict per matched Part:
    {"part": index, "a_<key>": v, "b_<key>": v, ...} for every key in RESPONSES.
    Never returns or logs the message text itself -- only the paired numeric metrics
    survive past this function (NFR-021); the message is used solely to build the match
    key and is discarded once each row dict has served that purpose.

    UNCHANGED matching behaviour (2026-08-02 correction §1: this is correct as written and
    stays the default) -- keys on the exact `ts` each row carries. If a caller ran a side's
    rows through apply_grid_snap() first, `ts` there is already the snapped value, so this
    function's own logic never needs to know grid-snapping happened at all. The only
    addition is propagating each row's `offset` field (if present) into the returned pair as
    `a_offset`/`b_offset`, purely a pass-through for stratify_pairs() -- absent entirely for
    rows that were never grid-snapped, so this is a no-op for every pre-existing caller."""
    a_by_key: dict[tuple, list[dict]] = {}
    for r in a_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        a_by_key.setdefault(key, []).append(r)
    b_by_key: dict[tuple, list[dict]] = {}
    for r in b_rows:
        key = (r["ts"], normalize_hash_tokens(r["message"]))
        b_by_key.setdefault(key, []).append(r)

    pairs = []
    part_index = 0
    for key in sorted(set(a_by_key) & set(b_by_key)):
        a_list = a_by_key[key]
        b_list = b_by_key[key]
        for a, b in zip(a_list, b_list):
            part_index += 1
            pair = {"part": part_index}
            for resp in RESPONSES:
                k = resp["key"]
                pair[f"a_{k}"] = a[k]
                pair[f"b_{k}"] = b[k]
            if "offset" in a:
                pair["a_offset"] = a["offset"]
            if "offset" in b:
                pair["b_offset"] = b["offset"]
            pairs.append(pair)
    return pairs


def stratify_pairs(pairs: list[dict], side: str) -> dict[int | None, list[dict]]:
    """Groups match_pairs() output by one side's grid-drift offset (see apply_grid_snap) --
    e.g. stratify_pairs(pairs, "a")[0] is every matched pair where appraiser A's ORIGINAL
    (pre-snap) timestamp landed exactly on-grid. `side` is "a" or "b". Pairs whose side never
    went through apply_grid_snap() (no offset recorded) land under the key None -- calling
    this on non-snapped data is harmless, it just returns {None: <all pairs>}."""
    groups: dict[int | None, list[dict]] = {}
    for p in pairs:
        key = p.get(f"{side}_offset")
        groups.setdefault(key, []).append(p)
    return groups


def render_stratum_breakdown(pairs: list[dict], side: str, a_label: str, b_label: str) -> str:
    """Renders the per-stratum-plus-POOLED breakdown table required whenever a report is
    grid-snapped WITHOUT an explicit single --stratum selected. Implements the 2026-08-02-
    1721 spec's §2 hard rule verbatim: 'no pooled cross-stratum mean of SNR or DT is to be
    reported for 8080, in any table, without the stratum breakdown printed immediately
    beside it.' The POOLED row is always first and always labelled DO-NOT-REPORT, matching
    that spec's own demonstration table -- this function exists so the tool enforces the
    rule mechanically rather than relying on every caller to remember it by hand."""
    groups = stratify_pairs(pairs, side)
    strata = sorted(k for k in groups if k is not None)
    L = []
    L.append("> **Grid-snapped, no single stratum selected.** Per the 2026-08-02 spec: pooling "
              "SNR/DT/frequency across drift strata produces numbers that describe this run's "
              "restart schedule, not the decoder -- the POOLED row below is shown for "
              "transparency only and must never be cited on its own.")
    L.append("")
    for resp in RESPONSES:
        k, label, unit, fmt = resp["key"], resp["label"], resp["unit"], resp["fmt"]
        L.append(f"### {label} ({unit}) -- grid-snapped, by stratum")
        L.append("")
        L.append(f"| stratum | n | {a_label} mean | {b_label} mean | gap ({b_label} minus {a_label}) |")
        L.append("|---|---:|---:|---:|---:|")
        if pairs:
            a_all = [p[f"a_{k}"] for p in pairs]
            b_all = [p[f"b_{k}"] for p in pairs]
            a_mean, b_mean = sum(a_all) / len(a_all), sum(b_all) / len(b_all)
            L.append(f"| **POOLED -- DO NOT REPORT** | {len(pairs)} | {fmt.format(a_mean)} | "
                      f"{fmt.format(b_mean)} | {fmt.format(b_mean - a_mean)} |")
        for s in strata:
            sp = groups[s]
            a_vals = [p[f"a_{k}"] for p in sp]
            b_vals = [p[f"b_{k}"] for p in sp]
            if not a_vals:
                continue
            a_mean, b_mean = sum(a_vals) / len(a_vals), sum(b_vals) / len(b_vals)
            L.append(f"| +{s}s stratum | {len(sp)} | {fmt.format(a_mean)} | "
                      f"{fmt.format(b_mean)} | {fmt.format(b_mean - a_mean)} |")
        L.append("")
    return "\n".join(L) + "\n"


def render_gate_section(gate_a: dict, a_label: str, gate_b: dict, b_label: str) -> str:
    """Renders the mechanical gate (compute_grid_gate) for both appraisers at the top of a
    report, per the 2026-08-02 correction's §6 ('run first and reported at the top of every
    output'). Purely descriptive -- callers decide what to do with ROW 2 (VOID), this
    function does not itself refuse to proceed."""
    L = ["## Grid-alignment gate (per HK-021, 2026-08-02 correction)", ""]
    L.append("| appraiser | unique ts | on-grid | G | row | verdict |")
    L.append("|---|---:|---:|---:|---|---|")
    for label, g in ((a_label, gate_a), (b_label, gate_b)):
        L.append(f"| {label} | {g['n_unique_ts']} | {g['n_on_grid']} | {g['g']:.4f} | "
                  f"ROW {g['row']} | {g['verdict']} |")
    L.append("")
    return "\n".join(L) + "\n"


def response_tuples(pairs: list[dict], key: str) -> list[tuple]:
    """Extracts (part_index, a_value, b_value) tuples for one response metric from
    match_pairs()'s output -- the shape two_way_anova_no_replication() and render_charts()
    expect (both generic over whichever numeric response they're handed)."""
    return [(p["part"], p[f"a_{key}"], p[f"b_{key}"]) for p in pairs]


def two_way_anova_no_replication(pairs: list[tuple]) -> dict:
    """Randomized complete block design, no replication: Part (block, b levels) x
    Appraiser (a=2 levels). Generic over whichever numeric response `pairs` carries (SNR,
    DT, or frequency offset -- see RESPONSES/response_tuples) -- this function itself has
    no notion of units, and no notion of which appraiser is 'a' or 'b'."""
    b_count = len(pairs)
    a_count = 2
    N = a_count * b_count

    a_vals = [p[1] for p in pairs]
    b_vals = [p[2] for p in pairs]
    all_vals = a_vals + b_vals
    grand_mean = sum(all_vals) / N

    part_means = [(p[1] + p[2]) / 2 for p in pairs]
    appraiser_means = {"a": sum(a_vals) / b_count, "b": sum(b_vals) / b_count}

    ss_part = a_count * sum((pm - grand_mean) ** 2 for pm in part_means)
    ss_appraiser = b_count * sum((am - grand_mean) ** 2 for am in appraiser_means.values())
    ss_total = sum((v - grand_mean) ** 2 for v in all_vals)
    ss_error = max(0.0, ss_total - ss_part - ss_appraiser)  # confounded w/ interaction, n=1/cell

    df_part = b_count - 1
    df_appraiser = a_count - 1
    df_error = df_part * df_appraiser  # = b_count - 1 when a_count = 2
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
        "b": b_count, "a": a_count, "N": N, "grand_mean": grand_mean,
        "appraiser_means": appraiser_means,
        "ss_part": ss_part, "ss_appraiser": ss_appraiser,
        "ss_error": ss_error, "ss_total": ss_total,
        "df_part": df_part, "df_appraiser": df_appraiser,
        "df_error": df_error, "df_total": df_total,
        "ms_part": ms_part, "ms_appraiser": ms_appraiser, "ms_error": ms_error,
        "f_appraiser": f_appraiser, "f_part": f_part,
        "p_appraiser": p_appraiser, "p_part": p_part,
    }


def render_charts(pairs: list[tuple], stats: dict, out_dir: str, stem: str,
                   label: str = "SNR", unit: str = "dB",
                   a_label: str = "OpenWSFZ", b_label: str = "jt9",
                   ) -> tuple[str | None, str | None]:
    """Writes <stem>_scatter.png and <stem>_residual.png into out_dir, alongside the
    markdown report (render_report.py displays images by relative path, so they must live
    next to the .md/.html they're referenced from). Returns their basenames, or (None,
    None) if there are too few pairs to plot anything meaningful.

    `pairs` is one response's (part_index, a_value, b_value) tuples, from
    response_tuples() -- this function is generic over whichever metric `label`/`unit`
    describe (SNR/dB, DT/s, Frequency offset/Hz), and whichever appraisers `a_label`/
    `b_label` name; it only ever touches those three numeric fields per tuple, never
    message text (NFR-021).
    """
    if len(pairs) < 2:
        return None, None

    import matplotlib
    matplotlib.use("Agg")  # headless -- these scripts commonly run backgrounded/unattended
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    # Sequential-magnitude ramp, single hue light->dark (dataviz skill, palette.md
    # "Sequential hue": blue, steps 100->700). A flat alpha-blended scatter of tens of
    # thousands of same-hue points was found live (2026-07-28) to make density differences
    # nearly illegible with no scale to read them against -- this ramp plus an explicit
    # colorbar replaces that with a real, explicit encoding.
    _SEQ_BLUE_STEPS = [
        "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
        "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
    ]
    seq_cmap = LinearSegmentedColormap.from_list("seq_blue", _SEQ_BLUE_STEPS)
    SURFACE = "#fcfcfb"
    INK_PRIMARY = "#0b0b0b"
    INK_SECONDARY = "#52514e"
    INK_MUTED = "#898781"

    a_vals = [p[1] for p in pairs]
    b_vals = [p[2] for p in pairs]
    diffs = [av - bv for av, bv in zip(a_vals, b_vals)]
    mean_diff = stats["appraiser_means"]["a"] - stats["appraiser_means"]["b"]
    # hexbin's own binning needs a reasonable grid density regardless of n; a small corpus
    # just yields mostly-empty bins with count 1, which is still an honest (if sparse)
    # picture -- no separate small-n code path needed.
    gridsize = min(60, max(10, len(pairs) // 20))

    # -- Scatter: a_label vs b_label, one point per matched Part, density-binned --------
    fig, ax = plt.subplots(figsize=(7.5, 7))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    hb = ax.hexbin(b_vals, a_vals, gridsize=gridsize, cmap=seq_cmap, mincnt=1,
                    bins="log", linewidths=0.1)
    lo, hi = min(min(b_vals), min(a_vals)), max(max(b_vals), max(a_vals))
    ax.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1.2, color=INK_SECONDARY,
             label="y = x (perfect agreement)")
    cb = fig.colorbar(hb, ax=ax, shrink=0.8)
    cb.set_label("matched pairs per bin (log scale)", color=INK_SECONDARY, fontsize=9)
    cb.ax.tick_params(labelcolor=INK_MUTED)
    ax.set_xlabel(f"{b_label} reported {label} ({unit})", color=INK_SECONDARY)
    ax.set_ylabel(f"{a_label} reported {label} ({unit})", color=INK_SECONDARY)
    ax.set_title(f"Matched-decode {label}: {a_label} vs {b_label} (n={len(pairs)} pairs)",
                 color=INK_PRIMARY)
    ax.tick_params(colors=INK_MUTED)
    ax.legend(loc="upper left", fontsize=8, facecolor=SURFACE, edgecolor=INK_MUTED)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    scatter_name = f"{stem}_scatter.png"
    fig.savefig(os.path.join(out_dir, scatter_name), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    # -- Residual/Part-effect: per-pair (a - b) vs b's value, density-binned ------------
    # Answers directly: is the Appraiser gap a flat offset (density hugs the mean-diff
    # line regardless of signal strength) or does it vary with how strong the signal is
    # (visible slope/trend in where the density sits)? This is the closest thing to an
    # interaction check the RCBD-without-replication design can offer -- see the report's
    # own caveat.
    fig, ax = plt.subplots(figsize=(9.5, 5))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    hb = ax.hexbin(b_vals, diffs, gridsize=gridsize, cmap=seq_cmap, mincnt=1,
                    bins="log", linewidths=0.1)
    ax.axhline(mean_diff, linestyle="--", linewidth=1.2, color=INK_SECONDARY,
               label=f"mean diff = {mean_diff:+.3f} {unit}")
    cb = fig.colorbar(hb, ax=ax, shrink=0.8)
    cb.set_label("matched pairs per bin (log scale)", color=INK_SECONDARY, fontsize=9)
    cb.ax.tick_params(labelcolor=INK_MUTED)
    ax.set_xlabel(f"{b_label} reported {label} ({unit})", color=INK_SECONDARY)
    ax.set_ylabel(f"{a_label} - {b_label} ({unit})", color=INK_SECONDARY)
    ax.set_title(f"Per-Part residual -- does the Appraiser gap in {label} depend on "
                 f"{b_label}-reported {label}?", color=INK_PRIMARY)
    ax.tick_params(colors=INK_MUTED)
    ax.legend(loc="best", fontsize=8, facecolor=SURFACE, edgecolor=INK_MUTED)
    fig.tight_layout()
    residual_name = f"{stem}_residual.png"
    fig.savefig(os.path.join(out_dir, residual_name), dpi=130, facecolor=SURFACE)
    plt.close(fig)

    return scatter_name, residual_name


def render_markdown_html(md_path: str) -> None:
    """Renders md_path to HTML alongside it, via the shared renderer
    (qa/rr-study/render_report.py -- generic despite its name/location; single source of
    truth for this repo's Markdown->HTML styling). Same helper tools/gather_live_run_
    artefacts.py uses for contents.md -- kept here as a small local copy rather than a
    cross-directory import, since qa/endurance and tools/ are not set up as importable
    packages. Best-effort: a rendering failure is warned about, not fatal -- the .md file,
    the primary artefact, is already written by the time this runs.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    renderer = os.path.normpath(os.path.join(here, "..", "rr-study", "render_report.py"))
    if not os.path.isfile(renderer):
        print(f"[WARN] {renderer} not found -- skipping HTML render of {md_path}",
              file=sys.stderr)
        return
    if not os.path.isfile(md_path):
        print(f"[WARN] {md_path} not found -- skipping HTML render", file=sys.stderr)
        return
    try:
        subprocess.run([sys.executable, renderer, md_path], check=True,
                        capture_output=True, text=True)
        print(f"wrote {os.path.splitext(md_path)[0]}.html")
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"[WARN] HTML render of {md_path} failed: {detail}", file=sys.stderr)


def ratio_of_sums(numerators: list[float], denominators: list[float]) -> float:
    """The standing estimator (see module docstring) for any decode-count ratio in this
    programme: SUM(numerators) / SUM(denominators), NOT mean(n/d for n, d in zip(...)).

    The two are not interchangeable. Mean-of-ratios gives a 2-decode cycle the same weight
    as a 40-decode one; ratio-of-sums weights every decode equally, which is what "what
    fraction of decodes did X get relative to Y" actually means. Deliberately takes two
    parallel lists rather than a list of (n, d) pairs or pre-computed per-part ratios, so a
    caller cannot accidentally average per-part ratios before calling this and call the
    result correct.

    len(numerators) must equal len(denominators); both empty returns NaN rather than raising
    (mirrors pct_or_na's "no data" handling below)."""
    if len(numerators) != len(denominators):
        raise ValueError(
            f"ratio_of_sums: numerators ({len(numerators)}) and denominators "
            f"({len(denominators)}) must be the same length -- one entry per part/cycle/"
            f"stratum."
        )
    denom_sum = sum(denominators)
    if not numerators or denom_sum == 0:
        return float("nan")
    return sum(numerators) / denom_sum


def pct_or_na(numerator: int, denominator: int) -> str:
    """'12.3%' normally; 'N/A (0 decodes)' when the denominator side decoded nothing at
    all, rather than a literal 'nan%' in the rendered report (found live, 2026-07-30, in a
    deliberately-sparse smoke-test window -- vanishingly unlikely across a full multi-
    thousand-decode session, but an honest report shouldn't print 'nan%' even in an edge
    case)."""
    if denominator == 0:
        return "N/A (0 decodes)"
    return f"{100.0 * numerator / denominator:.1f}%"


def render_report(response_results: list[tuple[dict, dict, tuple[str | None, str | None]]],
                   meta: dict) -> str:
    """`response_results` is one (resp_def, stats, chart_files) triple per entry in
    RESPONSES, sharing the same matched Parts -- see the entry-point scripts' main().
    Renders one ANOVA table + chart pair + appraiser-means section per response, followed
    by a single shared caveat section (the structural note applies identically to all
    three).

    `meta` required keys: run_label, generated_utc, a_label, b_label, n_a, n_b, n_pairs.
    Optional: method_note (str, describes how b's rows were obtained -- re-decode vs
    already-existing live log), extra_lines (list[str], script-specific bullets inserted
    right after the headline counts), n_wavs (int, only meaningful when a re-decode
    happened) / wav_context_label (str, defaults to "WAV cycles fed to {b_label}").
    """
    a_label, b_label = meta["a_label"], meta["b_label"]
    L = []
    L.append(f"# Endurance-session ANOVA -- matched-decode metrics ({a_label} vs {b_label})")
    L.append("")
    L.append(f"**Run:** {meta['run_label']}  ")
    L.append(f"**Generated:** {meta['generated_utc']} (`date -u`, HK-017)  ")
    L.append(f"**Design:** two-way ANOVA without replication (randomized complete block "
              f"design) -- Part (matched decode instance) x Appraiser ({a_label}, "
              f"{b_label}), run separately for each paired numeric response below (SNR, "
              f"DT, frequency offset) over the identical matched Parts. See "
              f"anova_common.py's module docstring for why this design applies to "
              f"single-pass live data, and not the replicated design in "
              f"`qa/rr-study/harness/anova_compute.py`.")
    if meta.get("method_note"):
        L.append("")
        L.append(meta["method_note"])
    L.append("")

    if meta.get("n_wavs") is not None:
        wav_label = meta.get("wav_context_label", f"WAV cycles fed to {b_label}")
        L.append(f"- {wav_label}: **{meta['n_wavs']}**")
    L.append(f"- {a_label} decodes in window: **{meta['n_a']}**")
    L.append(f"- {b_label} decodes in window: **{meta['n_b']}**")
    L.append(f"- Matched pairs (Parts, shared across every response below): "
              f"**{meta['n_pairs']}**")
    for line in meta.get("extra_lines", []):
        L.append(f"- {line}")
    L.append("")

    # Decode coverage: how much of each side's output the other side also reported.
    # Distinct from the RESPONSES loop below -- this isn't a per-Part paired value, it's a
    # volume/overlap comparison over the whole window.
    n_a, n_b, n_pairs = meta["n_a"], meta["n_b"], meta["n_pairs"]
    a_only = n_a - n_pairs
    b_only = n_b - n_pairs
    L.append("## Decode coverage")
    L.append("")
    L.append(f"- {a_label} decoded **{n_a}** messages in this window; {b_label} decoded "
              f"**{n_b}**.")
    L.append(f"- **{n_pairs}** decodes matched between the two (same cycle + normalised "
              f"message text) -- **{pct_or_na(n_pairs, n_a)}** of {a_label}'s decodes, "
              f"**{pct_or_na(n_pairs, n_b)}** of {b_label}'s decodes.")
    L.append(f"- {a_label}-only ({b_label} did not report it): **{a_only}** "
              f"({pct_or_na(a_only, n_a)} of {a_label}'s total).")
    L.append(f"- {b_label}-only ({a_label} did not report it): **{b_only}** "
              f"({pct_or_na(b_only, n_b)} of {b_label}'s total).")
    L.append("")

    if meta["n_pairs"] < 2:
        L.append("**Too few matched pairs to compute an ANOVA table (need >= 2).** "
                  "Re-run against a larger window.")
        return "\n".join(L) + "\n"

    for resp, stats, chart_files in response_results:
        label, unit, fmt = resp["label"], resp["unit"], resp["fmt"]
        L.append(f"## {label} ({unit})")
        L.append("")
        scatter_name, residual_name = chart_files
        if scatter_name:
            L.append(f"![Matched-decode {label} scatter: {a_label} vs {b_label}]"
                      f"({scatter_name})")
            L.append("")
            if residual_name:
                L.append(f"![Per-Part residual vs {b_label} {label}]({residual_name})")
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
        L.append(f"Appraiser means ({label}, {unit}): {a_label} "
                  f"{fmt.format(stats['appraiser_means']['a'])} {unit}, {b_label} "
                  f"{fmt.format(stats['appraiser_means']['b'])} {unit}, grand mean "
                  f"{fmt.format(stats['grand_mean'])} {unit}.")
        L.append("")

    L.append("## Caveat (structural, not a defect)")
    L.append("")
    L.append("With one observation per Part x Appraiser cell -- a live signal happens "
              "once -- the interaction term and the residual/error term are "
              "mathematically confounded (standard property of an unreplicated "
              "factorial design), for every response above. Each table can say whether "
              "the two appraisers' *mean* value differs after removing part-to-part "
              "variation (the Appraiser row); none of them can separately test whether "
              "that difference itself varies signal-to-signal.")
    L.append("")
    L.append("Cross-run comparison and interpretation of these numbers is "
              "Architect/Captain territory, not this module's.")
    L.append("")
    return "\n".join(L) + "\n"


def run_responses(pairs: list[dict], out_dir: str, out_stem: str,
                   a_label: str = "OpenWSFZ", b_label: str = "jt9",
                   ) -> list[tuple[dict, dict, tuple[str | None, str | None]]]:
    """Runs the shared RESPONSES loop (stats + charts) once per metric, all sharing the
    same matched Parts. Common to both entry-point scripts' main()."""
    response_results = []
    for resp in RESPONSES:
        tuples = response_tuples(pairs, resp["key"]) if len(pairs) >= 2 else []
        stats = two_way_anova_no_replication(tuples) if len(tuples) >= 2 else {"b": len(tuples)}
        chart_files: tuple[str | None, str | None] = (None, None)
        if len(tuples) >= 2:
            print(f"rendering {resp['label']} charts...")
            chart_files = render_charts(
                tuples, stats, out_dir, f"{out_stem}_{resp['key']}",
                resp["label"], resp["unit"], a_label, b_label,
            )
        response_results.append((resp, stats, chart_files))
    return response_results
