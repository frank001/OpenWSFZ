"""D-001 Isolated-Miss Pipeline Diagnosis -- sample materialisation, GENERIC corpus version.

Adapted from
`qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/materialise_isolated_sample.py`
(committed `0726bd6`, unmodified logic) to accept an arbitrary corpus directory, per
`qa/cycleframer-alignment-replay/2026-08-04-1441-architect-to-qa-spec-isolated-replay-rerun-post-drift-fix.md`
Sec.5's expectation that the harness would need a corpus-path parameter, disclosed here rather
than pre-registering silently.

DISCLOSED CHANGES from the original script (both purely mechanical -- classification logic,
sampling logic, and seeding are byte-identical):

1. **Corpus path is a parameter**, not hardcoded to `20260706_live_run_2308`. Both arm corpora
   use the newer `<corpus>/owsfz/ALL.TXT` + `<corpus>/wsjt-x/ALL.TXT` layout (space-free,
   subdirectory-based) instead of the original's `<corpus>/OpenWSFZ ALL.TXT` /
   `<corpus>/WSJT-X ALL.TXT` (space-separated, flat). The line format inside each file is
   unchanged (Format B, same regex).
2. **WAV source for replay is `<corpus>/wsjt-x/wav/`, not a single unified `save/` folder.**
   The original session had one shared `save/` directory (a single audio capture referenced by
   both decoders' logs). Both arm corpora instead carry SEPARATE `owsfz/wav/` and `wsjt-x/wav/`
   directories. Since the isolated-miss population is drawn from messages **WSJT-X decoded and
   OpenWSFZ missed live**, the correct replay source is the audio WSJT-X actually heard --
   `wsjt-x/wav/<ts>.wav` -- so the live-replay driver is testing "can OpenWSFZ decode what
   WSJT-X received," matching the question the spec poses. Using `owsfz/wav/` instead would
   replay OpenWSFZ's own (mis-timed, on the pre-fix arm) capture of the same nominal cycle,
   which is a different and less direct question.
3. **Output paths are per-arm** (`--out-dir`), so arm A and arm B never overwrite each other's
   `_work/` state or committed sample file.

NFR-021 unchanged: only ts/freq/snr/band/has_wav is ever committed; msg stays local-only in
`_work/` (gitignored).

Usage:
    python materialise_isolated_sample_generic.py --corpus <path> --out-dir <path> --label <arm>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

_QA_ROOT = REPO_ROOT / "qa" / "rr-study"
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))
from harness.common import compute_seed  # noqa: E402

LINE_RE = re.compile(
    r"^(?P<ts>\d{6}_\d{6})\s+(?P<dial>[\d.]+)\s+Rx\s+FT8\s+"
    r"(?P<snr>-?\d+)\s+(?P<dt>-?[\d.]+)\s+(?P<freq>\d+)\s+(?P<msg>.+?)\s*$"
)
HASH_TOKEN_RE = re.compile(r"<[^>]*>")

PRIMARY_TIGHT_CUTOFF = 15
PARTIAL_CUTOFF = 50

BAND_A = ("< -15 dB", lambda snr: snr < -15)
BAND_B = ("-15..-10 dB", lambda snr: -15 <= snr < -10)
BANDS = [BAND_A, BAND_B]

OVER_DRAW_PER_STRATUM = 60
SCENARIO_ID = "D001-ISO"


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
    """Verbatim from the original script / Option B's classify_cochannel.py."""
    if delta is None or delta > partial_cutoff:
        return "isolated"
    if delta <= cutoff:
        return "tight"
    return "partial"


def build_isolated_population(corpus: Path, wav_dir: Path) -> tuple[list[dict], dict]:
    owsfz_file = corpus / "owsfz" / "ALL.TXT"
    wsjt_file = corpus / "wsjt-x" / "ALL.TXT"
    if not owsfz_file.exists() or not wsjt_file.exists():
        sys.exit(f"ERROR: ALL.TXT pair not found under {corpus} (owsfz/ALL.TXT, wsjt-x/ALL.TXT)")

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

    class_counts = {"isolated": 0, "tight": 0, "partial": 0}
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

            cls = classify_delta(best_delta, PRIMARY_TIGHT_CUTOFF)
            class_counts[cls] += 1
            if cls != "isolated":
                continue

            population.append({
                "ts": ts_m,
                "freq_hz": freq_m,
                "wsjt_snr_db": miss_row["snr"],
                "band": band_name,
                "has_wav": (wav_dir / f"{ts_m}.wav").exists(),
                "msg": miss_row["msg"],
            })

    return population, class_counts


