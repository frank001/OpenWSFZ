#!/usr/bin/env python
"""Select a stratified, deterministic sub-sample of WAVs from an endurance-run
corpus for an S6-style corpus-replay R&R re-run.

Why stratified: a flat random draw from a 17-hour session is dominated by the
long midday lull (1,503 of 4,075 files are near-silent 08-14 UTC), which would
under-represent the interesting band conditions (busy evening, overnight
background, the 05-07 UTC propagation-shift spike documented in
qa/endurance/2026-07-07-bb0a1c4/report.md section 3.5). Stratifying by the same
time windows that report already established keeps the sample small (n=42,
matching the original S6 bench-corpus size) while covering each condition.

Usage (from qa/rr-study/):
    python select_endurance_sample.py \
        --source ../../artefacts/20260706_live_run_2308/save \
        --dest   results/2026-07-11-owsfz-rerun-sample/corpus \
        --n 42

Deterministic: seed = sha256("owsfz-rerun-sample-2026-07-11,<stratum>") so the
selection is reproducible from this script + its arguments alone.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import re
import shutil
import sys
from pathlib import Path

_WAV_PATTERN = re.compile(r"^(\d{6})_(\d{2})(\d{2})(\d{2})\.wav$", re.IGNORECASE)

# (label, hours (UTC, inclusive), target count)
_STRATA = [
    ("evening",              {21, 22, 23},                         12),
    ("overnight_background", {0, 1, 2, 3, 4},                      12),
    ("dawn_spike",           {5, 6, 7},                             12),
    ("midday_lull",          {8, 9, 10, 11, 12, 13, 14},             6),
]

_SEED_PREFIX = "owsfz-rerun-sample-2026-07-11"


def _seed_for(stratum: str) -> int:
    key = f"{_SEED_PREFIX},{stratum}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest(), 16) % (2**31)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--n", type=int, default=42)
    args = ap.parse_args()

    if not args.source.exists():
        sys.exit(f"ERROR: source dir not found: {args.source}")

    by_hour: dict[int, list[Path]] = {}
    for p in sorted(args.source.iterdir()):
        if not p.is_file():
            continue
        m = _WAV_PATTERN.match(p.name)
        if not m:
            continue
        hour = int(m.group(2))
        by_hour.setdefault(hour, []).append(p)

    total_target = sum(t for _, _, t in _STRATA)
    if total_target != args.n:
        sys.exit(f"ERROR: strata targets sum to {total_target}, expected --n {args.n}")

    args.dest.mkdir(parents=True, exist_ok=True)
    manifest_lines = [
        "# Endurance-run R&R sub-sample selection manifest",
        "",
        f"Source: {args.source}",
        f"Dest:   {args.dest}",
        f"Seed prefix: {_SEED_PREFIX!r}",
        "",
        "| Stratum | Hours (UTC) | Pool size | Selected |",
        "|---|---|---|---|",
    ]

    chosen_total: list[Path] = []
    for label, hours, target in _STRATA:
        pool: list[Path] = []
        for h in sorted(hours):
            pool.extend(by_hour.get(h, []))
        pool.sort(key=lambda p: p.name)  # deterministic order before shuffling
        if len(pool) < target:
            sys.exit(f"ERROR: stratum '{label}' pool has only {len(pool)} files, need {target}")
        rng = random.Random(_seed_for(label))
        chosen = rng.sample(pool, target)
        chosen.sort(key=lambda p: p.name)
        chosen_total.extend(chosen)
        manifest_lines.append(
            f"| {label} | {sorted(hours)} | {len(pool)} | {target} |"
        )

    manifest_lines.append("")
    manifest_lines.append("## Selected files")
    manifest_lines.append("")
    for p in sorted(chosen_total, key=lambda p: p.name):
        dst = args.dest / p.name
        shutil.copy2(p, dst)
        manifest_lines.append(f"- {p.name}")

    manifest_path = args.dest.parent / "sample_manifest.md"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print(f"Copied {len(chosen_total)} WAVs into {args.dest}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
