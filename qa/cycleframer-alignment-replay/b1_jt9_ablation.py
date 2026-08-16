#!/usr/bin/env python3
"""D-001 B.1 -- jt9 ablation. Runs WSJT-X's own CLI decoder (jt9.exe) over the 68-cycle corpus
at varying depth, scores against the live WSJT-X GUI reference and our own offline decoder,
per `2026-07-26-2330-architect-capability-pricing-plan.md` Sec.3 and
`2026-07-26-b1-jt9-ablation-task-spec.md`.

Reuses `c4_matched_decode_verification.py`'s normalize_hash_tokens/matching shape verbatim; the
only new piece is a parser for jt9's own stdout decode-line format (confirmed by the Sec.3.1
smoke test), since jt9 does not produce this repo's ALL.TXT writer format.

NFR-021: message text (real third-party callsigns) never printed to stdout; only aggregate
counts. Raw jt9 output stays under git-ignored artefacts/.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(REPO, "artefacts", "20260725_live_run_1806")
WSJTX_WAV_DIR = os.path.join(BASE, "wsjt-x", "wav")
OURS_WAV_DIR = os.path.join(BASE, "owsfz", "wav68")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
OURS_OFFLINE_ALL_TXT = os.path.join(BASE, "c4_min_score", "k10", "k10_c0.10_n60", "ALL.TXT")
JT9_EXE = r"D:\WSJT\wsjtx\bin\jt9.exe"
SCRATCH_ROOT = os.path.join(REPO, "artefacts", "d001_b1_jt9_ablation")

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")


def normalize_hash_tokens(message: str) -> str:
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def parse_all_txt(path: str) -> list[dict]:
    """This repo's own ALL.TXT writer format: ts dial Rx MODE snr dt freq message..."""
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                continue
            rows.append({"ts": tok[0], "snr": tok[4], "dt": tok[5], "freq": tok[6],
                         "message": " ".join(tok[7:])})
    return rows


_TS6_RE = re.compile(r"^\d{6}$")
_NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def parse_jt9_stdout(text: str, date_prefix: str) -> list[dict]:
    """jt9 -8 stdout format, confirmed by the Sec.3.1 smoke test:
        HHMMSS  SNR  DT  FREQ  MARKER  MESSAGE...
    MARKER is '~' for a non-AP decode (no -c/-x supplied in any arm). Lines that don't match
    (e.g. '<DecodeFinished> ...') are skipped, not fatal.
    """
    rows = []
    unrecognised_markers: set[str] = set()
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
        marker = tok[4]
        if marker != "~":
            unrecognised_markers.add(marker)
        rows.append({"ts": f"{date_prefix}_{tok[0]}", "snr": tok[1], "dt": tok[2],
                     "freq": tok[3], "message": " ".join(tok[5:])})
    if unrecognised_markers:
        print(f"  [NOTE] non-'~' markers seen: {sorted(unrecognised_markers)}", file=sys.stderr)
    return rows


def to_by_cycle(rows: list[dict]) -> dict[str, set[str]]:
    by_cycle: dict[str, set[str]] = {}
    for r in rows:
        by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))
    return by_cycle


def run_arm(label: str, depth: int, wav_dir: str, wav_names: list[str]) -> dict[str, set[str]]:
    scratch = os.path.join(SCRATCH_ROOT, label)
    os.makedirs(scratch, exist_ok=True)
    wav_paths = [os.path.join(wav_dir, name + ".wav") for name in wav_names]
    for p in wav_paths:
        assert os.path.isfile(p), f"missing WAV: {p}"
    cmd = [JT9_EXE, "-8", "-d", str(depth), "-p", "15", "-a", scratch, "-t", scratch] + wav_paths
    t0 = time.time()
    result = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"  [WARN] {label}: jt9 exited {result.returncode}", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
    date_prefix = wav_names[0].split("_")[0]
    rows = parse_jt9_stdout(result.stdout, date_prefix)
    with open(os.path.join(scratch, "stdout_raw.txt"), "w", encoding="utf-8") as fh:
        fh.write(result.stdout)
    print(f"  {label}: {elapsed:.1f}s, {len(rows)} raw decode lines, "
          f"{len(set((r['ts'], normalize_hash_tokens(r['message'])) for r in rows))} unique")
    return to_by_cycle(rows)


