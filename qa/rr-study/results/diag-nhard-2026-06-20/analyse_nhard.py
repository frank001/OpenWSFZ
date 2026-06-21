"""
analyse_nhard.py — D-009 R6 nhard/sync diagnostic analysis.

Reads nhard_s5_raw.log (FP population from S5 AWGN) and
nhard_s7_raw.log (genuine population from S7 P0-P2 co-channel).

Produces:
  nhard_fp_s5.txt         — one "nhard sync" pair per FP hit
  nhard_genuine_s7.txt    — one "nhard sync" pair per genuine hit
  nhard_observations.md   — QA observation log with stats and threshold analysis

Usage:
  python analyse_nhard.py --s5-log nhard_s5_raw.log --s7-log nhard_s7_raw.log
"""
from __future__ import annotations
import argparse
import re
import statistics
from pathlib import Path

# Match both the post-CRC labels (OSD_CRC_OK_SITE1/2) and the old pre-CRC labels
# (OSD_NHARD_SITE1/2) for backward compatibility.
_LINE_RE = re.compile(
    r"OSD_(?:CRC_OK_|NHARD_)SITE\d+\s+(\d+)\s+corr\s+([-\d.]+)\s+norm\s+([-\d.]+)\s+sync\s+(\d+)"
)


def parse_diag_log(path: Path) -> list[tuple[int, float, float, int]]:
    """Return list of (nhard, corr, norm, sync) tuples from an nhard_diag.log file."""
    records = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _LINE_RE.search(line.strip())
            if m:
                records.append((int(m.group(1)), float(m.group(2)),
                                 float(m.group(3)), int(m.group(4))))
    return records


