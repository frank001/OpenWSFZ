"""D-001 Option B — co-channel attribution classifier.

Decomposes the WSJT-X-only ("missed by OpenWSFZ") decode set into three
same-UTC-slot neighbourhood classes:

    Tight co-channel  : nearest same-slot neighbour (union of both apps'
                         ALL.TXT) within the tight-cutoff (default 15 Hz)
    Partial overlap   : nearest same-slot neighbour within 50 Hz but beyond
                         the tight cutoff
    Isolated          : no same-slot neighbour within 50 Hz

F = Tight / total classified misses (restricted to the low-SNR bands
< -15 dB and -15..-10 dB, non-hashed). See:
  dev-tasks/2026-07-07-d001-b-cochannel-attribution-spec.md  (method)
  dev-tasks/2026-07-07-d001-b-cochannel-attribution-HANDOFF.md (work order)

Inputs are read directly from the local, git-ignored `artefacts/` tree
(NFR-021 — these logs carry real third-party callsigns and are never
committed). This script's *output* is aggregate counts/fractions only —
no callsigns, no message text — and is safe to commit.

Usage: python classify_cochannel.py
"""
from __future__ import annotations

import json
import re
import statistics
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

TIGHT_CUTOFFS = [10, 12, 15, 20, 25]
PRIMARY_TIGHT_CUTOFF = 15
PARTIAL_CUTOFF = 50

