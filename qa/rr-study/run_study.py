#!/usr/bin/env python3
"""Master R&R study runner.

Runs scenarios in sequence (live playback into VB-CABLE), then collects
the WSJT-X and OpenWSFZ ALL.TXT logs, runs the matcher for every scenario,
and runs the analyser.

Run from qa/rr-study/:
    python run_study.py                          # full run (prompts for S8)
    python run_study.py --skip-s8                # full run, S8 excluded
    python run_study.py --scenarios S1,S1b       # targeted run
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Resolve qa/rr-study as a package root so ``harness`` is importable, same
# convention as harness/run_scenario.py.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from harness.common import make_run_dir  # noqa: E402
from harness import liveness as _lv  # noqa: E402  (M2/M3, 2026-10-14)
from harness import scenario_retry as _sr  # noqa: E402  (scenario-level retry, Captain 2026-10-14)

# #194 audio-setup sampler hook. A sampler problem must NEVER fail a battery: import errors included.
sys.path.insert(0, str(_HERE.parent / "audio-setup"))
try:
    import run_hook  # noqa: E402
except Exception as _exc:  # pragma: no cover
    run_hook = None
    print(f"  [audio-setup] hook unavailable, battery continues without it: {_exc}", flush=True)

# ── Timing ─────────────────────────────────────────────────────────────────
# Pause after each scenario to let the final cycle's decodes propagate into
# ALL.TXT before the log-collection step reads it.
_POST_SCENARIO_SETTLE_S: int = 5

# ── Paths ──────────────────────────────────────────────────────────────────
_VENV_PYTHON = _HERE / ".venv" / "Scripts" / "python.exe"
_SCENARIOS = _HERE / "scenarios"
_RESULTS = _HERE / "results"

WSJT_ALL_TXT    = Path(r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT")
# 2026-08-05 (repeat of 2026-06-22-f11f438 on newest build): the Captain now runs WSJT-X
# under the multi-instance "WSJT-X - FT991A" profile (three-decoder antenna-split setup),
# not the bare default profile this constant used to point at. See
# qa/rr-study/results/2026-08-05-<sha>/ run notes.
OWSFZ_ALL_TXT   = Path(r"D:\Projects\claude\OpenWSFZ\ALL.TXT")

# Full registry — used for --scenarios filtering and validation.
# Insertion order defines the default run order (S8 is prepended when selected).
_SCENARIO_REGISTRY: dict[str, Path] = {
    "S1":  _SCENARIOS / "s1-snr-ladder.json",
    "S1b": _SCENARIOS / "s1b-snr-threshold.json",
    "S2":  _SCENARIOS / "s2-freq-sweep.json",
    "S3":  _SCENARIOS / "s3-dt-offset.json",
    # C4 (Route B, 2026-08-19): registered so a TARGETED run (--scenarios S3b) can reach
    # it. Deliberately NOT added to _CONTROLLED_SCENARIO_IDS below -- like S8, it is not
    # part of the default batch. It is an attribute (decode-rate) study, not a Gage R&R
    # (see its own "analysis": "attribute_decode_rate" and harness_note), it needs
    # --device "Voicemeeter AUX Input" explicitly (this module's --device default below is
    # still "CABLE Input", which is unreliable on this machine per HK-020/the standing
    # capture-endpoint note), and at its corrected sizing (100 trials/part, see
    # scenarios/s3b-dt-boundary.json's _sizing_note) a full run is ~4.2h unattended and
    # needs an HK-013 supervisor -- not something the default batch should trigger blind.
    "S3b": _SCENARIOS / "s3b-dt-boundary.json",
    "S4":  _SCENARIOS / "s4-density.json",
    "S5":  _SCENARIOS / "s5-noise.json",
    "S7":  _SCENARIOS / "s7-compounding.json",
    "S8":  _SCENARIOS / "s8-band-scene.json",
    # C-ASYM-A Part C (2026-08-23): High-N copy of S8 (trials 5 -> 25) so M_syn's 95%
    # half-width resolves the spec's 0.10 gate bar (HK-021(m)). Reached only via
    # --scenarios S8HN, like S3b -- deliberately NOT in _CONTROLLED_SCENARIO_IDS and does
    # NOT touch S8's own entry above or s8-band-scene.json itself.
    "S8HN": _SCENARIOS / "s8hn-band-scene-highn.json",
    # S3c (#194 part B step 2, spec 2026-10-02-1730): the lean start-time edge guard. NOT a
    # harness/run_scenario.py scenario and not in truth.csv: it is played by s3c/s3c_play.py after
    # the other scenarios (same daemon session) and scored by s3c/s3c_score.py after the logs are
    # collected. Additive: S1-S8's own rows, truth.csv and the analyser are untouched.
    "S3c": _SCENARIOS / "s3c-edge-guard.json",
    # S6 (off-air WAV replay, spec 2026-10-13-1625 + amendment 1): not a harness/run_scenario.py scenario and not in truth.csv. The frozen tier list
    # is the "scenario file"; s6/s6_play.py plays it after S3c (the last playback), s6/s6_split.py moves its log lines out of the run folder, and
    # s6/s6_analyse.py writes the report block. Additive: a failure here voids the S6 block only, never S1-S8.
    "S6": _HERE / "s6" / "s6-wavlist.json",
}
_S3C_ID = "S3c"
_S6_ID = "S6"
_S6_CORPUS_WINDOWS = Path(r"D:\Projects\claude\OpenWSFZ\artefacts\rr-s6-refset-corpus")

# Controlled scenarios run by default (S8 handled separately via prompt / --skip-s8)
_CONTROLLED_SCENARIO_IDS = ["S1", "S1b", "S2", "S3", "S4", "S5", "S7", _S3C_ID, _S6_ID]

# R&R-009 (2026-08-23) restricted S5's routine battery to parts 0,1, reasoning
# that parts 2 (steady carrier @1500Hz) and 3 (multi-carrier "birdies") had
# detected only 1 false positive between them across history versus 52+ from
# parts 0/1 (AWGN). SUPERSEDED 2026-09-06 (S5-GATE-SIZING spec, Amendment 1,
# PO ruling Option 3): that restriction silently halved the ratified AWGN
# gate's own N (120->60, STUDY-SPEC.md Section 16) and removed the routine
# battery's only coverage of the narrowband-hallucination failure mode on an
# HK-026 argument (a zero-event history cannot bound its own future
# usefulness). Parts 2/3 are restored to the default battery -- their trial
# count now comes from scenarios/s5-noise.json itself (parts 0/1 carry a
# per-part "trials": 60 override; parts 2/3 use the file's default of 30),
# and harness/analyse.py scores the two populations as separate, never-pooled
# verdict rows (Gate A / Check B). This dict is left in place, empty, as the
# mechanism for any FUTURE default-battery part restriction -- do not repopulate
# it for S5 without a new spec revisiting the population question the way this
# one did.
_DEFAULT_BATTERY_PART_OVERRIDES: dict[str, str] = {}


_WINDOW_MARGIN_S = 120   # keep lines stamped up to two minutes before the battery's first playback


def _trim_log_to_window(path: Path, start_utc: "datetime") -> tuple[int, int]:
    """Drop the lines of an ALL.TXT COPY stamped before this battery began (the file is cumulative: an earlier
    battery's decodes of the same seeded texts would otherwise ride along as unmatched / false-positive rows in
    every *_matched.csv of this run, Architect 2026-10-03). A line is dated by its first token (YYMMDD_HHMMSS,
    UTC); a line that cannot be dated is KEPT, never dropped. Counts only (HK-037). Returns (kept, dropped)."""
    from datetime import timedelta
    cutoff = start_utc - timedelta(seconds=_WINDOW_MARGIN_S)
    kept: list[str] = []
    dropped = 0
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for line in fh:
            tok = line.split(None, 1)[0] if line.strip() else ""
            try:
                stamp = datetime.strptime(tok, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            except ValueError:
                kept.append(line)
                continue
            if stamp < cutoff:
                dropped += 1
            else:
                kept.append(line)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(kept)
    return len(kept), dropped


def _load_arm_config(run_dir: Path) -> dict:
    """{commit, dll_sha256, subtraction_enabled ('true'/'false'/'unknown')} from <run_dir>/arm_config.json."""
    import json
    try:
        d = json.loads((run_dir / "arm_config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    flag = ((d.get("daemon") or {}).get("decoder_readback") or {}).get("subtractionEnabled")
    return {"commit": (d.get("build") or {}).get("commit"),
            "dll_sha256": (d.get("daemon") or {}).get("dll_sha256"),
            "subtraction_enabled": {True: "true", False: "false"}.get(flag, "unknown")}


_CHILD = None        # the scenario process currently running (M2: the liveness watchdog stops it on a WSJT-X stall)


def _py(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command via the venv Python, streaming output in real time."""
    global _CHILD
    cmd = [str(_VENV_PYTHON), *args]
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    # CREATE_NO_WINDOW: this process may itself be console-less (run_study_detached.py's --poll
    # child); without it Windows gives every child a fresh visible console (found live 2026-09-22).
    proc = subprocess.Popen(cmd, cwd=str(_HERE), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _CHILD = proc
    try:
        rc = proc.wait()
    except BaseException:
        proc.kill()
        raise
    finally:
        _CHILD = None
    if check and rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)
    return subprocess.CompletedProcess(cmd, rc)