def stats(values: list[float]) -> dict:
    """Return descriptive stats dict for a list of values."""
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "median": None, "stdev": None}
    return {
        "n":      len(values),
        "min":    min(values),
        "max":    max(values),
        "mean":   statistics.mean(values),
        "median": statistics.median(values),
        "stdev":  statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def confusion(fp_vals: list[float], gen_vals: list[float], threshold: float,
              mode: str = "above") -> dict:
    """Compute 2x2 confusion for a threshold on one axis.

    mode='above': FPs are expected ABOVE threshold (reject if x > threshold).
    mode='below': FPs are expected BELOW threshold (reject if x < threshold).

    Returns: fp_rejected, fp_kept, gen_rejected, gen_kept
    """
    if mode == "above":
        fp_rej  = sum(1 for v in fp_vals  if v > threshold)
        fp_kept = sum(1 for v in fp_vals  if v <= threshold)
        gen_rej = sum(1 for v in gen_vals if v > threshold)
        gen_kpt = sum(1 for v in gen_vals if v <= threshold)
    else:
        fp_rej  = sum(1 for v in fp_vals  if v < threshold)
        fp_kept = sum(1 for v in fp_vals  if v >= threshold)
        gen_rej = sum(1 for v in gen_vals if v < threshold)
        gen_kpt = sum(1 for v in gen_vals if v >= threshold)
    return {
        "threshold": threshold,
        "mode":      mode,
        "fp_rejected": fp_rej,  "fp_kept": fp_kept,
        "gen_rejected": gen_rej, "gen_kept": gen_kpt,
        "fp_reject_rate":  fp_rej  / len(fp_vals)  if fp_vals  else 0,
        "gen_keep_rate":   gen_kpt / len(gen_vals) if gen_vals else 0,
    }


def best_threshold(fp_vals: list[float], gen_vals: list[float],
                   mode: str = "above") -> tuple[float, dict]:
    """Sweep candidate thresholds and return (T, confusion) with best trade-off.

    Objective: maximise FP rejection while keeping ≥97% of genuine decodes.
    """
    if not fp_vals or not gen_vals:
        return (float("nan"), {})

    all_vals = sorted(set(fp_vals + gen_vals))
    best_t = None
    best_c: dict = {}
    for t in all_vals:
        c = confusion(fp_vals, gen_vals, t, mode)
        if c["gen_keep_rate"] >= 0.97:
            if best_t is None or c["fp_reject_rate"] > best_c["fp_reject_rate"]:
                best_t = t
                best_c = c

    if best_t is None:
        # No threshold achieves 97% genuine keep — find best compromise
        best_score = -1.0
        for t in all_vals:
            c = confusion(fp_vals, gen_vals, t, mode)
            score = c["fp_reject_rate"] - 2.0 * (1.0 - c["gen_keep_rate"])
            if score > best_score:
                best_score = score
                best_t = t
                best_c = c

    return (best_t, best_c)


def format_stats_row(label: str, s: dict) -> str:
    if s["n"] == 0:
        return f"  {label}: n=0 (no data)"
    return (f"  {label}: n={s['n']}, min={s['min']:.1f}, max={s['max']:.1f}, "
            f"mean={s['mean']:.1f}, median={s['median']:.1f}, stdev={s['stdev']:.1f}")


def format_confusion(c: dict, label: str) -> str:
    if not c:
        return f"  {label}: (no data)"
    mode_str = "reject if >" if c["mode"] == "above" else "reject if <"
    return (f"  {label} T={c['threshold']:.0f} ({mode_str} T):\n"
            f"    FP rejected {c['fp_rejected']}/{c['fp_rejected']+c['fp_kept']} "
            f"= {c['fp_reject_rate']*100:.1f}%  |  "
            f"Genuine kept {c['gen_kept']}/{c['gen_kept']+c['gen_rejected']} "
            f"= {c['gen_keep_rate']*100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="D-009 R6 nhard/sync diagnostic analysis")
    parser.add_argument("--s5-log", default="nhard_s5_raw.log",
                        help="nhard_diag.log from S5 AWGN run (FP population)")
    parser.add_argument("--s7-log", default="nhard_s7_raw.log",
                        help="nhard_diag.log from S7 P0-2 run (genuine population)")
    parser.add_argument("--out-dir", default=".",
                        help="Output directory for data files and observations")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    s5_path = Path(args.s5_log)
    s7_path = Path(args.s7_log)

    print(f"Reading S5 log: {s5_path}")
    fp_records = parse_diag_log(s5_path) if s5_path.exists() else []
    print(f"  {len(fp_records)} FP records")

    print(f"Reading S7 log: {s7_path}")
    gen_records = parse_diag_log(s7_path) if s7_path.exists() else []
    print(f"  {len(gen_records)} genuine records")

    fp_nhard  = [r[0] for r in fp_records]
    fp_sync   = [r[3] for r in fp_records]
    gen_nhard = [r[0] for r in gen_records]
    gen_sync  = [r[3] for r in gen_records]

    # ── Write data files ─────────────────────────────────────────────────────
    fp_out = out_dir / "nhard_fp_s5.txt"
    with open(fp_out, "w", encoding="utf-8") as fh:
        fh.write("# nhard sync  (FP candidates, S5 AWGN, shim 20260028 NHARD_DIAG)\n")
        for r in fp_records:
            fh.write(f"{r[0]} {r[3]}\n")
    print(f"Wrote {fp_out} ({len(fp_records)} lines)")

    gen_out = out_dir / "nhard_genuine_s7.txt"
    with open(gen_out, "w", encoding="utf-8") as fh:
        fh.write("# nhard sync  (genuine OSD recoveries, S7 P0-2, shim 20260028 NHARD_DIAG)\n")
        for r in gen_records:
            fh.write(f"{r[0]} {r[3]}\n")
    print(f"Wrote {gen_out} ({len(gen_records)} lines)")

    # ── Statistics ────────────────────────────────────────────────────────────
    nhard_fp_s  = stats(fp_nhard)
    nhard_gen_s = stats(gen_nhard)
    sync_fp_s   = stats(fp_sync)
    sync_gen_s  = stats(gen_sync)

    # Distribution of nhard values (histogram)
    def nhard_hist(vals: list[int]) -> str:
        buckets = {}
        for v in vals:
            key = (v // 5) * 5  # bucket by 5
            buckets[key] = buckets.get(key, 0) + 1
        lines_out = []
        for k in sorted(buckets):
            bar = '#' * min(40, buckets[k])
            lines_out.append(f"    [{k:3d}-{k+4:3d}] {bar} ({buckets[k]})")
        return "\n".join(lines_out)

    def sync_hist(vals: list[int]) -> str:
        buckets = {}
        for v in vals:
            buckets[v] = buckets.get(v, 0) + 1
        lines_out = []
        for k in sorted(buckets):
            bar = '#' * min(40, buckets[k])
            lines_out.append(f"    [{k:3d}] {bar} ({buckets[k]})")
        return "\n".join(lines_out)

    # Best thresholds
    # nhard: FPs should be ABOVE threshold (higher nhard = more random = FP)
    # reject if nhard > T  → mode='above'
    nhard_best_t, nhard_best_c = best_threshold(fp_nhard, gen_nhard, mode="above")
    # sync: FPs should be BELOW threshold (lower sync = weaker sync = noise FP)
    # reject if sync < T  → mode='below'
    sync_best_t, sync_best_c = best_threshold(fp_sync, gen_sync, mode="below")

    # Separation verdict
    def separation_verdict(best_c: dict, axis: str) -> str:
        if not best_c:
            return f"{axis}: INSUFFICIENT DATA"
        fr = best_c["fp_reject_rate"]
        gk = best_c["gen_keep_rate"]
        if fr >= 0.97 and gk >= 0.97:
            return f"{axis}: SEPARATES CLEANLY (Branch A trigger) — {fr*100:.1f}% FP rejected, {gk*100:.1f}% genuine kept"
        elif gk >= 0.97:
            return f"{axis}: PARTIAL separation — only {fr*100:.1f}% FP rejected at 97% genuine keep"
        else:
            return f"{axis}: DOES NOT SEPARATE (best compromise: {fr*100:.1f}% FP rejected, {gk*100:.1f}% genuine kept)"

    nhard_verdict = separation_verdict(nhard_best_c, "nhard")
    sync_verdict  = separation_verdict(sync_best_c,  "sync")

    # Overall branch trigger (per decision fork doc)
    # Branch A: nhard gives FP<=3% + genuine>=97% at some T
    if (nhard_best_c and nhard_best_c["fp_reject_rate"] >= 0.97
            and nhard_best_c["gen_keep_rate"] >= 0.97):
        branch_triggered = "A"
        branch_desc = f"nhard separates cleanly — set OSD_NHARD_MAX = {nhard_best_t:.0f}"
    elif (sync_best_c and sync_best_c["fp_reject_rate"] >= 0.97
          and sync_best_c["gen_keep_rate"] >= 0.97):
        branch_triggered = "B1"
        branch_desc = f"sync separates (nhard does not) — add OSD_MIN_SYNC = {sync_best_t:.0f} entry gate"
    else:
        branch_triggered = "B2"
        branch_desc = "neither nhard nor sync separates — escalate to scope decision (§4)"

    # ── Write nhard_observations.md ───────────────────────────────────────────
    obs_path = out_dir / "nhard_observations.md"
    with open(obs_path, "w", encoding="utf-8") as fh:
        fh.write(f"""# D-009 R6 — nhard/sync Diagnostic Observations

**Date:** 2026-06-20
**Shim:** 20260028 (D-009 R5: OSD_NHARD_MAX=60, OSD_CORR_THRESHOLD=0.10, Rules A/B/C)
**Build:** NHARD_DIAG — probe fires after CRC-14 check, writes to C:\\Temp\\nhard_diag.log
**Populations:**
- **FP** (S5 AWGN, 40 trials): {nhard_fp_s['n']} OSD CRC-valid hits in pure noise
- **Genuine** (S7 P0-2 co-channel, 5 trials each): {nhard_gen_s['n']} OSD CRC-valid hits during real signal decoding

**Acceptance criteria met:** AC1 = {nhard_fp_s['n'] >= 30} (need ≥30 FP hits, got {nhard_fp_s['n']}); AC2 = {nhard_gen_s['n'] >= 20} (need ≥20 genuine hits, got {nhard_gen_s['n']})

---

## 1. nhard axis

### 1.1 Descriptive statistics

{format_stats_row('FP (S5 noise)', nhard_fp_s)}
{format_stats_row('Genuine (S7)', nhard_gen_s)}

### 1.2 nhard histogram — FP population (S5 AWGN)

```
{nhard_hist(fp_nhard) if fp_nhard else '  (no data)'}
```

### 1.3 nhard histogram — Genuine population (S7 P0-2)

```
{nhard_hist(gen_nhard) if gen_nhard else '  (no data)'}
```

### 1.4 Best threshold on nhard axis (reject if nhard > T)

{format_confusion(nhard_best_c, 'nhard')}

### 1.5 Verdict

**{nhard_verdict}**

---

## 2. sync axis

### 2.1 Descriptive statistics

{format_stats_row('FP (S5 noise)', sync_fp_s)}
{format_stats_row('Genuine (S7)', sync_gen_s)}

### 2.2 sync histogram — FP population

```
{sync_hist(fp_sync) if fp_sync else '  (no data)'}
```

### 2.3 sync histogram — Genuine population

```
{sync_hist(gen_sync) if gen_sync else '  (no data)'}
```

### 2.4 Best threshold on sync axis (reject if sync < T)

{format_confusion(sync_best_c, 'sync')}

### 2.5 Verdict

**{sync_verdict}**

---

## 3. Representative samples

### 3.1 FP samples (first 10 from S5)

| nhard | sync | corr   | norm   |
|-------|------|--------|--------|
""")
        for r in fp_records[:10]:
            fh.write(f"| {r[0]:5d} | {r[3]:4d} | {r[1]:6.1f} | {r[2]:6.1f} |\n")

        fh.write("""
### 3.2 Genuine samples (first 10 from S7)

| nhard | sync | corr   | norm   |
|-------|------|--------|--------|
""")
        for r in gen_records[:10]:
            fh.write(f"| {r[0]:5d} | {r[3]:4d} | {r[1]:6.1f} | {r[2]:6.1f} |\n")

        fh.write(f"""
---

## 4. Decision variable (per `2026-06-20-d009-r6-decision-fork.md` §2)

| Axis  | Best T | FP rejected at T | Genuine kept at T | Separates? |
|-------|--------|------------------|-------------------|------------|
| nhard | {nhard_best_t if nhard_best_c else 'n/a':>6} | {f"{nhard_best_c.get('fp_reject_rate',0)*100:.1f}%" if nhard_best_c else 'n/a':>16} | {f"{nhard_best_c.get('gen_keep_rate',0)*100:.1f}%" if nhard_best_c else 'n/a':>17} | {'YES' if nhard_best_c and nhard_best_c.get('fp_reject_rate',0)>=0.97 and nhard_best_c.get('gen_keep_rate',0)>=0.97 else 'NO':>10} |
| sync  | {sync_best_t if sync_best_c else 'n/a':>6} | {f"{sync_best_c.get('fp_reject_rate',0)*100:.1f}%" if sync_best_c else 'n/a':>16} | {f"{sync_best_c.get('gen_keep_rate',0)*100:.1f}%" if sync_best_c else 'n/a':>17} | {'YES' if sync_best_c and sync_best_c.get('fp_reject_rate',0)>=0.97 and sync_best_c.get('gen_keep_rate',0)>=0.97 else 'NO':>10} |

**R6 branch triggered: {branch_triggered}**

{branch_desc}

*(Architect selects the specific implementation per `2026-06-20-d009-r6-decision-fork.md` §3. Developer does not implement.)*

---

## 5. Methodology notes

- **FP population:** OSD hits in pure wideband AWGN (S5, 40 trials, 40 × 15 s = 600 s, no FT8 signal). All CRC-14 successes are by definition false positives. Probe emitted AFTER CRC-14 check so each line corresponds to an actual decode event visible in ALL.TXT.
- **Genuine population:** OSD hits during S7 P0-2 co-channel decoding (3 parts × 5 trials = 15 slots). Signal IS present; OSD fires when BP fails on the co-channel candidate. Most CRC-14 successes in S7 correspond to true signal decodes; rare spurious CRC coincidences from the co-channel noise are possible but statistically minor.
- **Probe placement:** Post-CRC, not pre-gate. Only OSD hits that passed BOTH the OSD_NHARD_MAX=60 gate AND the OSD_CORR_THRESHOLD=0.10 gate AND CRC-14 are captured. This is the target population for the R6 fix: candidates that slip through the current shim 20260028 filters.
- **Why OSD_NHARD_MAX=60 was not removed:** The diagnostic tests within the existing gate (nhard 0-60). If the data shows no gap in [0,60], we confirm the nhard avenue is exhausted (Branch B); if there IS a gap, we lower the gate to that T (Branch A). Either conclusion is correct.
- **NFR-021 compliance:** No real callsigns appear in this document. All sample messages from S7 use Q-prefix synthetic callsigns (MSG-01/02/03 from study-messages.json). S5 FPs are random CRC coincidences with no meaningful callsign content.
""")

    print(f"Wrote {obs_path}")
    print(f"\n=== BRANCH TRIGGERED: {branch_triggered} ===")
    print(f"{branch_desc}")


if __name__ == "__main__":
    main()