# Primary low-SNR bands (spec §4.1.3)
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
    ``"tight"`` / ``"partial"`` / ``"isolated"``.

    Extracted verbatim from ``classify_session``'s inner ``classify`` closure so
    downstream tooling reuses the single agreement algorithm rather than
    reimplementing it (D-001 runtime-param sweep, work-order step 13). The closure
    below now delegates here, so the two can never drift.
    """
    if delta is None or delta > partial_cutoff:
        return "isolated"
    if delta <= cutoff:
        return "tight"
    return "partial"


def classify_session(session_label: str, dirname: str,
                     session_dir: Path | None = None) -> dict | None:
    # session_dir override (additive, default preserves every existing call site):
    # lets a caller with its own per-point directory layout reuse this scorer against
    # a directory other than ARTEFACTS/<dirname> (D-001 param sweep, work-order step 13).
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

    # Slot index: union of both apps' raw rows, grouped by ts, keeping row
    # object identity so we can exclude "self" when finding neighbours.
    slot_index: dict[str, list[dict]] = {}
    for r in owsfz_rows:
        slot_index.setdefault(r["ts"], []).append(r)
    for r in wsjt_rows:
        slot_index.setdefault(r["ts"], []).append(r)

    # Build miss rows restricted to the two primary low-SNR bands.
    band_results = {}
    capture_deltas: list[float] = []
    pooled_min_deltas: list[tuple[float | None, str]] = []  # (min_delta, class-at-primary)

    for band_name, band_fn in BANDS:
        band_wsjt_keys = {
            k for k, r in wsjt_keys.items()
            if not is_hashed(k[2]) and band_fn(r["snr"])
        }
        band_total_wsjt = len(band_wsjt_keys)
        band_misses = band_wsjt_keys & wsjt_only_nonhashed

        min_deltas = []  # None if isolated (no neighbour <= 50Hz)
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
            pooled_min_deltas.append((best_delta, band_name))
            if best_delta is not None and best_delta <= PARTIAL_CUTOFF:
                if best_delta <= PRIMARY_TIGHT_CUTOFF:
                    capture_deltas.append(best_neighbour["snr"] - miss_row["snr"])

        # Classification at primary cutoff + sweep (delegates to the module-level
        # classify_delta so the sweep tooling and this report share one algorithm).
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
        }

    # Pooled across both bands
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
        },
        "capture_effect": {
            "n": len(capture_deltas),
            "mean_delta_db": statistics.mean(capture_deltas) if capture_deltas else None,
            "median_delta_db": statistics.median(capture_deltas) if capture_deltas else None,
            "n_captured_ge_10db": sum(1 for d in capture_deltas if d >= CAPTURE_DELTA_THRESHOLD_DB),
            "frac_captured_ge_10db": (
                sum(1 for d in capture_deltas if d >= CAPTURE_DELTA_THRESHOLD_DB) / len(capture_deltas)
            ) if capture_deltas else None,
        },
    }


def combine_pooled(results: list[dict]) -> dict:
    """Combine the 'pooled' (both-band) figures across sessions."""
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
    all_capture_n = sum(r["capture_effect"]["n"] for r in results)
    weighted_ge10 = sum(r["capture_effect"]["n_captured_ge_10db"] for r in results)
    return {
        "sweep": combined_sweep,
        "primary": combined_sweep[PRIMARY_TIGHT_CUTOFF],
        "wsjt_total_nonhashed_in_bands": wsjt_total,
        "recoverable_recall_pp_upper_bound":
            (100.0 * combined_sweep[PRIMARY_TIGHT_CUTOFF]["tight"] / wsjt_total) if wsjt_total else None,
        "capture_effect": {
            "n": all_capture_n,
            "n_captured_ge_10db": weighted_ge10,
            "frac_captured_ge_10db": (weighted_ge10 / all_capture_n) if all_capture_n else None,
        },
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
        print(f"  OpenWSFZ lines: {r['owsfz_lines']}  WSJT-X lines: {r['wsjt_lines']}")
        for band_name, _ in BANDS:
            b = r["bands"][band_name]
            p = b["primary"]
            print(f"  Band {band_name}: wsjt_total={b['wsjt_total_nonhashed']} "
                  f"miss={b['miss_count']} tight={p['tight']} partial={p['partial']} "
                  f"isolated={p['isolated']} F={fmt_pct(p['F'])} F'={fmt_pct(p['F_prime'])}")
        pp = r["pooled"]["primary"]
        print(f"  POOLED: total={pp['total']} tight={pp['tight']} partial={pp['partial']} "
              f"isolated={pp['isolated']} F={fmt_pct(pp['F'])} F'={fmt_pct(pp['F_prime'])}")
        print(f"  Recoverable recall upper bound: "
              f"{r['pooled']['recoverable_recall_pp_upper_bound']:.2f} pp"
              if r['pooled']['recoverable_recall_pp_upper_bound'] is not None else "  n/a")
        print(f"  Window sweep (F by tight cutoff): " +
              ", ".join(f"{c}Hz={fmt_pct(r['pooled']['sweep'][c]['F'])}" for c in TIGHT_CUTOFFS))
        ce = r["capture_effect"]
        print(f"  Capture-effect (Tight class, n={ce['n']}): mean dSNR={ce['mean_delta_db']}, "
              f"median={ce['median_delta_db']}, "
              f"n>=10dB={ce['n_captured_ge_10db']} ({fmt_pct(ce['frac_captured_ge_10db'])})")

    if not results:
        print("\nNO SESSIONS AVAILABLE — B cannot run. Escalate per spec §7.")
        return

    combined = combine_pooled(results)
    print("\n=== COMBINED (all available sessions, pooled bands) ===")
    cp = combined["primary"]
    print(f"  total={cp['total']} tight={cp['tight']} partial={cp['partial']} "
          f"isolated={cp['isolated']} F={fmt_pct(cp['F'])} F'={fmt_pct(cp['F_prime'])}")
    print(f"  Window sweep: " +
          ", ".join(f"{c}Hz={fmt_pct(combined['sweep'][c]['F'])}" for c in TIGHT_CUTOFFS))
    print(f"  Recoverable recall upper bound: {combined['recoverable_recall_pp_upper_bound']:.2f} pp")
    ce = combined["capture_effect"]
    print(f"  Capture-effect: n={ce['n']} n>=10dB={ce['n_captured_ge_10db']} "
          f"({fmt_pct(ce['frac_captured_ge_10db'])})")

    out = {
        "sessions": results,
        "combined": combined,
        "params": {
            "tight_cutoffs_sweep_hz": TIGHT_CUTOFFS,
            "primary_tight_cutoff_hz": PRIMARY_TIGHT_CUTOFF,
            "partial_cutoff_hz": PARTIAL_CUTOFF,
            "capture_delta_threshold_db": CAPTURE_DELTA_THRESHOLD_DB,
            "bands": [b[0] for b in BANDS],
        },
    }
    out_path = Path(__file__).resolve().parent / "cochannel_classification_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nAggregate results written to {out_path}")


if __name__ == "__main__":
    main()
