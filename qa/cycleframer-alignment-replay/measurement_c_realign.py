#!/usr/bin/env python3
"""D-001 Measurement C (S6b of the 2026-07-30-2253 Architect ruling) -- the re-alignment
experiment. Settles offline/deterministically whether the capture-clock-drift defect's
~13h collapse (see DEFECT-capture-clock-drift-silent-decode-loss.md) is window misalignment
and nothing else, using 5773 matched WAV pairs already on disk in
artefacts/20260729_live_run_1831-8080.

Design (S6b.2, verbatim):
  1. For each sampled cycle, measure the lag by cross-correlation.
  2. Shift our WAV by the measured lag (sample-domain roll, zero-padding the vacated
     boundary -- no resampling, no interpolation).
  3. Re-decode the shifted WAV with our own decoder, and with jt9 as a control.
  4. Compare parity before and after realignment, WITHIN the collapsed window (drift > 2.5s)
     and WITHIN the healthy window as a null control.

SHIFT DIRECTION -- derived, not guessed, and checked against the self-tested sign convention
in measure_drift_8080_session.py:
  measure_capture_alignment.ncc_full finds L (raw samples) maximizing a[i]~b[i+L], where
  a=OpenWSFZ, b=WSJT-X. Absolute-time algebra (t0_a + i/fr = t0_b + (i+L)/fr) gives
  L = (t0_owsfz_start - t0_wsjtx_start) * fr -- positive when OpenWSFZ starts later, which
  the synthetic self-test in measure_drift_8080_session.py already confirmed is this
  session's actual sign.

  To reindex OpenWSFZ's buffer onto WSJT-X's (non-drifting) absolute timeline: we want
  corrected[j] to hold the same real-world content as wsjtx[j]. Since a[i] holds the same
  content as b[i+L], setting i+L=j gives i=j-L, i.e. corrected[j] = a[j-L].
    - For j < L: no OpenWSFZ sample exists that early (it hadn't started recording) ->
      zero-fill.
    - For j >= L: corrected[j] = a[j-L] (valid while j-L < 180000).
    - OpenWSFZ's own LAST L samples (indices >= 180000-L) never get placed anywhere, and
      are dropped -- they describe real time past WSJT-X's own window end.
  Net effect: corrected = zeros(180000); corrected[L:] = a[:180000-L] (for L>=0), mirrored
  for L<0. This is validated empirically below, not just algebraically: the HEALTHY-WINDOW
  arm is the designed check (S6b.3) -- if realigning barely-drifted audio moves its parity
  materially, the shift logic is wrong and the run is void.

NFR-021: WAV audio and per-cycle decode counts only. No message text or callsigns are
printed or written outside the git-ignored `_work/` and `artefacts/` trees; only aggregate
counts reach this script's own stdout/report.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import os
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "endurance"))
import measure_capture_alignment as mca  # noqa: E402
import endurance_anova_jt9 as ejt9       # noqa: E402
import anova_common as ac                # noqa: E402

ROOT = HERE.parents[1] / "artefacts" / "20260729_live_run_1831-8080"
OURS_WAV_DIR = ROOT / "owsfz" / "wav"
WSJTX_WAV_DIR = ROOT / "wsjt-x" / "wav"
WSJTX_ALL_TXT = ROOT / "wsjt-x" / "ALL.TXT"
OURS_ALL_TXT = ROOT / "owsfz" / "ALL.TXT"

SAMPLE_RATE = mca.SAMPLE_RATE
LAG_LIMIT = int(6 * SAMPLE_RATE)

WORK = HERE / "_work" / "measurement_c"
UNSHIFTED_DIR = WORK / "unshifted"
SHIFTED_DIR = WORK / "shifted"
OUT_DIR = WORK / "decoded"

N_PER_STRATUM = int(os.environ.get("MEAS_C_N_PER_STRATUM", "150"))
HEALTHY_LAG_BOUND = 0.5   # |predicted lag| < 0.5 s
COLLAPSED_LAG_BOUND = 2.5  # predicted lag <= -2.5 s

# Regression from measure_drift_8080_session.py's coarse pass (this session):
#   lag_seconds(elapsed_h) ~= INTERCEPT + SLOPE * elapsed_h
INTERCEPT = -0.2366
SLOPE = -0.1744  # s/h

DIAL_MHZ = "7.074"  # read off ALL.TXT (both apps agree -- same dial, same feed)
JT9_EXE = r"D:\WSJT\wsjtx\bin\jt9.exe"
HARNESS_EXE = HERE.parents[0] / "rr-study" / "d001-param-sweep-2026-07-22" / "bin" / "Release" / "net10.0" / "D001ParamSweep.exe"
GRID_POINT = "k10_c0.10_n60"


def cycle_ts_to_seconds(stem: str) -> int:
    date_part, time_part = stem.split("_")
    hh, mm, ss = int(time_part[0:2]), int(time_part[2:4]), int(time_part[4:6])
    day_offset = 0 if date_part == "260729" else 1
    return day_offset * 86400 + hh * 3600 + mm * 60 + ss


def select_cycles() -> tuple[list[str], list[str]]:
    common = sorted(
        p.stem for p in OURS_WAV_DIR.glob("*.wav")
        if (WSJTX_WAV_DIR / p.name).exists()
    )
    t0 = cycle_ts_to_seconds(common[0])
    healthy, collapsed = [], []
    for stem in common:
        elapsed_h = (cycle_ts_to_seconds(stem) - t0) / 3600.0
        predicted = INTERCEPT + SLOPE * elapsed_h
        if abs(predicted) < HEALTHY_LAG_BOUND:
            healthy.append(stem)
        elif predicted <= -COLLAPSED_LAG_BOUND:
            collapsed.append(stem)

    def fixed_stride_sample(pool: list[str], n: int) -> list[str]:
        if len(pool) <= n:
            return pool
        stride = len(pool) / n
        return [pool[int(i * stride)] for i in range(n)]

    healthy_sel = fixed_stride_sample(healthy, N_PER_STRATUM)
    collapsed_sel = fixed_stride_sample(collapsed, N_PER_STRATUM)
    print(f"Healthy-window candidates (|predicted lag| < {HEALTHY_LAG_BOUND}s): {len(healthy)} "
          f"-> sampled {len(healthy_sel)}")
    print(f"Collapsed-window candidates (predicted lag <= -{COLLAPSED_LAG_BOUND}s): {len(collapsed)} "
          f"-> sampled {len(collapsed_sel)}")
    return healthy_sel, collapsed_sel


def read_pcm16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        fr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    return np.frombuffer(raw, dtype="<i2").astype(np.float64), fr


def write_pcm16(path: Path, data: np.ndarray, fr: int) -> None:
    clipped = np.clip(np.round(data), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fr)
        w.writeframes(clipped.tobytes())


def build_pair(stem: str) -> tuple[float, float]:
    """Copies the original (unshifted) WAV and writes the shift-corrected WAV. Returns
    (lag_seconds, peak_corr)."""
    a, fr = read_pcm16(OURS_WAV_DIR / f"{stem}.wav")
    b, _ = read_pcm16(WSJTX_WAV_DIR / f"{stem}.wav")
    n = min(len(a), len(b))
    a_full = a  # keep full-length original for writing/copy
    a_c, b_c = a[:n], b[:n]

    lags, corr = mca.ncc_full(a_c, b_c, min(LAG_LIMIT, n - 1))
    idx = int(np.argmax(corr))
    L = int(lags[idx])
    peak = float(corr[idx])
    lag_seconds = -L / SAMPLE_RATE

    corrected = np.zeros(180000, dtype=np.float64)
    if L >= 0:
        keep = min(180000 - L, len(a_full))
        corrected[L:L + keep] = a_full[:keep]
    else:
        M = -L
        keep = min(180000 - M, len(a_full))
        corrected[:keep] = a_full[M:M + keep]

    shutil.copy(OURS_WAV_DIR / f"{stem}.wav", UNSHIFTED_DIR / f"{stem}.wav")
    write_pcm16(SHIFTED_DIR / f"{stem}.wav", corrected, SAMPLE_RATE)
    return lag_seconds, peak


def run_harness(wav_dir: Path, out_dir: Path) -> None:
    if not HARNESS_EXE.exists():
        raise SystemExit(f"harness not found: {HARNESS_EXE}")
    import subprocess
    cmd = [str(HARNESS_EXE), "--wav-dir", str(wav_dir), "--out-dir", str(out_dir),
           "--all-txt-name", "ALL.TXT", "--points", GRID_POINT, "--dial-mhz", DIAL_MHZ,
           "--progress-every", "50"]
    print(f"  running harness: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        print(f"[WARN] harness exited {result.returncode}\nSTDOUT:\n{result.stdout[-2000:]}\n"
              f"STDERR:\n{result.stderr[-2000:]}")
    else:
        print(f"  harness done ({len(result.stdout.splitlines())} stdout lines)")


def pooled_parity(our_rows: list[dict], ref_rows: list[dict]) -> tuple[int, int, float]:
    pairs = ac.match_pairs(our_rows, ref_rows)
    matched = len(pairs)
    ref_total = len(ref_rows)
    parity = matched / ref_total if ref_total else float("nan")
    return matched, ref_total, parity


def main() -> int:
    UNSHIFTED_DIR.mkdir(parents=True, exist_ok=True)
    SHIFTED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    healthy_sel, collapsed_sel = select_cycles()
    all_sel = healthy_sel + collapsed_sel
    strata = {s: "healthy" for s in healthy_sel}
    strata.update({s: "collapsed" for s in collapsed_sel})

    print(f"\nBuilding {len(all_sel)} shifted/unshifted WAV pairs...")
    manifest = []
    for i, stem in enumerate(all_sel):
        lag_s, peak = build_pair(stem)
        manifest.append((stem, strata[stem], lag_s, peak))
        if i % 50 == 0:
            print(f"  [{i+1}/{len(all_sel)}] {stem} ({strata[stem]}) lag={lag_s:+.3f}s peak={peak:.3f}")

    manifest_path = HERE / "measurement_c_manifest.csv"
    with open(manifest_path, "w", encoding="ascii") as fh:
        fh.write("stem,stratum,lag_seconds,peak_corr\n")
        for stem, stratum, lag_s, peak in manifest:
            fh.write(f"{stem},{stratum},{lag_s:.5f},{peak:.4f}\n")
    print(f"Wrote manifest: {manifest_path}")

    # ---- jt9: unshifted and shifted ----
    print("\n=== jt9 decode: unshifted ===")
    unshifted_paths = [str(UNSHIFTED_DIR / f"{s}.wav") for s in all_sel]
    jt9_unshifted = ejt9.run_jt9(JT9_EXE, unshifted_paths, depth=3, batch_size=150)
    print(f"jt9 unshifted decodes: {len(jt9_unshifted)}")

    print("\n=== jt9 decode: shifted ===")
    shifted_paths = [str(SHIFTED_DIR / f"{s}.wav") for s in all_sel]
    hhmmss_map = {os.path.splitext(os.path.basename(p))[0].split("_", 1)[1]:
                  os.path.splitext(os.path.basename(p))[0] for p in shifted_paths}
    jt9_shifted = ejt9.run_jt9(JT9_EXE, shifted_paths, depth=3, batch_size=150,
                                hhmmss_to_ts=hhmmss_map)
    print(f"jt9 shifted decodes: {len(jt9_shifted)}")

    # ---- our decoder: unshifted and shifted ----
    print("\n=== our decoder: unshifted ===")
    run_harness(UNSHIFTED_DIR, OUT_DIR / "unshifted")
    print("\n=== our decoder: shifted ===")
    run_harness(SHIFTED_DIR, OUT_DIR / "shifted")

    ours_unshifted = ac.parse_all_txt(str(OUT_DIR / "unshifted" / GRID_POINT / "ALL.TXT"))
    ours_shifted = ac.parse_all_txt(str(OUT_DIR / "shifted" / GRID_POINT / "ALL.TXT"))

    # ---- reference: WSJT-X's own ALL.TXT, restricted to the selected cycles ----
    wsjtx_all = ac.parse_all_txt(str(WSJTX_ALL_TXT))
    sel_set = set(all_sel)
    wsjtx_sel = [r for r in wsjtx_all if r["ts"] in sel_set]

    def subset(rows, stems):
        s = set(stems)
        return [r for r in rows if r["ts"] in s]

    report_lines = ["# Measurement C -- re-alignment experiment (D-001 ruling S6b)\n"]
    report_lines.append(f"Manifest: `measurement_c_manifest.csv`. "
                         f"{len(healthy_sel)} healthy-window + {len(collapsed_sel)} "
                         f"collapsed-window cycles.\n")
    report_lines.append("| stratum | condition | decoder | matched | ref decodes | parity |")
    report_lines.append("|---|---|---|---:|---:|---:|")

    results = {}
    for stratum_name, stems in (("healthy", healthy_sel), ("collapsed", collapsed_sel)):
        ref_sub = subset(wsjtx_sel, stems)
        for cond_name, ours_rows, jt9_rows in (
            ("unshifted", subset(ours_unshifted, stems), subset(jt9_unshifted, stems)),
            ("shifted", subset(ours_shifted, stems), subset(jt9_shifted, stems)),
        ):
            for dec_name, dec_rows in (("ours", ours_rows), ("jt9", jt9_rows)):
                matched, ref_total, parity = pooled_parity(dec_rows, ref_sub)
                results[(stratum_name, cond_name, dec_name)] = (matched, ref_total, parity)
                report_lines.append(f"| {stratum_name} | {cond_name} | {dec_name} | {matched} | "
                                     f"{ref_total} | {parity*100:.1f}% |")

    report_path = HERE / "measurement_c_realign_report.md"
    with open(report_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(report_lines) + "\n")
    print(f"\nWrote: {report_path}")

    for k, v in results.items():
        print(k, v)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
