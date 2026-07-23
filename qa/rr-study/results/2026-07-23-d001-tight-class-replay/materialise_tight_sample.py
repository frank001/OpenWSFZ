"""D-001 Option D, Step 1 — Tight-class sample materialisation (spec §3.1).

Executes step 1 of `dev-tasks/2026-07-23-d001-option-d-tight-class-replay-spec.md`.

Copy of the sibling isolated-miss pass's `materialise_isolated_sample.py`
(`qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/materialise_isolated_sample.py`),
changed only in which classification bucket is retained: **tight** (nearest same-slot
neighbour within the primary 15 Hz cutoff) instead of **isolated** (no neighbour within
50 Hz). Same session (07-07 -- the only one with retained per-slot WAV audio), same two
low-SNR bands, same `classify_delta` definition (verbatim from Option B's
`classify_cochannel.py`, so this pass's Tight population can never disagree with Option B's
own classification), same stratified/seeded/over-drawn sampling shape -- so the resulting
Decoded-on-replay rate is directly comparable to the Isolated pass's, not merely similar in
spirit.

Uses a distinct scenario id (`D001-TIGHT`) for seeding, independent of `D001-ISO`.

NFR-021 / project convention: the full Tight-miss population list (ts/freq/snr only) is
written to `_work/` (git-ignored, local only); only the drawn candidate-sample list
(msg-stripped) is committed alongside this script.

Usage: python materialise_tight_sample.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
ARTEFACTS = REPO_ROOT / "artefacts"
SAVE_DIR = ARTEFACTS / "20260706_live_run_2308" / "save"

_QA_ROOT = REPO_ROOT / "qa" / "rr-study"
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))
from harness.common import compute_seed  # noqa: E402

SESSION_LABEL = "2026-07-07"
SESSION_DIRNAME = "20260706_live_run_2308"

LINE_RE = re.compile(
    r"^(?P<ts>\d{6}_\d{6})\s+(?P<dial>[\d.]+)\s+Rx\s+FT8\s+"
    r"(?P<snr>-?\d+)\s+(?P<dt>-?[\d.]+)\s+(?P<freq>\d+)\s+(?P<msg>.+?)\s*$"
)
HASH_TOKEN_RE = re.compile(r"<[^>]*>")

PRIMARY_TIGHT_CUTOFF = 15  # identical to Option B / the isolated-miss pass (spec §3.1) --
PARTIAL_CUTOFF = 50        # do NOT redefine; comparability depends on the shared definition.

BAND_A = ("< -15 dB", lambda snr: snr < -15)
BAND_B = ("-15..-10 dB", lambda snr: -15 <= snr < -10)
BANDS = [BAND_A, BAND_B]

OVER_DRAW_PER_STRATUM = 60
TARGET_PER_STRATUM = 20
SCENARIO_ID = "D001-TIGHT"


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
    """Verbatim from Option B's classify_cochannel.py -- kept identical so this pass's
    "tight" population can never disagree with Option B's own classification."""
    if delta is None or delta > partial_cutoff:
        return "isolated"
    if delta <= cutoff:
        return "tight"
    return "partial"


def build_tight_population() -> list[dict]:
    session_dir = ARTEFACTS / SESSION_DIRNAME
    owsfz_file = session_dir / "OpenWSFZ ALL.TXT"
    wsjt_file = session_dir / "WSJT-X ALL.TXT"
    if not owsfz_file.exists() or not wsjt_file.exists():
        sys.exit(f"ERROR: ALL.TXT pair not found in {session_dir}")

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

    population: list[dict] = []
    for band_name, band_fn in BANDS:
        band_wsjt_keys = {
            k for k, r in wsjt_keys.items()
            if not is_hashed(k[2]) and band_fn(r["snr"])
        }
        band_misses = band_wsjt_keys & wsjt_only_nonhashed

        for k in band_misses:
            miss_row = wsjt_keys[k]
            ts_m, freq_m = miss_row["ts"], miss_row["freq"]
            candidates = slot_index.get(ts_m, [])
            neighbours = [r for r in candidates if r is not miss_row]
            if not neighbours:
                best_delta = None
            else:
                deltas = [(abs(freq_m - r["freq"]), r) for r in neighbours]
                deltas.sort(key=lambda t: (t[0], -t[1]["snr"]))
                best_delta = deltas[0][0]

            if classify_delta(best_delta, PRIMARY_TIGHT_CUTOFF) != "tight":
                continue

            population.append({
                "ts": ts_m,
                "freq_hz": freq_m,
                "wsjt_snr_db": miss_row["snr"],
                "band": band_name,
                "neighbour_delta_hz": best_delta,
                "has_wav": (SAVE_DIR / f"{ts_m}.wav").exists(),
                # msg is retained here for the live-replay driver's own Gate R check.
                # LOCAL ONLY -- stripped before anything is committed (strip_msg below),
                # per NFR-021 / project convention.
                "msg": miss_row["msg"],
            })

    return population