def main() -> None:
    wav_names = sorted(os.path.splitext(f)[0]
                        for f in os.listdir(OURS_WAV_DIR) if f.endswith(".wav"))
    cycle_set = set(wav_names)
    assert len(wav_names) == 68, f"expected 68 matched cycles, got {len(wav_names)}"
    print(f"corpus: {len(wav_names)} matched cycles")

    # Anchors
    wsjtx_by_cycle = to_by_cycle(r for r in parse_all_txt(WSJTX_ALL_TXT) if r["ts"] in cycle_set)
    ours_by_cycle = to_by_cycle(r for r in parse_all_txt(OURS_OFFLINE_ALL_TXT)
                                 if r["ts"] in cycle_set)
    wsjtx_total = sum(len(v) for v in wsjtx_by_cycle.values())
    ours_total = sum(len(v) for v in ours_by_cycle.values())
    print(f"anchor: live WSJT-X GUI (restricted to 68 cycles) = {wsjtx_total}")
    print(f"anchor: our decoder offline on WSJT-X's WAVs (restricted to 68 cycles) = {ours_total}")

    missed_by_cycle: dict[str, set[str]] = {}
    missed_total = 0
    for ts, wset in wsjtx_by_cycle.items():
        m = wset - ours_by_cycle.get(ts, set())
        if m:
            missed_by_cycle[ts] = m
            missed_total += len(m)
    print(f"the miss population (WSJT-X-live minus our-offline, per cycle) = {missed_total}")
    print()

    arms = [
        ("A0_d3", 3),
        ("A1_d2", 2),
        ("A2_d1", 1),
    ]

    print("Running arms (WSJT-X's own WAVs, single process per arm, chronological order)...")
    results = {}
    for label, depth in arms:
        results[label] = run_arm(label, depth, WSJTX_WAV_DIR, wav_names)
    print()

    print("SCORING")
    hdr = f"{'arm':<8} {'total':>7} {'miss_cov':>9} {'miss_pct':>9} {'ovl_ours':>9} {'ovl_pct':>8}"
    print(hdr)
    print("-" * len(hdr))
    for label, _ in arms:
        by_cycle = results[label]
        total = sum(len(v) for v in by_cycle.values())
        miss_cov = sum(len(by_cycle.get(ts, set()) & m) for ts, m in missed_by_cycle.items())
        ovl_ours = sum(len(by_cycle.get(ts, set()) & ours_by_cycle.get(ts, set()))
                       for ts in cycle_set)
        print(f"{label:<8} {total:>7} {miss_cov:>9} {miss_cov / max(1, missed_total):>8.1%} "
              f"{ovl_ours:>9} {ovl_ours / max(1, ours_total):>7.1%}")

    print()
    print("READING (plan Sec.3.4):")
    a0_total = sum(len(v) for v in results["A0_d3"].values())
    print(f"  A0={a0_total} vs anchor(2028-equivalent)={wsjtx_total}: "
          f"ratio={a0_total / max(1, wsjtx_total):.3f}")
    a2_total = sum(len(v) for v in results["A2_d1"].values())
    print(f"  A2={a2_total} vs our-offline-anchor={ours_total}: "
          f"ratio={a2_total / max(1, ours_total):.3f}")
    a1_total = sum(len(v) for v in results["A1_d2"].values())
    print(f"  T(3)-T(2) = {a0_total - a1_total}, T(2)-T(1) = {a1_total - a2_total}")


if __name__ == "__main__":
    main()
