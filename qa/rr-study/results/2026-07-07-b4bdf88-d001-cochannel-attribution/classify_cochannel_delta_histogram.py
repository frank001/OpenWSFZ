"""D-001 Partial-Bucket Δf Structure — fine-grained histogram + extended sweep.

Copy of `classify_cochannel.py` (Option B), extended per
`dev-tasks/2026-07-22-d001-partial-bucket-delta-histogram-spec.md`. Does NOT modify the
committed Option B script or its verdict — this only adds resolution inside data Option B
already computed:

  1. A 5 Hz-binned histogram of every classified miss's nearest-same-slot-neighbour Δf
     (`best_delta`), 0-50 Hz plus a final "isolated" bin, pooled per-band, per-session, and
     combined. Sourced from `min_deltas` (not `pooled_min_deltas`), per spec §3.1 point 1 —
     `pooled_min_deltas` silently drops the no-same-slot-neighbour-at-all misses (recorded as
     `(None, None)` and `continue`d past before reaching that accumulator), which would corrupt
     the Isolated bin.
  2. An extended window-sensitivity sweep, TIGHT_CUTOFFS widened from {10,12,15,20,25} to also
     include {30,35,40,45}, filling the gap to the 50 Hz Partial boundary (spec §3.2).
  3. The capture-effect sub-check (SNR delta to nearest neighbour, fraction >=10 dB) extended
     to the Partial class as well as Tight (spec §3.3) — this requires retaining each miss's own
     SNR through the loop, which the committed script does not do (it only needed the delta for
     the Tight branch).

Self-check (spec §3.1 point 2): the Isolated bin must sum to Option B's combined isolated count
(8,236) and the 0-50 Hz bins together to Tight+Partial (9,956 + 15,428 = 25,384). Asserted below;
a mismatch means this decomposition has diverged from the coarse classification it refines, and
the run fails loudly rather than publish a silently-inconsistent histogram.

Inputs, NFR-021 handling, and session list are identical to Option B's — no new data, no new
session. Output is aggregate counts/fractions only (no callsigns, no message text) and is safe to
commit.

Usage: python classify_cochannel_delta_histogram.py
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
ARTEFACTS = REPO_ROOT / "artefacts"

# (session label, artefact dir name, shim)
SESSIONS = [
    ("2026-07-07", "20260706_live_run_2308", "20260033"),
    ("2026-07-06", "20260706_live_run", "20260031"),
    ("2026-06-22", "20260622_live run", "20260029"),
]

LINE_RE = re.compile(
    r"^(?P<ts>\d{6}_\d{6})\s+(?P<dial>[\d.]+)\s+Rx\s+FT8\s+"
    r"(?P<snr>-?\d+)\s+(?P<dt>-?[\d.]+)\s+(?P<freq>\d+)\s+(?P<msg>.+?)\s*$"
)
HASH_TOKEN_RE = re.compile(r"<[^>]*>")

# Extended per spec §3.2: {10,12,15,20,25} -> add {30,35,40,45} to fill the gap to the 50 Hz
# Partial boundary. One-line change; the sweep loop, combine_pooled, and the console print all
# iterate this list, so the extension propagates with no other edits.
TIGHT_CUTOFFS = [10, 12, 15, 20, 25, 30, 35, 40, 45]
PRIMARY_TIGHT_CUTOFF = 15
PARTIAL_CUTOFF = 50

# Fine-grained histogram bins, spec §3.1: 5 Hz bins from 0-50 Hz, plus "isolated".
HIST_BIN_WIDTH = 5
HIST_BIN_LABELS = [f"{i}-{i + HIST_BIN_WIDTH}" for i in range(0, PARTIAL_CUTOFF, HIST_BIN_WIDTH)] + ["isolated"]

# Option B's own combined figures (report.md §3.1 / §3.2), reconciled against below (spec §3.1
# point 2) as a built-in self-check that this decomposition hasn't diverged from Option B.
OPTION_B_COMBINED_ISOLATED = 8236
OPTION_B_COMBINED_TIGHT_PLUS_PARTIAL = 9956 + 15428  # 25,384

# Primary low-SNR bands (spec §4.1.3 of the original Option B spec)
BAND_A = ("< -15 dB", lambda snr: snr < -15)
BAND_B = ("-15..-10 dB", lambda snr: -15 <= snr < -10)
BANDS = [BAND_A, BAND_B]

CAPTURE_DELTA_THRESHOLD_DB = 10  # "captured by a much stronger partner"


def parse(path: Path, source: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            rows.append({
                "ts": m.group("ts"),
                "snr": int(m.group("snr")),
                "dt": float(m.group("dt")),
                "freq": int(m.group("freq")),
                "msg": " ".join(m.group("msg").split()).upper(),
                "source": source,
            })
    return rows


def freq_bin(freq_hz: int, width: int = 50) -> int:
    return int(round(freq_hz / width)) * width


def sig_key(row: dict) -> tuple:
    return (row["ts"], freq_bin(row["freq"]), row["msg"])


def is_hashed(msg: str) -> bool:
    return bool(HASH_TOKEN_RE.search(msg))


def classify_delta(delta, cutoff, partial_cutoff: int = PARTIAL_CUTOFF) -> str:
    """Classify a miss by its nearest-same-slot-neighbour Δf (Hz) into
    ``"tight"`` / ``"partial"`` / ``"isolated"``. Verbatim from Option B's ``classify_cochannel.py``
    so this decomposition can never disagree with the coarse classification it refines."""
    if delta is None or delta > partial_cutoff:
        return "isolated"
    if delta <= cutoff:
        return "tight"
    return "partial"


def hist_label(delta) -> str:
    """Bin a Δf (Hz) into a 5 Hz bin label 0-50 Hz, or "isolated". Maps both
    ``delta is None`` (no same-slot neighbour at all) and ``delta > PARTIAL_CUTOFF`` (neighbour
    exists but beyond 50 Hz) into the single Isolated bin -- the two distinct ways Option B's
    ``classify()`` reaches "isolated" (spec §3.1 point 1)."""
    if delta is None or delta > PARTIAL_CUTOFF:
        return "isolated"
    idx = int(delta // HIST_BIN_WIDTH)
    # delta == PARTIAL_CUTOFF (50) exactly falls in the last numeric bin (45-50), not a
    # nonexistent "50-55" bin -- clamp rather than let floor division create an off-by-one bin.
    idx = min(idx, (PARTIAL_CUTOFF // HIST_BIN_WIDTH) - 1)
    lo = idx * HIST_BIN_WIDTH
    return f"{lo}-{lo + HIST_BIN_WIDTH}"


def classify_session(session_label: str, dirname: str,
                     session_dir: Path | None = None) -> dict | None:
    session_dir = session_dir if session_dir is not None else (ARTEFACTS / dirname)
    owsfz_file = session_dir / "OpenWSFZ ALL.TXT"
    wsjt_file = session_dir / "WSJT-X ALL.TXT"
    if not owsfz_file.exists() or not wsjt_file.exists():
        return None

    owsfz_rows = parse(owsfz_file, "owsfz")
    wsjt_rows = parse(wsjt_file, "wsjt")

    owsfz_keys = {sig_key(r): r for r in owsfz_rows}
    wsjt_keys = {sig_key(r): r for r in wsjt_rows}
    owsfz_set = set(owsfz_keys)
    wsjt_set = set(wsjt_keys)

    wsjt_only = wsjt_set - owsfz_set
    wsjt_only_nonhashed = {k for k in wsjt_only if not is_hashed(k[2])}

    slot_index: dict[str, list[dict]] = {}
    for r in owsfz_rows:
        slot_index.setdefault(r["ts"], []).append(r)
    for r in wsjt_rows:
        slot_index.setdefault(r["ts"], []).append(r)

    band_results = {}
    capture_deltas: list[float] = []           # Tight class (unchanged from Option B)
    partial_capture_deltas: list[float] = []   # Partial class (new, spec §3.3)

    for band_name, band_fn in BANDS:
        band_wsjt_keys = {
            k for k, r in wsjt_keys.items()
            if not is_hashed(k[2]) and band_fn(r["snr"])
        }
        band_total_wsjt = len(band_wsjt_keys)
        band_misses = band_wsjt_keys & wsjt_only_nonhashed

        min_deltas = []  # (best_delta or None, best_neighbour or None)
        for k in band_misses:
            miss_row = wsjt_keys[k]
            ts_m, freq_m = miss_row["ts"], miss_row["freq"]
            candidates = slot_index.get(ts_m, [])
            neighbours = [r for r in candidates if r is not miss_row]
            if not neighbours:
                min_deltas.append((None, None))
                continue
            deltas = [(abs(freq_m - r["freq"]), r) for r in neighbours]
            deltas.sort(key=lambda t: (t[0], -t[1]["snr"]))
            best_delta, best_neighbour = deltas[0]
            min_deltas.append((best_delta, best_neighbour))
            if best_delta is not None and best_delta <= PARTIAL_CUTOFF:
                delta_db = best_neighbour["snr"] - miss_row["snr"]
                if best_delta <= PRIMARY_TIGHT_CUTOFF:
                    capture_deltas.append(delta_db)
                else:
                    partial_capture_deltas.append(delta_db)

        # Fine-grained histogram, sourced from min_deltas (not pooled_min_deltas -- see module
        # docstring / spec §3.1 point 1) so truly-isolated (no same-slot neighbour at all)
        # misses are correctly counted in the Isolated bin.
        band_hist = Counter(hist_label(d) for d, _ in min_deltas)
        band_hist = {label: band_hist.get(label, 0) for label in HIST_BIN_LABELS}

        def classify(delta, cutoff):
            return classify_delta(delta, cutoff)

        sweep = {}
        for cutoff in TIGHT_CUTOFFS:
            tight = sum(1 for d, _ in min_deltas if classify(d, cutoff) == "tight")
            partial = sum(1 for d, _ in min_deltas if classify(d, cutoff) == "partial")
            isolated = sum(1 for d, _ in min_deltas if classify(d, cutoff) == "isolated")
            total = len(min_deltas)
            sweep[cutoff] = {
                "tight": tight, "partial": partial, "isolated": isolated,
                "total": total,
                "F": (tight / total) if total else None,
                "F_prime": ((tight + partial) / total) if total else None,
            }

        band_results[band_name] = {
            "wsjt_total_nonhashed": band_total_wsjt,
            "miss_count": len(band_misses),
            "sweep": sweep,
            "primary": sweep[PRIMARY_TIGHT_CUTOFF],
            "histogram": band_hist,
        }

    pooled_sweep = {}
    for cutoff in TIGHT_CUTOFFS:
        tight = partial = isolated = total = 0
        for band_name, _ in BANDS:
            s = band_results[band_name]["sweep"][cutoff]
            tight += s["tight"]; partial += s["partial"]; isolated += s["isolated"]
            total += s["total"]
        pooled_sweep[cutoff] = {
            "tight": tight, "partial": partial, "isolated": isolated, "total": total,
            "F": (tight / total) if total else None,
            "F_prime": ((tight + partial) / total) if total else None,
        }
    pooled_wsjt_total = sum(band_results[b]["wsjt_total_nonhashed"] for b, _ in BANDS)

    pooled_hist = Counter()
    for band_name, _ in BANDS:
        for label, n in band_results[band_name]["histogram"].items():
            pooled_hist[label] += n
    pooled_hist = {label: pooled_hist.get(label, 0) for label in HIST_BIN_LABELS}

    def capture_stats(deltas: list[float]) -> dict:
        n_ge10 = sum(1 for d in deltas if d >= CAPTURE_DELTA_THRESHOLD_DB)
        return {
            "n": len(deltas),
            "mean_delta_db": statistics.mean(deltas) if deltas else None,
            "median_delta_db": statistics.median(deltas) if deltas else None,
            "n_captured_ge_10db": n_ge10,
            "frac_captured_ge_10db": (n_ge10 / len(deltas)) if deltas else None,
        }

    return {
        "session": session_label,
        "dirname": dirname,
        "owsfz_lines": len(owsfz_rows),
        "wsjt_lines": len(wsjt_rows),
        "bands": band_results,
        "pooled": {
            "sweep": pooled_sweep,
            "primary": pooled_sweep[PRIMARY_TIGHT_CUTOFF],
            "wsjt_total_nonhashed_in_bands": pooled_wsjt_total,
            "recoverable_recall_pp_upper_bound":
                (100.0 * pooled_sweep[PRIMARY_TIGHT_CUTOFF]["tight"] / pooled_wsjt_total)
                if pooled_wsjt_total else None,
            "histogram": pooled_hist,
        },
        "capture_effect": capture_stats(capture_deltas),
        "capture_effect_partial": capture_stats(partial_capture_deltas),
    }


def combine_pooled(results: list[dict]) -> dict:
    combined_sweep = {}
    for cutoff in TIGHT_CUTOFFS:
        tight = partial = isolated = total = 0
        for r in results:
            s = r["pooled"]["sweep"][cutoff]
            tight += s["tight"]; partial += s["partial"]; isolated += s["isolated"]
            total += s["total"]
        combined_sweep[cutoff] = {
            "tight": tight, "partial": partial, "isolated": isolated, "total": total,
            "F": (tight / total) if total else None,
            "F_prime": ((tight + partial) / total) if total else None,
        }
    wsjt_total = sum(r["pooled"]["wsjt_total_nonhashed_in_bands"] for r in results)

    combined_hist = Counter()
    for r in results:
        for label, n in r["pooled"]["histogram"].items():
            combined_hist[label] += n
    combined_hist = {label: combined_hist.get(label, 0) for label in HIST_BIN_LABELS}

    def combine_capture(key: str) -> dict:
        all_n = sum(r[key]["n"] for r in results)
        weighted_ge10 = sum(r[key]["n_captured_ge_10db"] for r in results)
        return {
            "n": all_n,
            "n_captured_ge_10db": weighted_ge10,
            "frac_captured_ge_10db": (weighted_ge10 / all_n) if all_n else None,
        }

    return {
        "sweep": combined_sweep,
        "primary": combined_sweep[PRIMARY_TIGHT_CUTOFF],
        "wsjt_total_nonhashed_in_bands": wsjt_total,
        "recoverable_recall_pp_upper_bound":
            (100.0 * combined_sweep[PRIMARY_TIGHT_CUTOFF]["tight"] / wsjt_total) if wsjt_total else None,
        "histogram": combined_hist,
        "capture_effect": combine_capture("capture_effect"),
        "capture_effect_partial": combine_capture("capture_effect_partial"),
    }


def fmt_pct(x):
    return f"{100*x:.1f}%" if x is not None else "n/a"


def main() -> None:
    results = []
    for label, dirname, shim in SESSIONS:
        r = classify_session(label, dirname)
        if r is None:
            print(f"[SKIP] {label} ({dirname}): ALL.TXT pair not found")
            continue
        r["shim"] = shim
        results.append(r)
        print(f"\n=== Session {label} (shim {shim}) ===")
        pp = r["pooled"]["primary"]
        print(f"  POOLED (primary 15 Hz cutoff): total={pp['total']} tight={pp['tight']} "
              f"partial={pp['partial']} isolated={pp['isolated']} F={fmt_pct(pp['F'])} "
              f"F'={fmt_pct(pp['F_prime'])}")
        print("  Histogram (pooled bands): " +
              ", ".join(f"{lbl}={r['pooled']['histogram'][lbl]}" for lbl in HIST_BIN_LABELS))
        print("  Extended window sweep (F by tight cutoff): " +
              ", ".join(f"{c}Hz={fmt_pct(r['pooled']['sweep'][c]['F'])}" for c in TIGHT_CUTOFFS))
        ce = r["capture_effect"]
        cep = r["capture_effect_partial"]
        print(f"  Capture-effect Tight   (n={ce['n']}): n>=10dB={ce['n_captured_ge_10db']} "
              f"({fmt_pct(ce['frac_captured_ge_10db'])})")
        print(f"  Capture-effect Partial (n={cep['n']}): n>=10dB={cep['n_captured_ge_10db']} "
              f"({fmt_pct(cep['frac_captured_ge_10db'])})")

    if not results:
        print("\nNO SESSIONS AVAILABLE — cannot run. Escalate per spec §7 reference chain.")
        return

    combined = combine_pooled(results)

    print("\n=== COMBINED (all sessions, pooled bands) ===")
    cp = combined["primary"]
    print(f"  total={cp['total']} tight={cp['tight']} partial={cp['partial']} "
          f"isolated={cp['isolated']} F={fmt_pct(cp['F'])} F'={fmt_pct(cp['F_prime'])}")
    print("  Histogram (combined): " +
          ", ".join(f"{lbl}={combined['histogram'][lbl]}" for lbl in HIST_BIN_LABELS))
    print("  Extended window sweep: " +
          ", ".join(f"{c}Hz={fmt_pct(combined['sweep'][c]['F'])}" for c in TIGHT_CUTOFFS))
    print(f"  Recoverable recall upper bound: {combined['recoverable_recall_pp_upper_bound']:.2f} pp")
    ce = combined["capture_effect"]
    cep = combined["capture_effect_partial"]
    print(f"  Capture-effect Tight:   n={ce['n']} n>=10dB={ce['n_captured_ge_10db']} "
          f"({fmt_pct(ce['frac_captured_ge_10db'])})")
    print(f"  Capture-effect Partial: n={cep['n']} n>=10dB={cep['n_captured_ge_10db']} "
          f"({fmt_pct(cep['frac_captured_ge_10db'])})")

    # --- Self-check against Option B (spec §3.1 point 2): fail loudly on any divergence ---
    hist = combined["histogram"]
    isolated_n = hist["isolated"]
    numeric_bins_total = sum(hist[lbl] for lbl in HIST_BIN_LABELS if lbl != "isolated")
    assert isolated_n == OPTION_B_COMBINED_ISOLATED, (
        f"Self-check FAILED: histogram Isolated bin = {isolated_n}, "
        f"expected Option B's combined isolated count = {OPTION_B_COMBINED_ISOLATED}"
    )
    assert numeric_bins_total == OPTION_B_COMBINED_TIGHT_PLUS_PARTIAL, (
        f"Self-check FAILED: histogram 0-50 Hz bins sum = {numeric_bins_total}, "
        f"expected Option B's combined Tight+Partial = {OPTION_B_COMBINED_TIGHT_PLUS_PARTIAL}"
    )
    print(f"\n  Self-check OK: Isolated bin = {isolated_n} (matches Option B's {OPTION_B_COMBINED_ISOLATED}); "
          f"0-50 Hz bins sum = {numeric_bins_total} "
          f"(matches Option B's Tight+Partial {OPTION_B_COMBINED_TIGHT_PLUS_PARTIAL})")

    out = {
        "sessions": results,
        "combined": combined,
        "params": {
            "tight_cutoffs_sweep_hz": TIGHT_CUTOFFS,
            "primary_tight_cutoff_hz": PRIMARY_TIGHT_CUTOFF,
            "partial_cutoff_hz": PARTIAL_CUTOFF,
            "capture_delta_threshold_db": CAPTURE_DELTA_THRESHOLD_DB,
            "histogram_bin_width_hz": HIST_BIN_WIDTH,
            "histogram_bin_labels": HIST_BIN_LABELS,
            "bands": [b[0] for b in BANDS],
        },
        "self_check": {
            "isolated_matches_option_b": isolated_n == OPTION_B_COMBINED_ISOLATED,
            "tight_plus_partial_matches_option_b": numeric_bins_total == OPTION_B_COMBINED_TIGHT_PLUS_PARTIAL,
        },
    }
    out_path = Path(__file__).resolve().parent / "cochannel_delta_histogram_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nAggregate results written to {out_path}")


if __name__ == "__main__":
    main()
