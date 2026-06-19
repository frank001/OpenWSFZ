"""H6 directed AP decode efficacy probe.

Measures whether OpenWSFZ's H6 directed AP decode (SetApConstraints) improves
FT8 decode performance under close co-channel interference compared to blind
decode (WSJT-X as control appraiser, which does not have AP armed for the probe
message).

── Test design ─────────────────────────────────────────────────────────────────

Each trial spans FOUR FT8 cycles (60 seconds):

  Cycle 0 — ARM:    Inject "CQ {hiscall} {grid}" at {freq_hz}, clean, high SNR.
                    OpenWSFZ hears the CQ, auto-answers ("Q1ABC Q4XYZ -07").
                    QsoAnswererService → TxAnswer state.

  Cycle 1 — WAIT:   Noise only. OpenWSFZ transmits its answer → WaitReport.
                    H6 AP constraints armed: mycall={mycall}, hiscall={hiscall}.

  Cycle 2 — PROBE:  "{mycall} {hiscall} -07" at {freq_hz}  ┐ mixed via
                    interferer at ({freq_hz} + {offset_hz}) ┘ shared floor
                    Both at {probe_snr_db} dB.
                    OpenWSFZ (H6 armed) attempts decode of probe message.
                    WSJT-X (no AP for this message) decodes blind — control.

  Post-probe:       Wait ~3 s for decode logs to flush, then POST /abort to
                    reset state machine without waiting for watchdog (~1 min).

  Cycle 3 — SETTLE: Noise only. State returns to Idle.

── Callsign policy (NFR-021) ────────────────────────────────────────────────────

All callsigns committed to version control MUST use ITU-unallocated Q-prefix
(e.g. Q4XYZ, Q1ABC). Configure OpenWSFZ with mycall = Q4XYZ (or another Q-prefix)
for the duration of this test. The default --mycall and --hiscall values match the
existing study-messages.json MSG-02 / MSG-01 exactly, so no new message files
are required.

── Comparison baseline ──────────────────────────────────────────────────────────

From S7 R2 sweep (SHA 30be5ab, P16, Δ7 Hz, blind decode, K=10):
  Lower signal (1500 Hz): 4/10 = 40%   ← H6 target to beat
  Upper signal (1507 Hz): 10/10 = 100%

H6 efficacy is confirmed if OpenWSFZ probe decode rate >> 40%.
WSJT-X control rate at Δ7 Hz is expected to be ≈ 40% (same blind conditions).

── Usage ────────────────────────────────────────────────────────────────────────

  python harness/run_h6_probe.py \\
      --device "CABLE Input" \\
      --trials 20 \\
      --offset-hz 7 \\
      --owsfz-url http://localhost:8080 \\
      --owsfz-all-txt "C:/path/to/owsfz/ALL.TXT" \\
      --wsjt-all-txt  "C:/path/to/wsjtx/ALL.TXT"

WSJT-X note: disable WSJT-X auto-TX during this test (Settings → Enable Tx →
uncheck) to prevent WSJT-X from TXing replies that advance its own state machine
into WaitReport. WSJT-X should remain running as a passive RX observer (control).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Resolve qa/rr-study as a package root.
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import (
    SLOT_SECONDS,
    AllTxtRecord,
    compute_seed,
    make_run_dir,
    normalise_slot,
    parse_all_txt,
)
from synth.constants import DEFAULT_SAMPLE_RATE_HZ

# ── Constants ─────────────────────────────────────────────────────────────────
_PLAYBACK_PEAK: float = 0.9
_CYCLE_PREWARM_S: float = 0.5
_FADEOUT_DURATION_S: float = 0.2
_NOISE_CUTOFF_HZ: float = 4700.0
_ABORT_DELAY_S: float = 3.0       # seconds after probe cycle end before calling abort
_ABORT_TIMEOUT_S: float = 5.0     # HTTP timeout for the abort call

# Noise level for wait/settle cycles (dBFS, RMS). Low enough to not interfere
# with the FT8 decoder's noise floor estimator.
_WAIT_NOISE_DBFS: float = -30.0

# ── Scenario identity ─────────────────────────────────────────────────────────
_SCENARIO_ID: str = "H6"


# ---------------------------------------------------------------------------
# Audio rendering
# ---------------------------------------------------------------------------

def _noise_samples(seed: int) -> "np.ndarray":
    """Return 15 s of bandlimited AWGN for wait/settle cycles."""
    import numpy as np
    n = int(DEFAULT_SAMPLE_RATE_HZ * SLOT_SECONDS)
    rng = np.random.default_rng(seed)
    raw = rng.standard_normal(n) * (10.0 ** (_WAIT_NOISE_DBFS / 20.0))
    return raw.astype("float32")


def _render_arm(hiscall: str, grid: str, freq_hz: float,
                arm_snr_db: float, seed: int) -> "np.ndarray":
    """Render the arming CQ: 'CQ {hiscall} {grid}' at freq_hz."""
    from synth import channel, encoder
    text = f"CQ {hiscall} {grid}"
    clean = encoder.encode_message(text, base_freq_hz=freq_hz, dt_s=0.0,
                                   snr_db=None,
                                   sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)
    return channel.add_noise(clean, arm_snr_db, seed,
                             sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
                             noise_cutoff_hz=_NOISE_CUTOFF_HZ)


def _render_probe(mycall: str, hiscall: str,
                  freq_hz: float, offset_hz: float,
                  probe_snr_db: float, seed: int) -> "np.ndarray":
    """Render the probe slot: probe signal + co-channel interferer.

    Probe:      "{mycall} {hiscall} -07" at freq_hz, probe_snr_db
    Interferer: "CQ {hiscall} FN42"      at (freq_hz + offset_hz), probe_snr_db

    Mixed via mix_to_shared_floor so both signals share ONE noise floor, exactly
    as the S7 scenario does.  The interferer uses the CQ message from MSG-01 so
    the two-signal geometry mirrors S7 P16 with messages swapped: the probe
    (the target we want to decode with H6) sits at the lower frequency.
    """
    from synth import channel, encoder
    probe_text = f"{mycall} {hiscall} -07"
    intf_text   = f"CQ {hiscall} FN42"

    clean_probe = encoder.encode_message(
        probe_text, base_freq_hz=freq_hz, dt_s=0.0,
        snr_db=None, sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)
    clean_intf = encoder.encode_message(
        intf_text, base_freq_hz=float(freq_hz + offset_hz), dt_s=0.0,
        snr_db=None, sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ)

    return channel.mix_to_shared_floor(
        [clean_probe, clean_intf],
        [float(probe_snr_db), float(probe_snr_db)],
        seed,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        noise_cutoff_hz=_NOISE_CUTOFF_HZ,
    )


def _normalise(samples: "np.ndarray") -> "np.ndarray":
    """Normalise to ±_PLAYBACK_PEAK and apply half-cosine fade-out."""
    import numpy as np
    peak = float(np.max(np.abs(samples)))
    if peak > 0.0:
        samples = (samples * (_PLAYBACK_PEAK / peak)).astype("float32")
    n_fade = int(_FADEOUT_DURATION_S * DEFAULT_SAMPLE_RATE_HZ)
    if 0 < n_fade <= len(samples):
        t = np.linspace(0.0, 1.0, n_fade, endpoint=True)
        env = (0.5 * (1.0 + np.cos(np.pi * t))).astype("float32")
        samples[-n_fade:] *= env
    return samples.astype("float32")


# ---------------------------------------------------------------------------
# Cycle timing
# ---------------------------------------------------------------------------

def _next_boundary() -> float:
    now_s = int(time.time())
    rem = now_s % SLOT_SECONDS
    if rem == 0:
        return float(now_s + SLOT_SECONDS)
    return float(now_s + (SLOT_SECONDS - rem))


def _wait_for_boundary(ts: float) -> datetime:
    target = ts - _CYCLE_PREWARM_S
    remaining = target - time.time()
    if remaining > 0:
        time.sleep(remaining)
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0)


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

def _play(samples: "np.ndarray", device_idx: int, blocking: bool = True) -> None:
    import sounddevice as sd
    try:
        sd.play(samples, samplerate=DEFAULT_SAMPLE_RATE_HZ,
                device=device_idx, blocking=blocking)
        if blocking:
            sd.wait()
    except sd.PortAudioError as exc:
        print(f"\nERROR: PortAudio playback failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _sd_wait() -> None:
    import sounddevice as sd
    sd.wait()


# ---------------------------------------------------------------------------
# QSO abort
# ---------------------------------------------------------------------------

def _abort_qso(base_url: str) -> None:
    """POST /api/v1/tx/abort to force QsoAnswererService back to Idle."""
    url = base_url.rstrip("/") + "/api/v1/tx/abort"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=_ABORT_TIMEOUT_S) as resp:
            status = resp.status
        if status != 200:
            print(f"  [abort] WARNING: HTTP {status} from {url}", file=sys.stderr)
        else:
            print(f"  [abort] OK (HTTP 200)")
    except urllib.error.URLError as exc:
        print(f"  [abort] WARNING: could not reach {url}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Truth CSV
# ---------------------------------------------------------------------------

_TRUTH_COLUMNS = [
    "trial_index", "cycle_phase",
    "probe_message", "probe_freq_hz", "probe_snr_db",
    "interferer_freq_hz", "interferer_snr_db", "offset_hz",
    "arm_cycle_utc", "probe_cycle_utc", "seed",
]


def _write_truth(run_dir: Path, row: dict) -> None:
    path = run_dir / "h6_truth.csv"
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_TRUTH_COLUMNS)
        if write_header:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------------------
# Post-run analysis
# ---------------------------------------------------------------------------

def _analyse(run_dir: Path, args: argparse.Namespace) -> None:
    """Match ALL.TXT entries against truth.csv and report probe decode rates."""

    truth_path = run_dir / "h6_truth.csv"
    if not truth_path.exists():
        print("No truth.csv found — skipping analysis.", file=sys.stderr)
        return

    with open(truth_path, encoding="utf-8") as fh:
        truth_rows = list(csv.DictReader(fh))

    if not truth_rows:
        print("truth.csv is empty — skipping analysis.", file=sys.stderr)
        return

    probe_message = truth_rows[0]["probe_message"]

    def _load_all_txt(path_str: str | None) -> list[AllTxtRecord]:
        if not path_str:
            return []
        p = Path(path_str)
        if not p.exists():
            print(f"WARNING: ALL.TXT not found: {p}", file=sys.stderr)
            return []
        records, skipped = parse_all_txt(p)
        print(f"  Loaded {len(records)} records ({skipped} skipped) from {p}")
        return records

    print("\n── Post-run analysis ─────────────────────────────────────────────")
    owsfz_records = _load_all_txt(args.owsfz_all_txt)
    wsjt_records  = _load_all_txt(args.wsjt_all_txt)

    def _check_decoded(records: list[AllTxtRecord], slot_utc_str: str,
                       message: str, freq_hz: float) -> bool:
        """Return True if records contains a decode of message in the given slot."""
        slot_dt = datetime.strptime(slot_utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        slot_norm = normalise_slot(slot_dt)
        for r in records:
            if (r.message == message and
                    r.utc == slot_norm and
                    abs(r.freq_hz - freq_hz) <= 10.0):   # ±10 Hz frequency tolerance
                return True
        return False

    owsfz_hits = 0
    wsjt_hits  = 0
    n = len(truth_rows)

    print(f"\n  Probe message : {probe_message}")
    print(f"  Trials        : {n}")
    print(f"\n  {'Trial':>5}  {'OWSFZ':>6}  {'WSJT-X':>6}  probe_cycle")
    print(f"  {'─────':>5}  {'──────':>6}  {'──────':>6}  ─────────────────────")

    for row in truth_rows:
        tidx = int(row["trial_index"])
        slot = row["probe_cycle_utc"]
        fhz  = float(row["probe_freq_hz"])
        o = _check_decoded(owsfz_records, slot, probe_message, fhz)
        w = _check_decoded(wsjt_records,  slot, probe_message, fhz)
        owsfz_hits += int(o)
        wsjt_hits  += int(w)
        print(f"  {tidx:>5}  {'✓' if o else '✗':>6}  {'✓' if w else '✗':>6}  {slot}")

    print(f"\n  {'─────':>5}  {'──────':>6}  {'──────':>6}")
    owsfz_rate = 100.0 * owsfz_hits / n if n > 0 else 0.0
    wsjt_rate  = 100.0 * wsjt_hits  / n if n > 0 else 0.0
    print(f"  {'TOTAL':>5}  {owsfz_hits}/{n} ({owsfz_rate:.0f}%)  {wsjt_hits}/{n} ({wsjt_rate:.0f}%)")
    print()
    print(f"  Blind-decode baseline (S7 R2 P16, Δ7 Hz, lower signal): 4/10 = 40%")
    if owsfz_hits > 0 and owsfz_rate > 50.0:
        print(f"  H6 efficacy: CONFIRMED — OpenWSFZ {owsfz_rate:.0f}% >> 40% blind baseline")
    elif owsfz_rate > 40.0:
        print(f"  H6 efficacy: MARGINAL — OpenWSFZ {owsfz_rate:.0f}% ≈ blind baseline")
    else:
        print(f"  H6 efficacy: NOT CONFIRMED — OpenWSFZ {owsfz_rate:.0f}% ≤ blind baseline")

    # Write result summary CSV
    summary_path = run_dir / "h6_result.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["appraiser", "hits", "trials", "rate_pct"])
        w.writerow(["OpenWSFZ_H6", owsfz_hits, n, f"{owsfz_rate:.1f}"])
        w.writerow(["WSJT-X_blind", wsjt_hits, n, f"{wsjt_rate:.1f}"])
        w.writerow(["S7_P16_blind_baseline", 4, 10, "40.0"])
    print(f"\n  Summary written to: {summary_path.relative_to(_QA_ROOT)}")


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------

def _select_device(substring: str) -> int:
    import sounddevice as sd
    devices = sd.query_devices()
    matches = [(i, d) for i, d in enumerate(devices)
               if substring.lower() in d["name"].lower()
               and d["max_output_channels"] > 0]
    if not matches:
        print(f"ERROR: no output device matching '{substring}'. Available:")
        for i, d in enumerate(devices):
            if d["max_output_channels"] > 0:
                print(f"  [{i}] {d['name']}")
        sys.exit(1)
    return matches[0][0]


def _run(args: argparse.Namespace) -> None:
    import numpy as np

    probe_message = f"{args.mycall} {args.hiscall} -07"
    arm_message   = f"CQ {args.hiscall} {args.grid}"
    intf_freq_hz  = args.freq_hz + args.offset_hz

    # ── Setup ─────────────────────────────────────────────────────────────────
    results_root = _QA_ROOT / "results"
    run_dir = make_run_dir(results_root)

    print(f"\n{'═'*60}")
    print(f"  H6 Directed AP Decode Efficacy Probe")
    print(f"{'═'*60}")
    print(f"  Run dir     : {run_dir.relative_to(_QA_ROOT)}")
    print(f"  mycall      : {args.mycall}")
    print(f"  hiscall     : {args.hiscall}")
    print(f"  Arm message : {arm_message}")
    print(f"  Probe msg   : {probe_message}")
    print(f"  Probe freq  : {args.freq_hz:.0f} Hz  (interferer at "
          f"{intf_freq_hz:.0f} Hz, Δ{args.offset_hz:.0f} Hz)")
    print(f"  SNR (probe) : {args.probe_snr_db} dB  "
          f"(arm: {args.arm_snr_db} dB)")
    print(f"  Trials      : {args.trials}")
    print(f"  OpenWSFZ URL: {args.owsfz_url}")
    if args.dry_run:
        print(f"  *** DRY RUN — no audio playback ***")
    print(f"{'─'*60}\n")

    device_idx: int | None = None
    if not args.dry_run:
        device_idx = _select_device(args.device)

    for trial in range(args.trials):
        print(f"Trial {trial + 1}/{args.trials}")

        # Deterministic seeds (independent from S7 seeds via distinct prefix)
        arm_seed   = compute_seed(f"{_SCENARIO_ID}-ARM",  trial, 0)
        probe_seed = compute_seed(f"{_SCENARIO_ID}-PROBE", trial, 0)
        wait_seed  = compute_seed(f"{_SCENARIO_ID}-WAIT",  trial, 0)
        setl_seed  = compute_seed(f"{_SCENARIO_ID}-SETL",  trial, 0)

        # Pre-render all four slots
        arm_samples   = _normalise(_render_arm(
            args.hiscall, args.grid, args.freq_hz,
            args.arm_snr_db, arm_seed))
        wait_samples  = _normalise(_noise_samples(wait_seed))
        probe_samples = _normalise(_render_probe(
            args.mycall, args.hiscall, args.freq_hz, args.offset_hz,
            args.probe_snr_db, probe_seed))
        settle_samples = _normalise(_noise_samples(setl_seed))

        if args.dry_run:
            arm_cycle_utc   = datetime.now(timezone.utc).replace(microsecond=0)
            probe_cycle_utc = arm_cycle_utc + timedelta(seconds=30)
        else:
            import sounddevice as sd

            # Use sequential boundary arithmetic: b_{n+1} = b_n + SLOT_SECONDS.
            # Do NOT call _next_boundary() after each play — at the exact cycle
            # boundary it would return boundary + SLOT_SECONDS (the one after next),
            # causing a one-cycle slip on every transition.
            b0 = _next_boundary()

            # ── Cycle 0: ARM ──────────────────────────────────────────────────
            arm_cycle_utc = _wait_for_boundary(b0)
            print(f"  [ARM]   {arm_cycle_utc.strftime('%H:%M:%SZ')}  "
                  f"{arm_message} @ {args.freq_hz:.0f} Hz  "
                  f"SNR={args.arm_snr_db} dB  seed={arm_seed}", end=" … ", flush=True)
            _play(arm_samples, device_idx)
            print("done")

            # ── Cycle 1: WAIT (OpenWSFZ TX window) ───────────────────────────
            b1 = b0 + SLOT_SECONDS
            wait_utc = _wait_for_boundary(b1)   # prewarm only; play finishes at b0+15
            print(f"  [WAIT]  {wait_utc.strftime('%H:%M:%SZ')}  "
                  "noise only (OpenWSFZ TX slot)", end=" … ", flush=True)
            _play(wait_samples, device_idx)
            print("done")

            # ── Cycle 2: PROBE ────────────────────────────────────────────────
            b2 = b1 + SLOT_SECONDS
            probe_cycle_utc = _wait_for_boundary(b2)
            print(f"  [PROBE] {probe_cycle_utc.strftime('%H:%M:%SZ')}  "
                  f"{probe_message} @ {args.freq_hz:.0f} Hz  "
                  f"interferer @ {intf_freq_hz:.0f} Hz  "
                  f"Δ={args.offset_hz:.0f} Hz  "
                  f"seed={probe_seed}", end=" … ", flush=True)
            _play(probe_samples, device_idx)
            print("done")

            # ── Cycle 3: SETTLE ───────────────────────────────────────────────
            # Start settle noise immediately (non-blocking). After _ABORT_DELAY_S
            # seconds the decode has been written to ALL.TXT; call abort then wait
            # for the playback to finish naturally at the end of the cycle.
            b3 = b2 + SLOT_SECONDS
            settle_utc = _wait_for_boundary(b3)
            print(f"  [SETL]  {settle_utc.strftime('%H:%M:%SZ')}  "
                  "noise + abort", end=" … ", flush=True)
            sd.play(settle_samples, samplerate=DEFAULT_SAMPLE_RATE_HZ,
                    device=device_idx, blocking=False)
            time.sleep(_ABORT_DELAY_S)
            _abort_qso(args.owsfz_url)
            _sd_wait()
            print("done")

        arm_utc_str   = arm_cycle_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        probe_utc_str = probe_cycle_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        _write_truth(run_dir, {
            "trial_index":        trial,
            "cycle_phase":        "probe",
            "probe_message":      probe_message,
            "probe_freq_hz":      args.freq_hz,
            "probe_snr_db":       args.probe_snr_db,
            "interferer_freq_hz": intf_freq_hz,
            "interferer_snr_db":  args.probe_snr_db,
            "offset_hz":          args.offset_hz,
            "arm_cycle_utc":      arm_utc_str,
            "probe_cycle_utc":    probe_utc_str,
            "seed":               probe_seed,
        })

        print()

    print(f"{'─'*60}")
    truth_rel = (run_dir / "h6_truth.csv").relative_to(_QA_ROOT)
    print(f"  {args.trials} trial(s) complete.  Truth: {truth_rel}")
    print(f"  Elapsed: ~{args.trials * 4 * SLOT_SECONDS // 60} min "
          f"{(args.trials * 4 * SLOT_SECONDS) % 60} s\n")

    # ── Post-run analysis ─────────────────────────────────────────────────────
    if args.owsfz_all_txt or args.wsjt_all_txt:
        _analyse(run_dir, args)
    else:
        print("  No --owsfz-all-txt / --wsjt-all-txt provided.")
        print("  Run the analysis manually once ALL.TXT files are available:")
        print(f"  python harness/run_h6_probe.py --analyse-only {run_dir}")


# ---------------------------------------------------------------------------
# Analyse-only mode (re-run analysis on a completed result directory)
# ---------------------------------------------------------------------------

def _analyse_only(run_dir_str: str, args: argparse.Namespace) -> None:
    run_dir = Path(run_dir_str)
    if not run_dir.exists():
        sys.exit(f"ERROR: result directory not found: {run_dir}")
    _analyse(run_dir, args)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="H6 directed AP decode efficacy probe — "
                    "measures AP decode improvement under Δ7 Hz co-channel interference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Audio / device
    parser.add_argument("--device", default="CABLE Input",
                        help="Output device name substring (default: 'CABLE Input')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip audio playback and HTTP calls; write truth.csv only")

    # Trial parameters
    parser.add_argument("--trials", type=int, default=20,
                        help="Number of probe trials (default: 20, ~20 min)")
    parser.add_argument("--offset-hz", type=float, default=7.0,
                        help="Co-channel frequency offset in Hz (default: 7 — the gap zone)")
    parser.add_argument("--freq-hz", type=float, default=1500.0,
                        help="Probe signal centre frequency in Hz (default: 1500)")
    parser.add_argument("--probe-snr-db", type=float, default=0.0,
                        help="SNR for probe and interferer (dB, default: 0)")
    parser.add_argument("--arm-snr-db", type=float, default=6.0,
                        help="SNR for arming CQ (dB, default: +6 — ensure reliable decode)")

    # QSO callsigns (NFR-021: must be Q-prefix in version control)
    parser.add_argument("--mycall", default="Q4XYZ",
                        help="OpenWSFZ mycall for this test — MUST match app config. "
                             "Must be Q-prefix per NFR-021. (default: Q4XYZ)")
    parser.add_argument("--hiscall", default="Q1ABC",
                        help="Partner callsign (hiscall). (default: Q1ABC)")
    parser.add_argument("--grid", default="FN42",
                        help="Grid for the arming CQ. (default: FN42)")

    # Application endpoints and log paths
    parser.add_argument("--owsfz-url", default="http://localhost:8080",
                        help="OpenWSFZ base URL for abort API (default: http://localhost:8080)")
    parser.add_argument("--owsfz-all-txt", default=None,
                        metavar="PATH",
                        help="Path to OpenWSFZ ALL.TXT for post-run analysis")
    parser.add_argument("--wsjt-all-txt", default=None,
                        metavar="PATH",
                        help="Path to WSJT-X ALL.TXT for blind-decode control comparison")

    # Analyse-only mode
    parser.add_argument("--analyse-only", default=None,
                        metavar="RESULT_DIR",
                        help="Skip trials; re-run analysis on an existing result directory")

    args = parser.parse_args()

    if args.analyse_only:
        _analyse_only(args.analyse_only, args)
        return

    _run(args)


if __name__ == "__main__":
    main()