def _flag_stall_and_exit(run_dir: Path, reading, scenario, where: str) -> None:
    """M2: STOP AND FLAG. No restart, no recovery, no analysis of a sweep in which an appraiser went silent (Architect, 2026-10-14)."""
    info = {"utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "scenario": scenario, "where": where, "reason": reading.reason,
            "newest_wav_age_s": reading.age_s, "wsjtx_pids": reading.pids,
            "note": "The battery STOPPED because WSJT-X stopped taking in audio (liveness gate). The sweep is INVALID and is replaced, never repaired; "
                    "see monitor.jsonl / stall-*/ in the supervisor folder for the snapshot."}
    (run_dir / "STALLED.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"\n  *** STALLED ({where}, scenario {scenario}): {reading.reason}. Battery stopped; sweep INVALID (STALLED.json). ***", flush=True)
    raise SystemExit(21)


def _s6_corpus(args) -> Path:
    if args.s6_corpus:
        return Path(args.s6_corpus)
    return Path.home() / "rr-s6-refset-corpus" if sys.platform != "win32" else _S6_CORPUS_WINDOWS


def _s6_scratch(args, run_dir: Path) -> Path:
    if args.s6_scratch:
        return Path(args.s6_scratch)
    if sys.platform == "win32":
        return Path(r"D:\Projects\claude\_qa-scratch") / f"s6-{run_dir.name}"
    return Path.home() / "qa-scratch" / f"s6-{run_dir.name}"


def _battery_label(scenario_ids: list) -> str:
    """The report may call the battery "S1-S8" only when S6 actually ran (spec 2.1); otherwise it says which scenarios ran."""
    full = {"S1", "S1b", "S2", "S3", "S4", "S5", "S6", "S7"}
    return "S1-S8" if full <= set(scenario_ids) else "scenarios run: " + ", ".join(scenario_ids)


def main() -> None:
    global WSJT_ALL_TXT, OWSFZ_ALL_TXT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="CABLE Input",
                        help="Audio output device name substring")
    parser.add_argument("--skip-s8", action="store_true",
                        help="Skip the S8 realistic band scene (no prompt). "
                             "Ignored when --scenarios is given.")
    parser.add_argument("--skip-warmup", action="store_true",
                        help="Skip the INTERACTIVE pre-flight warm-up prompt (the supervised runs do). A MECHANICAL warm-up check still runs "
                             "before scenario 1 (both ALL.TXT must gain a line from a synthetic cycle); see --no-warmup-check.")
    parser.add_argument("--no-warmup-check", action="store_true",
                        help="Also skip the mechanical warm-up check (DANGEROUS: a battery can then run with one appraiser silent, as the "
                             "Linux repeats of 2026-10-11 did). Recorded in the run folder.")
    parser.add_argument("--scenarios", default=None,
                        metavar="ID[,ID...]",
                        help="Comma-separated list of scenario IDs to run "
                             "(e.g. S1,S1b). Bypasses the S8 prompt. "
                             f"Valid IDs: {', '.join(_SCENARIO_REGISTRY)}")
    parser.add_argument("--parts", default=None,
                        metavar="IDX[,IDX...]",
                        help="Comma-separated list of part indices (0-based) to run "
                             "within each selected scenario. Useful for targeted runs "
                             "of a single scenario (e.g. --scenarios S7 --parts 0,1,2). "
                             "Applied to every scenario when multiple are selected — use "
                             "with care. Not applicable to S8 (silently ignored).")
    parser.add_argument("--s3c-flag-state", default="auto", choices=["auto", "true", "false", "unknown"],
                        help="decoder.subtractionEnabled of the daemon under test, recorded in the S3c result "
                             "and trend, never pooled. 'auto' (default) reads it from the run dir's "
                             "arm_config.json (the launcher's read-back from the RUNNING daemon).")
    parser.add_argument("--s3c-build-sha", default="auto",
                        help="the daemon build's commit SHA; 'auto' reads arm_config.json")
    parser.add_argument("--s3c-dll-sha256-prefix", default="auto",
                        help="libft8.dll SHA-256 prefix of the daemon under test (HK-022); 'auto' reads arm_config.json")
    parser.add_argument("--s6-tier", default="standard", choices=["quick", "standard", "extended"],
                        help="S6 size: 24 / 60 / 180 WAVs x 3 trials (prefixes of one frozen list). Default standard.")
    parser.add_argument("--skip-s6", action="store_true", help="leave S6 out of the default battery")
    parser.add_argument("--s6-corpus", default=None, metavar="DIR",
                        help="the frozen rr-s6-refset-corpus (default: ~/rr-s6-refset-corpus on Linux, artefacts\\rr-s6-refset-corpus on Windows). "
                             "The default battery includes S6 only if this exists; --scenarios S6 without it is an error.")
    parser.add_argument("--s6-scratch", default=None, metavar="DIR",
                        help="where the S6 log slices (real callsigns) go, OUTSIDE git (default ~/qa-scratch/s6-<run> or D:\\Projects\\claude\\_qa-scratch\\s6-<run>)")
    parser.add_argument("--s6-ows-lib", default=None, help="the native library the daemon loaded (S6-V5 pin; the detached launcher passes it)")
    parser.add_argument("--s6-wsjtx-exe", default=None, help="the WSJT-X executable (S6-V5 pin; default ~/wsjtx-2.7.0/bin/wsjtx on Linux when present)")
    parser.add_argument("--daemon-log", default=None, help="the daemon's stdout log (per-play deadlineAbandoned for S6; the detached launcher passes it)")
    parser.add_argument("--s6-series-label", default="First S6 row of the LINUX series",
                        help="label of the S6 block (the tier is added); never pool across series or tiers")
    parser.add_argument("--legacy-no-arm-config", action="store_true",
                        help="allow a run with no arm_config.json in the run dir (a hand-run battery). Without it "
                             "the run is REFUSED at the start, not after hours: the report header would name the "
                             "wrong build (HK-022, four times). The analyser is passed the same flag.")
    # Overridable ALL.TXT locations (run_study_detached.py forwards the ones it read from the
    # daemon's own config; the constants above stay the defaults so no old invocation changes).
    parser.add_argument("--wsjt-all-txt", default=str(WSJT_ALL_TXT), metavar="PATH",
                        help="Path to WSJT-X's ALL.TXT.")
    parser.add_argument("--owsfz-all-txt", default=str(OWSFZ_ALL_TXT), metavar="PATH",
                        help="Path to OpenWSFZ's ALL.TXT.")
    parser.add_argument("--liveness-save-dir", default=None, metavar="PATH",
                        help="WSJT-X's save/ folder (SaveAll true). Turns on M2 (stop and flag when no new WAV arrives for --liveness-stall-s, or no `wsjtx` process) "
                             "and M3 (coverage slots written to the run folder for the analyser). Off by default (Windows runs unchanged).")
    parser.add_argument("--coverage-owsfz-dir", default=None, metavar="PATH",
                        help="OpenWSFZ's cycle-audio archive folder (same yymmdd_HHMMSS.wav names): M3 coverage for the second appraiser.")
    parser.add_argument("--liveness-stall-s", type=float, default=_lv.STALL_S, help="Stall limit in seconds (default 45 = 3 cycles).")
    parser.add_argument("--liveness-poll-s", type=float, default=_lv.POLL_S, help="Watchdog polling interval in seconds (default 15).")
    parser.add_argument("--scenario-retries", type=int, default=0, metavar="N",
                        help="Retries PER SCENARIO when WSJT-X stalls inside it (M2 stop) or the scenario's coverage fails (M3 for S1-S8, S6-V7 for S6): restart WSJT-X (--wsjtx-restart-cmd) and "
                             "rerun THAT scenario with all its trials in the same run folder; the failed attempt is kept as INVALID and a replacement recorded (scenario_retries.json). "
                             "The next failure after N retries halts and flags (exit 22). Default 0 = stop and flag at the first stall (exit 21). Never a single trial or play.")
    parser.add_argument("--wsjtx-restart-cmd", default=None, metavar="CMD",
                        help="Shell command that stops WSJT-X (also a frozen one) and starts it again, returning 0 when a fresh WAV is being written. Required for --scenario-retries > 0.")
    parser.add_argument("--no-liveness-gate", action="store_true",
                        help="Do NOT stop on a WSJT-X stall (DANGEROUS; recorded in the run folder). The coverage slots are still written.")
    args = parser.parse_args()
    WSJT_ALL_TXT, OWSFZ_ALL_TXT = Path(args.wsjt_all_txt), Path(args.owsfz_all_txt)
    if args.scenario_retries > 0 and not args.wsjtx_restart_cmd:
        sys.exit("ERROR: --scenario-retries > 0 needs --wsjtx-restart-cmd (the command that restarts WSJT-X).")
    if args.scenario_retries > 0 and not args.liveness_save_dir:
        sys.exit("ERROR: --scenario-retries > 0 needs --liveness-save-dir (the gate that detects the stall).")

    # ── Build scenario list ────────────────────────────────────────────────
    scenario_part_overrides: dict[str, str] = {}
    if args.scenarios:
        requested = [s.strip() for s in args.scenarios.split(",")]
        unknown   = [s for s in requested if s not in _SCENARIO_REGISTRY]
        if unknown:
            sys.exit(
                f"ERROR: unknown scenario ID(s): {', '.join(unknown)}\n"
                f"       Valid IDs: {', '.join(_SCENARIO_REGISTRY)}"
            )
        scenario_ids   = requested
        scenario_files = [_SCENARIO_REGISTRY[s] for s in requested]
        print(f"  Targeted run: {', '.join(scenario_ids)}\n")
    else:
        scenario_ids   = list(_CONTROLLED_SCENARIO_IDS)
        if args.skip_s6 or not _s6_corpus(args).is_dir():
            if not args.skip_s6:
                print(f"  WARNING: S6 left out of the default battery: its corpus {_s6_corpus(args)} does not exist "
                      "(pass --s6-corpus, or --skip-s6 to silence this). The report names the scenarios that ran.\n", flush=True)
            scenario_ids.remove(_S6_ID)
        scenario_files = [_SCENARIO_REGISTRY[s] for s in scenario_ids]
        scenario_part_overrides = dict(_DEFAULT_BATTERY_PART_OVERRIDES)

        if not args.skip_s8:
            ans = input("Run S8 realistic band scene first? [Y/n]: ").strip().lower()
            if ans in ("", "y", "yes"):
                scenario_files.insert(0, _SCENARIO_REGISTRY["S8"])
                scenario_ids.insert(0, "S8")
                print("  S8 included.\n")
            else:
                print("  S8 skipped.\n")

    if _S6_ID in scenario_ids and not _s6_corpus(args).is_dir():
        sys.exit(f"ERROR: S6 requested but its corpus {_s6_corpus(args)} does not exist (--s6-corpus).")
    battery = _battery_label(scenario_ids)
    print(f"  Battery         : {battery}\n", flush=True)

    # Warn when --parts is combined with multiple scenarios — it is applied to
    # all of them, which is rarely the intent.
    if args.parts and len(scenario_ids) > 1:
        print(
            f"  WARNING: --parts '{args.parts}' will be applied to every selected "
            f"scenario ({', '.join(scenario_ids)}).  Part indices must be valid for "
            f"all of them, or you will get an error mid-run.  "
            f"Prefer --scenarios <single-id> --parts <indices> for targeted work.\n"
        )

    # Pin the run directory ONCE, before any scenario runs, and pass it
    # explicitly to every harness/run_scenario.py invocation below (Item 1,
    # 2026-08-27 Architect work order). run_scenario.py otherwise resolves
    # its own output directory fresh from the *live* git HEAD SHA on every
    # invocation -- a commit landing mid-battery (however unrelated to src/)
    # silently splits the run's truth data across two directories and
    # crashes the matcher on whichever scenario falls on the wrong side of
    # the split. This bit a real run on 2026-08-27; see that run's report.md
    # Section 1 and qa/rr-study/2026-08-27-2141-architect-to-qa-outstanding-
    # work-order.md Item 1.
    run_dir = make_run_dir(_RESULTS)

    # The daemon-under-test's provenance record (run_study_detached.py copies it into the run dir).
    arm = _load_arm_config(run_dir)
    if not arm.get("commit") and not args.legacy_no_arm_config:
        sys.exit(f"ERROR: {run_dir / 'arm_config.json'} is missing or has no build commit. Launch this battery "
                 "through run_study_detached.py (it records the daemon's build and decoder flags), or pass "
                 "--legacy-no-arm-config for a hand-run battery (the report then says the build is NOT VERIFIED).")
    if args.s3c_flag_state == "auto":
        args.s3c_flag_state = arm.get("subtraction_enabled", "unknown")
    if args.s3c_build_sha == "auto":
        args.s3c_build_sha = arm.get("commit") or "unknown"
    if args.s3c_dll_sha256_prefix == "auto":
        args.s3c_dll_sha256_prefix = (arm.get("dll_sha256") or "unknown")[:16]

    print("=" * 70)
    print("OpenWSFZ R&R Study -- live run")
    print("=" * 70)
    print(f"  WSJT-X ALL.TXT  : {WSJT_ALL_TXT}")
    print(f"  OpenWSFZ ALL.TXT: {OWSFZ_ALL_TXT}")
    print(f"  Device          : {args.device}")
    print(f"  Scenarios       : {', '.join(scenario_ids)}")
    print(f"  Run directory   : {run_dir.relative_to(_HERE)}  (pinned for the whole battery)")
    if args.parts:
        print(f"  Parts filter    : {args.parts}")
    elif scenario_part_overrides:
        for sid, parts in scenario_part_overrides.items():
            if sid in scenario_ids:
                print(f"  Parts filter    : {sid} restricted to parts {parts} "
                      f"(R&R-009 default-battery override; see run_study.py)")
    print()

    # ── Step -1: audio-setup sampler (#194) ───────────────────────────────
    # Started >= 12 s before the first played audio (Amendment 1: a cold sample must not overlap a cycle) and
    # stopped by an explicit teardown right after the last scenario; atexit covers a crash or sys.exit.
    _as_handle = None
    if run_hook is not None:
        _as_ini = (arm.get("wsjtx") or {}).get("ini_path") if isinstance(arm, dict) else None
        _as_handle = run_hook.start(run_dir, _as_ini)
        if _as_handle is not None:
            import atexit
            atexit.register(run_hook.stop, _as_handle)

    # ── Step 0: Pre-flight warm-up check ──────────────────────────────────
    # Play one FT8 cycle at +6 dB SNR and ask the operator to confirm both
    # WSJT-X and OpenWSFZ decoded it.  This catches routing failures before
    # any study data is recorded.  The cycle is NOT written to truth.csv.
    def _mechanical_warmup_check(record_name: str) -> bool:
        """Both ALL.TXT must gain a line from a synthetic cycle (up to 3 attempts); the result is written to <run>/<record_name>. Used before scenario 1 and after every WSJT-X restart."""
        import json as _json
        from harness import warmup_check
        from harness import run_scenario as _rs
        from harness.warmup import _render_warmup_cycle
        import sounddevice as _sd
        _dev = _rs._select_device(args.device)
        _buf = _render_warmup_cycle()

        def _play(boundary_ts: float) -> None:
            time.sleep(max(0.0, boundary_ts - _rs._CYCLE_PREWARM_S - time.time()))
            _sd.play(_buf, samplerate=48_000, device=_dev, blocking=False)
            _sd.wait()
        print("  Mechanical warm-up check (both ALL.TXT must gain a line from a synthetic cycle) ...", flush=True)
        _ok, _res = warmup_check.mechanical_warmup(_play, str(WSJT_ALL_TXT), str(OWSFZ_ALL_TXT))
        (run_dir / record_name).write_text(_json.dumps(_res, indent=1), encoding="utf-8")
        for _r in _res["attempts"]:
            print(f"    attempt {_r['attempt']} slot {_r['slot_stamp']}: WSJT-X {_r['wsjtx_lines']} line(s), OpenWSFZ {_r['owsfz_lines']} line(s)", flush=True)
        if not _ok:
            print(f"  Warm-up check FAILED: {_res['message']}", flush=True)
        else:
            print("  Warm-up check PASSED.\n", flush=True)
        return _ok

    if args.skip_warmup:
        # The interactive prompt is skipped (supervised run), the MECHANICAL check is not: both appraisers must decode a synthetic cycle
        # before scenario 1, or the battery stops here (2026-10-13; the Linux repeats ran with WSJT-X silent).
        if scenario_ids == [_S6_ID]:
            print("  Warm-up: S6 runs its own mechanical warm-up.")
        elif args.no_warmup_check:
            print("  WARNING: --no-warmup-check: NO warm-up of any kind; a silent appraiser would not be noticed.", flush=True)
            (run_dir / "warmup_check.json").write_text('{"skipped": "--no-warmup-check"}', encoding="utf-8")
        else:
            if not _mechanical_warmup_check("warmup_check.json"):
                sys.exit("ERROR: the mechanical warm-up failed. Nothing was run. (Start/repair the silent appraiser and re-launch.)")
        return _ok

    if args.skip_warmup:
        # The interactive prompt is skipped (supervised run), the MECHANICAL check is not: both appraisers must decode a synthetic cycle
        # before scenario 1, or the battery stops here (2026-10-13; the Linux repeats ran with WSJT-X silent).
        if scenario_ids == [_S6_ID]:
            print("  Warm-up: S6 runs its own mechanical warm-up.")
        elif args.no_warmup_check:
            print("  WARNING: --no-warmup-check: NO warm-up of any kind; a silent appraiser would not be noticed.", flush=True)
            (run_dir / "warmup_check.json").write_text('{"skipped": "--no-warmup-check"}', encoding="utf-8")
        else:
            import json as _json
            from harness import warmup_check
            from harness import run_scenario as _rs
            from harness.warmup import _render_warmup_cycle
            import sounddevice as _sd
            _dev = _rs._select_device(args.device)
            _buf = _render_warmup_cycle()

            def _play(boundary_ts: float) -> None:
                time.sleep(max(0.0, boundary_ts - _rs._CYCLE_PREWARM_S - time.time()))
                _sd.play(_buf, samplerate=48_000, device=_dev, blocking=False)
                _sd.wait()
            print("  Mechanical warm-up check (both ALL.TXT must gain a line from a synthetic cycle) ...", flush=True)
            _ok, _res = warmup_check.mechanical_warmup(_play, str(WSJT_ALL_TXT), str(OWSFZ_ALL_TXT))
            (run_dir / "warmup_check.json").write_text(_json.dumps(_res, indent=1), encoding="utf-8")
            for _r in _res["attempts"]:
                print(f"    attempt {_r['attempt']} slot {_r['slot_stamp']}: WSJT-X {_r['wsjtx_lines']} line(s), OpenWSFZ {_r['owsfz_lines']} line(s)", flush=True)
            if not _ok:
                sys.exit(f"ERROR: {_res['message']}. Nothing was run. (Start/repair the silent appraiser and re-launch.)")
            print("  Warm-up check PASSED.\n", flush=True)
    else:
        _py("harness/warmup.py", "--device", args.device)

    # The battery's own window starts here (UTC). ALL.TXT is CUMULATIVE and every battery plays the same
    # seeded texts, so the copies taken below are trimmed to this window (see _trim_log_to_window).
    battery_start_utc = datetime.now(timezone.utc)

    # ── M2: WSJT-X liveness gate (stop and flag; Architect 2026-10-14) ─────
    stall_hit: dict = {"reading": None}
    gate_on = bool(args.liveness_save_dir) and not args.no_liveness_gate
    watchdog_box: dict = {"w": None}
    ledger = _sr.Ledger(str(run_dir), args.scenario_retries)
    if args.liveness_save_dir:
        if args.no_liveness_gate:
            print("  WARNING: --no-liveness-gate: the battery will NOT stop if WSJT-X goes silent mid-run.", flush=True)
            (run_dir / "liveness_gate.json").write_text('{"bypassed": "--no-liveness-gate"}', encoding="utf-8")
        else:
            first = _lv.check_liveness(args.liveness_save_dir, args.liveness_stall_s)
            (run_dir / "liveness_gate.json").write_text(json.dumps({"stall_s": args.liveness_stall_s, "poll_s": args.liveness_poll_s, "save_dir": args.liveness_save_dir,
                                                                   "scenario_retries": args.scenario_retries, "first_reading_ok": first.ok, "first_reading": first.reason,
                                                                   "wsjtx_pids": first.pids}, indent=1), encoding="utf-8")
            if not first.ok:
                _flag_stall_and_exit(run_dir, first, None, "before scenario 1")

    def _start_watchdog() -> None:
        if not gate_on:
            return
        stall_hit["reading"] = None

        def _on_stall(r) -> None:
            stall_hit["reading"] = r
            child = _CHILD
            if child is not None and child.poll() is None:
                child.terminate()
        watchdog_box["w"] = _lv.Watchdog(args.liveness_save_dir, _on_stall, args.liveness_stall_s, args.liveness_poll_s)
        watchdog_box["w"].start()
        print(f"  Liveness gate ON: save dir {args.liveness_save_dir}, stall limit {args.liveness_stall_s:.0f} s, poll {args.liveness_poll_s:.0f} s, retries per scenario {args.scenario_retries}", flush=True)

    def _stop_watchdog() -> None:
        if watchdog_box["w"] is not None:
            watchdog_box["w"].stop()
            watchdog_box["w"].join(2.0)
            watchdog_box["w"] = None

    def _restart_wsjtx_and_rewarm() -> None:
        """Retry step: restart WSJT-X, prove it listens (warm-up), restart the gate. A failure here halts (exit 23): there is nothing to rerun on."""
        print("  Restarting WSJT-X (--wsjtx-restart-cmd) ...", flush=True)
        try:
            rr = subprocess.run(args.wsjtx_restart_cmd, shell=True, timeout=300)
        except subprocess.TimeoutExpired:
            print("  *** WSJT-X restart command timed out (300 s): halting. ***", flush=True)
            raise SystemExit(23)
        if rr.returncode != 0:
            print(f"  *** WSJT-X restart command failed (rc {rr.returncode}): halting. ***", flush=True)
            raise SystemExit(23)
        if not _mechanical_warmup_check("warmup_check_after_restart_%d.json" % (ledger.sc and sum(v["retries_used"] for v in ledger.sc.values()) or 1)):
            print("  *** WSJT-X was restarted but did not pass the warm-up: halting. ***", flush=True)
            raise SystemExit(23)

    _start_watchdog()

    # ── Step 1: Run all scenarios (each in as many attempts as the per-scenario retry cap allows) ──
    for sid, sf in zip(scenario_ids, scenario_files):
        if not sf.exists():
            sys.exit(f"ERROR: scenario file not found: {sf}")
        while True:
            attempt = ledger.start(sid)
            t_attempt = datetime.now(timezone.utc)
            failure = None                    # (kind, reason)
            if watchdog_box["w"] is not None:
                _pre = _lv.check_liveness(args.liveness_save_dir, args.liveness_stall_s)
                if not _pre.ok:
                    failure = ("stall-before", _pre.reason, _pre)
            if failure is None:
                try:
                    run_args = [
                        "harness/run_scenario.py", str(sf),
                        "--device", args.device,
                        "--run-dir", str(run_dir),
                    ]
                    parts_for_this = args.parts or scenario_part_overrides.get(sid)
                    if parts_for_this:
                        run_args += ["--parts", parts_for_this]
                    if sid == _S3C_ID:
                        # S3c is the LAST playback and additive: its failure must never cost S1-S8's logs,
                        # matcher and analyser (check=False; the scorer then finds no playback log and warns).
                        r3 = _py("s3c/s3c_play.py", "--scenario", str(sf), "--run-dir", str(run_dir),
                                 "--device", args.device, check=False)
                        if r3.returncode != 0:
                            print(f"  [WARN] S3c playback exited {r3.returncode}; S1-S8 continue", flush=True)
                    elif sid == _S6_ID:
                        # S6 is additive and LAST: its failure (any exit code) voids the S6 block only; S1-S8's logs, matcher and analyser stand.
                        wsjtx_exe = args.s6_wsjtx_exe or (str(Path.home() / "wsjtx-2.7.0" / "bin" / "wsjtx") if sys.platform != "win32" else None)
                        r6 = _py("s6/s6_play.py", "--run-dir", str(run_dir), "--tier", args.s6_tier, "--corpus", str(_s6_corpus(args)),
                                 "--device", args.device, "--wsjt-all-txt", str(WSJT_ALL_TXT), "--owsfz-all-txt", str(OWSFZ_ALL_TXT),
                                 *(["--ows-lib", args.s6_ows_lib] if args.s6_ows_lib else []),
                                 *(["--wsjtx-exe", wsjtx_exe] if wsjtx_exe and Path(wsjtx_exe).is_file() else []), check=False)
                        if r6.returncode != 0:
                            print(f"  [WARN] S6 playback exited {r6.returncode} (2 = corpus verification, 4 = warm-up, 5 = pins, 6 = other); S1-S8 continue", flush=True)
                    else:
                        _py(*run_args)
                except subprocess.CalledProcessError:
                    if stall_hit["reading"] is None:
                        raise                  # a failure that is NOT a WSJT-X stall halts at once (the caller sees the traceback)
                if stall_hit["reading"] is not None:
                    failure = ("stall", stall_hit["reading"].reason, stall_hit["reading"])
                else:
                    time.sleep(_POST_SCENARIO_SETTLE_S)
                    if gate_on:
                        # coverage right after the scenario: both appraisers must have data for its cycles (M3: expected - 1 for S1-S8; S6-V7: every play slot)
                        _w0 = t_attempt - timedelta(seconds=30)
                        _ws = _lv.list_wav_slots(args.liveness_save_dir, _w0, datetime.now(timezone.utc))
                        _os = _lv.list_wav_slots(args.coverage_owsfz_dir, _w0, datetime.now(timezone.utc)) if args.coverage_owsfz_dir else None
                        _cf = _sr.coverage_failure(str(run_dir), sid, _ws, _os)
                        if _cf:
                            failure = ("coverage", _cf["reason"], None)
            if failure is None:
                print(f"  [OK] {sf.name} complete" + (f" (attempt {attempt})" if attempt > 1 else "") + "\n", flush=True)
                break
            # ---- a failed attempt: stop and flag, or retry within the per-scenario cap
            kind, reason, reading = failure
            _stop_watchdog()
            can_retry = ledger.retries_used(sid) < args.scenario_retries and bool(args.wsjtx_restart_cmd)
            aside = _sr.set_aside(str(run_dir), sid, attempt) if (can_retry or args.scenario_retries > 0) else {"cycles": [], "moved": [], "truth_rows_set_aside": 0}
            ledger.fail(sid, kind, reason, aside, can_retry)
            print(f"\n  *** {sid} attempt {attempt} FAILED ({kind}: {reason}); " + ("retry %d of %d: restarting WSJT-X and rerunning %s with all its trials ***" % (ledger.retries_used(sid), args.scenario_retries, sid) if can_retry else "no retry left: STOP AND FLAG ***"), flush=True)
            if not can_retry:
                if args.scenario_retries > 0:
                    (run_dir / "RETRIES_EXHAUSTED.json").write_text(json.dumps({"utc": _sr.utc_now(), "scenario": sid, "attempts": attempt, "cap_retries_per_scenario": args.scenario_retries,
                                                                                "last_failure": {"kind": kind, "reason": reason},
                                                                                "note": "The 4th failure of the same scenario (3 retries used): the battery HALTS and flags; nothing is repaired. See scenario_retries.json."}, indent=1), encoding="utf-8")
                    raise SystemExit(22)
                if reading is not None:
                    _flag_stall_and_exit(run_dir, reading, sid, "before the scenario" if kind == "stall-before" else "during the scenario")
                # coverage failure with no retries allowed: flag it as a stall-class stop (the sweep is INVALID)
                class _R:                     # noqa: N801 (a tiny record for the flag file)
                    pass
                _r = _R()
                _r.reason, _r.age_s, _r.pids = reason, None, []
                _flag_stall_and_exit(run_dir, _r, sid, "coverage after the scenario")
            _restart_wsjtx_and_rewarm()
            _start_watchdog()

    _stop_watchdog()
    ledger.write()                       # always: the stall row counts every scenario's attempts, also when nothing failed
    if run_hook is not None:
        run_hook.stop(_as_handle)
    print(f"\nRun directory: {run_dir.relative_to(_HERE)}")

    # ── Step 3: Collect log files ──────────────────────────────────────────
    print("\nCollecting decode logs ...")
    if not WSJT_ALL_TXT.exists():
        sys.exit(
            f"ERROR: WSJT-X ALL.TXT not found at {WSJT_ALL_TXT}\n"
            "       Was Monitor ON and did WSJT-X decode anything?"
        )
    if not OWSFZ_ALL_TXT.exists():
        sys.exit(
            f"ERROR: OpenWSFZ ALL.TXT not found at {OWSFZ_ALL_TXT}\n"
            "       Is decodeLog.enabled = true in config?"
        )

    wsjt_dest  = run_dir / "wsjt-all.txt"
    owsfz_dest = run_dir / "owsfz-all.txt"
    shutil.copy2(WSJT_ALL_TXT,  wsjt_dest)
    shutil.copy2(OWSFZ_ALL_TXT, owsfz_dest)
    print(f"  Copied WSJT-X   -> {wsjt_dest.name}")
    print(f"  Copied OpenWSFZ -> {owsfz_dest.name}")
    for dest in (wsjt_dest, owsfz_dest):
        kept, dropped = _trim_log_to_window(dest, battery_start_utc)
        print(f"  Trimmed {dest.name} to this battery's window: kept {kept} lines, dropped {dropped} earlier ones")
        if ledger.invalid_cycles:
            _gone = _sr.drop_cycles_from_log(str(dest), ledger.invalid_cycles)
            print(f"  Removed {_gone} line(s) of INVALID scenario attempts from the copy {dest.name} (the live log is untouched)", flush=True)

    # M3: the cycles for which each appraiser had audio data in this battery's window (slot stamps only; the analyser's coverage row reads them)
    if args.liveness_save_dir:
        _end = datetime.now(timezone.utc)
        _w = _lv.list_wav_slots(args.liveness_save_dir, battery_start_utc, _end)
        _lv.write_slots(str(run_dir / "coverage_slots_wsjtx.txt"), _w)
        print(f"  Coverage slots: WSJT-X {len(_w)} cycles with a saved WAV", flush=True)
        if args.coverage_owsfz_dir:
            _o = _lv.list_wav_slots(args.coverage_owsfz_dir, battery_start_utc, _end)
            _lv.write_slots(str(run_dir / "coverage_slots_owsfz.txt"), _o)
            print(f"  Coverage slots: OpenWSFZ {len(_o)} cycles in the cycle-audio archive", flush=True)

    # S6 plays REAL off-air audio: its log lines carry real callsigns and would be unexplained decodes to the S1-S8 matcher. Move them out of the
    # run folder's copies into a scratch dir outside git before anything reads the copies (NFR-021, HK-037).
    s6_scratch = _s6_scratch(args, run_dir)
    if _S6_ID in scenario_ids and (run_dir / "s6" / "s6_playlog.jsonl").is_file():
        _py("s6/s6_split.py", "--run-dir", str(run_dir), "--wsjt-copy", str(wsjt_dest), "--owsfz-copy", str(owsfz_dest),
            "--scratch", str(s6_scratch), check=False)

    # Record WSJT-X version
    ver_path = run_dir / "wsjt-version.txt"
    ver_path.write_text("WSJT-X 2.7.0 (inferred from binary date 2025-02-04)", encoding="utf-8")

    # ── Step 4: Run matcher for each scenario ──────────────────────────────
    print("\nRunning matcher ...")
    for scen_id in scenario_ids:
        if scen_id in (_S3C_ID, _S6_ID):
            continue                      # not in truth.csv; S3c is scored by s3c_score.py below, S6 by s6_analyse.py after the analyser
        _py(
            "harness/matcher.py",
            "--run-dir", str(run_dir),
            "--scenario", scen_id,
            "--wsjt",  str(wsjt_dest),
            "--owsfz", str(owsfz_dest),
        )
        print(f"  [OK] {scen_id} matched\n", flush=True)

    # ── Step 4b: S3c rows (counts only; a failure here never blocks the analyser) ─────────────
    if _S3C_ID in scenario_ids:
        print("\nScoring S3c ...")
        r = _py("s3c/s3c_score.py", "--scenario", str(_SCENARIO_REGISTRY[_S3C_ID]),
                "--run-dir", str(run_dir), "--wsjtx-alltxt", str(wsjt_dest),
                "--owsfz-alltxt", str(owsfz_dest),
                "--subtraction-enabled", args.s3c_flag_state, "--build-sha", args.s3c_build_sha,
                "--dll-sha256-prefix", args.s3c_dll_sha256_prefix,
                "--trend", str(_HERE / "s3c_trend.csv"), check=False)
        if r.returncode != 0:
            print(f"  [WARN] S3c scoring exited {r.returncode}; the battery continues (see the run log)",
                  flush=True)

    # ── Step 5: Analyse ────────────────────────────────────────────────────
    s6_only = scenario_ids == [_S6_ID]
    if s6_only:
        # An S6-only run has no truth.csv and no *_matched.csv: the S1-S8 analyser would crash (found on the first dry run, 2026-10-13). The S6
        # analysis below writes this run's whole report.
        print("\nS6-only run: the S1-S8 matcher/analyser is skipped.", flush=True)
    else:
        print("\nRunning analyser ...")
        _py("harness/analyse.py", "--run-dir", str(run_dir),
            *(["--legacy-no-arm-config"] if args.legacy_no_arm_config else []))

    # ── Step 5b: S6 analysis (aggregates only; a failure never blocks the report) ───────────────────────────
    if _S6_ID in scenario_ids and (run_dir / "s6" / "s6_playlog.jsonl").is_file():
        r6a = _py("s6/s6_analyse.py", "--run-dir", str(run_dir), "--scratch", str(s6_scratch),
                  *(["--daemon-log", args.daemon_log] if args.daemon_log else []),
                  "--series-label", f"{args.s6_series_label} (tier {args.s6_tier})", "--corpus", str(_s6_corpus(args)), check=False)
        blk = run_dir / "s6" / "s6_section5.md"
        if r6a.returncode == 0 and blk.is_file() and s6_only:
            from s6 import s6_report_header
            (run_dir / "report.md").write_text(s6_report_header.header(run_dir, arm, args) + "\n" + blk.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  S6-only report written: {run_dir / 'report.md'}", flush=True)
        elif r6a.returncode == 0 and blk.is_file():
            with open(run_dir / "report.md", "a", encoding="utf-8") as _fh:
                _fh.write("\n\n" + blk.read_text(encoding="utf-8"))
        else:
            print(f"  [WARN] S6 analysis exited {r6a.returncode}; the report carries no S6 block", flush=True)

    # ── Step 6: audio-setup summary (#194): crashes, restarts, coverage, changes; into the report ──
    if run_hook is not None:
        _md = run_hook.finish(_as_handle, run_dir)
        if _md:
            with open(run_dir / "report.md", "a", encoding="utf-8") as _fh:
                _fh.write("\n\n" + _md)

    print("\n" + "=" * 70)
    print(f"Study complete.  Report: {run_dir / 'report.md'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