def build_reference_success_pool(corpus: Path, wav_dir: Path) -> list[dict]:
    owsfz_file = corpus / "owsfz" / "ALL.TXT"
    owsfz_rows = parse(owsfz_file, "owsfz")

    pool: list[dict] = []
    for band_name, band_fn in BANDS:
        for r in owsfz_rows:
            if is_hashed(r["msg"]) or not band_fn(r["snr"]):
                continue
            ts_r = r["ts"]
            if not (wav_dir / f"{ts_r}.wav").exists():
                continue
            pool.append({
                "ts": ts_r,
                "freq_hz": r["freq"],
                "wsjt_snr_db": r["snr"],
                "band": band_name,
                "has_wav": True,
                "msg": r["msg"],
            })
    return pool


def strip_msg(records: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "msg"} for r in records]


def stratified_overdraw_sample(population: list[dict], scenario_id: str) -> dict:
    by_band: dict[str, list[dict]] = {b: [] for b, _ in BANDS}
    for rec in population:
        by_band[rec["band"]].append(rec)

    samples: dict[str, list[dict]] = {}
    for i, (band_name, _) in enumerate(BANDS):
        recs = sorted(by_band[band_name], key=lambda r: (r["ts"], r["freq_hz"]))
        seed = compute_seed(scenario_id, i, 0)
        import numpy as np
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(recs))
        drawn = [recs[idx] for idx in order[:OVER_DRAW_PER_STRATUM]]
        samples[band_name] = drawn

    return samples


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path,
                    help="per-arm output directory (committed sample json + _work/ subfolder)")
    ap.add_argument("--label", required=True, help="arm label, e.g. 'arm-A' or 'arm-B'")
    args = ap.parse_args()

    corpus = args.corpus.resolve()
    wav_dir = corpus / "wsjt-x" / "wav"
    scenario_id = f"{SCENARIO_ID}-{args.label}"

    population, class_counts = build_isolated_population(corpus, wav_dir)
    n_total = len(population)
    n_with_wav = sum(1 for r in population if r["has_wav"])
    print(f"[{args.label}] Isolated-class population (both bands, primary 15 Hz cutoff): {n_total}")
    print(f"[{args.label}]   ...of which have an on-disk WSJT-X-side WAV: {n_with_wav} "
          f"({100.0 * n_with_wav / n_total:.1f}%)" if n_total else "  n/a")
    for band_name, _ in BANDS:
        n_band = sum(1 for r in population if r["band"] == band_name)
        print(f"[{args.label}]   {band_name}: {n_band}")
    print(f"[{args.label}] Classification counts (WSJT-X-only, non-hashed, in-band candidates): "
          f"isolated={class_counts['isolated']} tight={class_counts['tight']} "
          f"partial={class_counts['partial']}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = args.out_dir / "_work"
    work_dir.mkdir(exist_ok=True)

    pop_path = work_dir / "isolated_population.json"
    with open(pop_path, "w", encoding="utf-8") as f:
        json.dump(population, f, indent=2)
    print(f"[{args.label}] Full population (local only) written to {pop_path}")

    samples = stratified_overdraw_sample(population, scenario_id)

    samples_with_msg_path = work_dir / "isolated_sample_candidates_with_msg.json"
    with open(samples_with_msg_path, "w", encoding="utf-8") as f:
        json.dump({b: recs for b, recs in samples.items()}, f, indent=2)
    print(f"[{args.label}] Candidate sample WITH msg (local only) written to {samples_with_msg_path}")

    ref_pool = build_reference_success_pool(corpus, wav_dir)
    ref_samples: dict[str, list[dict]] = {}
    for i, (band_name, _) in enumerate(BANDS):
        recs = sorted([r for r in ref_pool if r["band"] == band_name],
                      key=lambda r: (r["ts"], r["freq_hz"]))
        import numpy as np
        seed = compute_seed(scenario_id + "-REF", i, 0)
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(recs))
        ref_samples[band_name] = [recs[idx] for idx in order[:10]]
    ref_path = work_dir / "reference_success_sample_with_msg.json"
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(ref_samples, f, indent=2)
    print(f"[{args.label}] Reference success-pool sample (local only) written to {ref_path}")

    out_path = args.out_dir / "isolated_sample_candidates.json"
    out = {
        "arm": args.label,
        "corpus": str(corpus),
        "scenario_id": scenario_id,
        "over_draw_per_stratum": OVER_DRAW_PER_STRATUM,
        "target_per_stratum": 20,
        "classification_counts": class_counts,
        "population_totals": {
            "total": n_total,
            "with_wav": n_with_wav,
            "by_band": {b: sum(1 for r in population if r["band"] == b) for b, _ in BANDS},
        },
        "samples": {b: strip_msg(recs) for b, recs in samples.items()},
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[{args.label}] Candidate sample (committed, msg-stripped) written to {out_path}")

    for band_name, _ in BANDS:
        n_wav_in_sample = sum(1 for r in samples[band_name] if r["has_wav"])
        print(f"[{args.label}] {band_name}: drawn {len(samples[band_name])}, "
              f"{n_wav_in_sample} have an on-disk WAV")


if __name__ == "__main__":
    main()