def strip_msg(records: list[dict]) -> list[dict]:
    """Remove the local-only msg field before anything is committed (NFR-021)."""
    return [{k: v for k, v in r.items() if k != "msg"} for r in records]


def stratified_overdraw_sample(population: list[dict]) -> dict:
    by_band: dict[str, list[dict]] = {b: [] for b, _ in BANDS}
    for rec in population:
        by_band[rec["band"]].append(rec)

    samples: dict[str, list[dict]] = {}
    for i, (band_name, _) in enumerate(BANDS):
        recs = sorted(by_band[band_name], key=lambda r: (r["ts"], r["freq_hz"]))
        seed = compute_seed(SCENARIO_ID, i, 0)
        import numpy as np
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(recs))
        drawn = [recs[idx] for idx in order[:OVER_DRAW_PER_STRATUM]]
        samples[band_name] = drawn

    return samples


def main() -> None:
    population = build_tight_population()
    n_total = len(population)
    n_with_wav = sum(1 for r in population if r["has_wav"])
    print(f"Tight-class population (07-07, both bands, primary 15 Hz cutoff): {n_total}")
    if n_total:
        print(f"  ...of which have an on-disk same-named WAV: {n_with_wav} "
              f"({100.0 * n_with_wav / n_total:.1f}%)")
    for band_name, _ in BANDS:
        n_band = sum(1 for r in population if r["band"] == band_name)
        print(f"  {band_name}: {n_band}")

    work_dir = Path(__file__).resolve().parent / "_work"
    work_dir.mkdir(exist_ok=True)
    pop_path = work_dir / "tight_population_07-07.json"
    with open(pop_path, "w", encoding="utf-8") as f:
        json.dump(population, f, indent=2)
    print(f"\nFull population (local only, not committed) written to {pop_path}")

    samples = stratified_overdraw_sample(population)

    samples_with_msg_path = work_dir / "tight_sample_candidates_with_msg.json"
    with open(samples_with_msg_path, "w", encoding="utf-8") as f:
        json.dump({b: recs for b, recs in samples.items()}, f, indent=2)
    print(f"Candidate sample WITH msg (local only, not committed) written to {samples_with_msg_path}")

    out_path = Path(__file__).resolve().parent / "tight_sample_candidates.json"
    out = {
        "scenario_id": SCENARIO_ID,
        "over_draw_per_stratum": OVER_DRAW_PER_STRATUM,
        "target_per_stratum": TARGET_PER_STRATUM,
        "population_totals": {
            "total": n_total,
            "with_wav": n_with_wav,
            "by_band": {b: sum(1 for r in population if r["band"] == b) for b, _ in BANDS},
        },
        "samples": {b: strip_msg(recs) for b, recs in samples.items()},
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Candidate sample (committed, msg-stripped) written to {out_path}")

    for band_name, _ in BANDS:
        n_wav_in_sample = sum(1 for r in samples[band_name] if r["has_wav"])
        print(f"\n{band_name}: drawn {len(samples[band_name])}, "
              f"{n_wav_in_sample} have an on-disk WAV (target: first {TARGET_PER_STRATUM} that "
              f"also survive Gate R reproduction check, per spec §3.1/§3.2)")


if __name__ == "__main__":
    main()
