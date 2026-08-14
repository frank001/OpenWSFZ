#!/usr/bin/env python3
"""Top-level driver -- runs M0 through M4 (M4 gated) as ONE unattended Python process.

Implements `2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md` end to
end, per the Captain's 2026-08-06 instruction to run the entire chain unattended. Sequencing
follows SS7's dependency graph exactly:

    M0                              always, first.
    M1 + M2                         always, offline, one shared data pull.
    M3                              always, independent of M1's outcome.
    M4                              ONLY if M1 fired ROW 1. Otherwise MUST NOT RUN.

Every pre-registered gate that the spec marks HALT/escalate stops this script's own further
action on that thread of the investigation -- it does not invent extra measurements to
"resolve" an escalation, it reports the escalation plainly in the final write-up. M0 and
M1+M2 failing outright (not "fired an escalate row", but "the extraction itself broke") is
fatal to the whole run, since nothing downstream can be trusted without them.

PRECONDITION THIS SCRIPT CANNOT VERIFY BY ITSELF: WSJT-X must already be running,
`--rig-name=FT991A`, Deep/AP off, listening on `CABLE Output`, with Monitor switched ON,
before this script is started. There is no API this script can use to flip that toggle for
you. `replay_lib.play_pass_guarded()` mitigates the specific failure mode tonight's first
attempt hit (Monitor enabled late) by aborting a pass after 2 silent cycles rather than
running blind for the full 5 minutes -- but it cannot turn Monitor on for you, and a run
that aborts twice in a row means the precondition was not met, not that the script is
broken.

NFR-021: no message text or callsign is ever printed or written by this script; every
sub-module it calls holds the same discipline. ASCII-only console output (HK-009).
"""
from __future__ import annotations

import datetime
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # HK-009
except AttributeError:
    pass

import gates  # noqa: E402
import m0_preserve  # noqa: E402
import m1_m2_analysis  # noqa: E402
import m3_select_window  # noqa: E402
import mapping  # noqa: E402
import replay_lib  # noqa: E402
from m4_load import LoadGenerator  # noqa: E402

import os  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "..", "endurance"))
from anova_common import normalize_hash_tokens, parse_all_txt  # noqa: E402

LIVE_REPLAY_DIR = HERE.parents[0] / "2026-08-06-live-cross-decode-replay"
sys.path.insert(0, str(LIVE_REPLAY_DIR))
from run_cross_decode_replay import WINDOW as BUSY_WINDOW  # noqa: E402

REPO_ROOT = HERE.parents[2]  # HERE is already this script's own directory, not the file
CORPUS = REPO_ROOT / "artefacts" / "20260803_live_run_1713"
PRESERVED_DIR = REPO_ROOT / "artefacts" / "20260806_cross_decode_replay_2009"

M3_PORT = 8090
M4_PORT = 8091
MAX_ATTEMPTS_PER_RUN = 2  # bounded retry on PreflightAbort, HK-013 discipline: cap, don't loop
PASS_DURATION_S = 20 * replay_lib.SLOT_SECONDS  # 300s of audio
LOAD_DURATION_S = PASS_DURATION_S + 90  # covers daemon warmup + flush either side of playback


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] ORCH: {msg}", flush=True)


def utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def run_replay_with_retry(run_dir: Path, port: int, wav_dir: Path, window_wav_files: list[str],
                           label: str) -> dict:
    """Wraps replay_lib.run_single_pass() with a bounded retry on preflight-abort (the
    Monitor-not-listening failure mode), per HK-013's 'cap retries, do not loop forever'."""
    last = None
    for attempt in range(1, MAX_ATTEMPTS_PER_RUN + 1):
        log(f"{label}: attempt {attempt}/{MAX_ATTEMPTS_PER_RUN}")
        time.sleep(2)  # let the prior attempt's port fully release (HK-019)
        result = replay_lib.run_single_pass(run_dir, port, wav_dir, window_wav_files, label)
        last = result
        if not result["aborted"]:
            return result
        log(f"{label}: attempt {attempt} aborted (preflight). "
            f"{'Retrying.' if attempt < MAX_ATTEMPTS_PER_RUN else 'Out of attempts.'}")
        time.sleep(5)
    return last


def count_live_wsjtx_for_window(pass_start_iso: str, window_cycles: list[str]) -> int:
    """Re-reads the LIVE (growing) WSJT-X AppData ALL.TXT and returns the number of distinct
    (cycle, normalised message) keys this run's own pass-1 slot map picked up. Re-parsing
    the whole file each time is deliberate and cheap (file stays well under 1 MB for a
    session like this) -- it avoids any cursor/offset bookkeeping bug class entirely."""
    rows = parse_all_txt(str(replay_lib.WSJTX_ALL_TXT))
    mapped, _ = mapping.map_rows_to_cycles(rows, pass_start_iso, window_cycles)
    keys = {(m["corpus_cycle"], normalize_hash_tokens(m["message"])) for m in mapped}
    return len(keys)


def get_w0_busy_no_load() -> float:
    """The established no-load comparator for the busy window -- mean of tonight's 5-run
    ANOVA series' pass-1 WSJT-X counts, read from the M0-preserved summaries rather than
    hardcoded (SS6.1: 'the no-load control is free -- tonight's 5 runs already provide
    W(0) = 754 on this window')."""
    vals = []
    for i in range(1, 6):
        p = PRESERVED_DIR / f"summary_run{i}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        vals.append(d["pass1"]["n_wx"])
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# M0
# ---------------------------------------------------------------------------
def stage_m0() -> dict:
    log("=== M0: preserve evidence ===")
    result = m0_preserve.run()
    m0_preserve.regenerate_inventory()
    log("M0 complete.")
    return {"status": "COMPLETE", **result}


# ---------------------------------------------------------------------------
# M1 + M2
# ---------------------------------------------------------------------------
def stage_m1_m2() -> dict:
    log("=== M1 + M2: offline SNR/set-test gates ===")
    m1_m2_analysis.main()
    result = json.loads((HERE / "m1_m2_result.json").read_text(encoding="utf-8"))
    log(f"M1 row: {result['m1'].get('row')}. M2: "
        f"{result['m2'].get('row', result['m2'].get('verdict'))}.")
    return result


# ---------------------------------------------------------------------------
# M3
# ---------------------------------------------------------------------------
def stage_m3() -> dict:
    log("=== M3: low-density window replay (runs regardless of M1) ===")
    m3_select_window.main()
    selection = json.loads((HERE / "m3_window_selection.json").read_text(encoding="utf-8"))

    if not selection["run_m3"]:
        log("M3 NOT RUN: density-leverage contrast below 3.0 (SS5.2 step 5). Escalating.")
        return {"status": "NOT RUN", "reason": "density leverage contrast < 3.0",
                "selection": selection}

    window_cycles = selection["selected_window"]
    window_wav_files = selection["selected_window_wav_files"]
    wav_dir = CORPUS / "wsjt-x" / "wav"

    counts = []
    run_details = []
    for i in (1, 2, 3):
        run_dir = HERE / "_work" / "m3" / f"run{i}"
        result = run_replay_with_retry(run_dir, M3_PORT, wav_dir, window_wav_files,
                                        f"M3 run{i}")
        if result["aborted"]:
            log(f"M3 run{i}: FATAL -- aborted on every attempt. Cannot proceed "
                f"autonomously: WSJT-X did not respond. Halting M3.")
            return {"status": "HALTED", "reason": f"run{i} aborted on every attempt "
                    f"(WSJT-X preflight check never saw growth) -- Monitor may not be "
                    f"enabled, or the machine violated the 'no other audio work' "
                    f"precondition.", "selection": selection, "run_details": run_details}
        count = count_live_wsjtx_for_window(result["pass_start"], window_cycles)
        counts.append(count)
        run_details.append({"run": i, "count": count, **result})
        log(f"M3 run{i}: WSJT-X pass-1 count on selected window = {count}")

    validity = gates.m3_validity(counts)
    if validity:
        log(f"M3 VALIDITY GATE FIRED: {validity}. SS5.4 not evaluated. Escalating.")
        return {"status": "INVALID", "reason": validity, "counts": counts,
                "selection": selection, "run_details": run_details}

    archived_wsjtx_rows = [r for r in parse_all_txt(str(CORPUS / "wsjt-x" / "ALL.TXT"))
                            if r["ts"] in set(window_cycles)]
    archived_original_count = len(archived_wsjtx_rows)
    s_low = (sum(counts) / len(counts)) / archived_original_count if archived_original_count else float("inf")
    row = gates.m3_row(s_low)
    log(f"M3 result: s_low={s_low:.3f} -> {row} -- {gates.M3_CONSEQUENCE[row]}")

    return {
        "status": "EVALUATED", "row": row, "consequence": gates.M3_CONSEQUENCE[row],
        "s_low": s_low, "counts": counts, "archived_original_count": archived_original_count,
        "selection": selection, "run_details": run_details,
    }


# ---------------------------------------------------------------------------
# M4 (gated)
# ---------------------------------------------------------------------------
def stage_m4(m1_row: str) -> dict:
    if m1_row != "ROW 1":
        log(f"=== M4: SKIPPED -- M1 fired {m1_row}, not ROW 1. M4 MUST NOT RUN. ===")
        return {"status": "SKIPPED", "reason": f"M1 fired {m1_row}, gate requires ROW 1"}

    log("=== M4: load sweep (authorised -- M1 fired ROW 1) ===")
    c = replay_lib.get_logical_processor_count()
    import math
    levels = {"L1": math.ceil(c / 2), "L2": c, "L3": 2 * c}
    log(f"C (logical processors) = {c} -> L1={levels['L1']} L2={levels['L2']} L3={levels['L3']}")

    busy_window_cycles = [w[:-4] for w in BUSY_WINDOW]
    wav_dir = CORPUS / "wsjt-x" / "wav"

    w0 = get_w0_busy_no_load()
    counts: dict[str, int] = {}
    cpu_util: dict[str, list[float]] = {}
    run_details = []

    for level_label in ("L1", "L2", "L3"):
        n_workers = levels[level_label]
        run_dir = HERE / "_work" / "m4" / level_label
        gen = LoadGenerator(n_workers, level_label)
        util_samples = []
        gen.start(LOAD_DURATION_S)
        try:
            time.sleep(10)  # let load ramp before sampling / before playback begins
            s = replay_lib.get_cpu_utilization_percent()
            if s is not None:
                util_samples.append(s)
            result = run_replay_with_retry(run_dir, M4_PORT, wav_dir, BUSY_WINDOW, f"M4 {level_label}")
            s = replay_lib.get_cpu_utilization_percent()
            if s is not None:
                util_samples.append(s)
        finally:
            gen.stop()

        if result["aborted"]:
            log(f"M4 {level_label}: FATAL -- aborted on every attempt. Halting M4.")
            return {"status": "HALTED", "reason": f"{level_label} aborted on every attempt",
                    "levels": levels, "w0": w0, "counts": counts, "run_details": run_details}

        count = count_live_wsjtx_for_window(result["pass_start"], busy_window_cycles)
        counts[level_label] = count
        cpu_util[level_label] = util_samples
        run_details.append({"level": level_label, "n_workers": n_workers, "count": count,
                             "cpu_util_pct_samples": util_samples, **result})
        avg_util = (sum(util_samples) / len(util_samples)) if util_samples else None
        log(f"M4 {level_label}: n_workers={n_workers}, count={count}, "
            f"avg CPU util={avg_util}")

    w1, w2, w3 = counts["L1"], counts["L2"], counts["L3"]
    row = gates.m4_row(w1, w2, w3)
    log(f"M4 result: W(L1)={w1} W(L2)={w2} W(L3)={w3} -> {row} -- {gates.M4_CONSEQUENCE[row]}")

    return {
        "status": "EVALUATED", "row": row, "consequence": gates.M4_CONSEQUENCE[row],
        "w0_no_load": w0, "levels": levels, "counts": counts, "cpu_util_samples": cpu_util,
        "run_details": run_details,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def write_report(results: dict) -> Path:
    L = []
    L.append("# QA -> Architect: reference-suppression investigation, M0-M4 -- results")
    L.append("")
    L.append(f"**Author:** QA (autonomous orchestrator), {utc_stamp()} (per HK-017).")
    L.append("**Executes:** "
              "`2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`, "
              "run in full per the Captain's instruction to run the entire chain "
              "unattended, M4 gated on M1's own outcome as specced.")
    L.append("**Script:** "
              "`qa/cycleframer-alignment-replay/2026-08-07-reference-suppression-m0-m4/"
              "orchestrate.py`.")
    L.append("")
    L.append("---")
    L.append("")

    m0 = results.get("m0", {})
    L.append("## M0 -- evidence preservation")
    L.append("")
    L.append(f"**Status: {m0.get('status', 'DID NOT RUN')}.** "
              f"Preserved to `{m0.get('out_dir', 'n/a')}`.")
    L.append("")

    m1m2 = results.get("m1_m2", {})
    m1 = m1m2.get("m1", {})
    m2 = m1m2.get("m2", {})
    L.append("## M1 -- SNR signature of the suppressed decodes")
    L.append("")
    L.append(f"**{m1.get('row', 'DID NOT RUN')}.** {m1.get('consequence', m1.get('reason', ''))}")
    if "delta_db" in m1:
        L.append("")
        L.append(f"- delta = {m1['delta_db']:+.3f} dB, p = {m1['p']:.6g} "
                  f"(Mann-Whitney U = {m1['u_stat']:.1f})")
        L.append(f"- median(NEW) = {m1['median_new']:+.1f} dB (n={m1['n_new']}), "
                  f"median(SHARED) = {m1['median_shared']:+.1f} dB (n={m1['n_shared']})")
    L.append("")

    L.append("## M2 -- direct set test, OpenWSFZ-exclusive population")
    L.append("")
    L.append(f"**{m2.get('row', m2.get('verdict', 'DID NOT RUN'))}.** "
              f"{m2.get('consequence', m2.get('reason', ''))}")
    if "r_owsfz" in m2:
        L.append("")
        L.append(f"- R_owsfz = {m2['r_owsfz']:.4f}, R_owsfz_all5 = {m2['r_owsfz_all5']:.4f}, "
                  f"R_wsjtx_self = {m2['r_wsjtx_self']:.4f}")
        if m2.get("residual_exclusive_count") is not None:
            L.append(f"- residual exclusive population: {m2['residual_exclusive_count']}")
        if m2.get("intermittency_note"):
            L.append(f"- {m2['intermittency_note']}")
    L.append("")

    m3 = results.get("m3", {})
    L.append("## M3 -- does it generalise? low-density window replay")
    L.append("")
    L.append("> **Provenance note.** The first attempt at this stage (this same report, "
              "prior version) reported `ROW 4 -- ANOMALY, instrument suspect, s_low=0.217`. "
              "That result is **VOID**, not a finding: `replay_lib.py`'s preflight check "
              "contained a 10.0s blocking sleep inside the playback loop, which "
              "desynchronised every cycle from the 3rd onward off the 15s UTC slot grid. "
              "See `2026-08-06-2249-architect-to-qa-m3-void-preflight-desync.md` for the "
              "full root-cause analysis. **`s_low=0.217` must not be cited anywhere.** The "
              "fix (no sleep; a mandatory <3.0s phase-lock assertion added instead) and a "
              "corrected window-selection rule (floor raised 60->100, selection changed "
              "from the minimum to the 10th percentile among survivors, since minimising "
              "subject to a floor is guaranteed to land exactly on it) are both applied "
              "below.")
    L.append("")
    L.append(f"**Status: {m3.get('status', 'DID NOT RUN')}.**")
    if m3.get("status") == "EVALUATED":
        L.append("")
        L.append(f"**{m3['row']}.** {m3['consequence']}")
        L.append("")
        L.append(f"- s_low = {m3['s_low']:.3f} (S_busy comparator = 2.30)")
        L.append(f"- 3 replicate counts: {m3['counts']}, "
                  f"archived original count: {m3['archived_original_count']}")
        sel = m3["selection"]
        L.append(f"- selected window: {sel['selected_window'][0]} .. "
                  f"{sel['selected_window'][-1]}, mean_combined="
                  f"{sel['mean_combined']:.2f}/cycle, contrast={sel['contrast']:.2f}")
    elif m3.get("reason"):
        L.append(f"Reason: {m3['reason']}")
        sel = m3.get("selection")
        if sel:
            L.append("")
            L.append(f"- candidate window (target {sel.get('target_percentile', '?')}th pct, "
                      f"floor >= {sel.get('min_wsjtx_total_floor', '?')}): "
                      f"{sel['selected_window'][0]} .. {sel['selected_window'][-1]}, "
                      f"mean_combined={sel['mean_combined']:.2f}/cycle, "
                      f"wsjtx_total={sel['wsjtx_total']}")
            L.append(f"- contrast against busy window = {sel['contrast']:.3f} "
                      f"(required >= {sel['min_contrast_required']:.1f})")
    L.append("")

    m4 = results.get("m4", {})
    L.append("## M4 -- load sweep (gated on M1 ROW 1)")
    L.append("")
    L.append(f"**Status: {m4.get('status', 'DID NOT RUN')}.**")
    if m4.get("status") == "EVALUATED":
        L.append("")
        L.append(f"**{m4['row']}.** {m4['consequence']}")
        L.append("")
        L.append(f"- levels: {m4['levels']}")
        L.append(f"- counts: {m4['counts']} (no-load comparator W(0) = {m4['w0_no_load']:.1f})")
    elif m4.get("reason"):
        L.append(f"Reason: {m4['reason']}")
    L.append("")

    L.append("---")
    L.append("")
    L.append("*Per HK-015 this is QA (autonomous) -> Architect. Per HK-014/HK-010 written "
              "locally, no push, no merge implied. Per HK-011 nothing here touches `src/`. "
              "Per NFR-021 no message text or callsign appears in this document. Per "
              "HK-021 every gate above is the spec's own pre-registered code, evaluated "
              "mechanically by `gates.py`, not re-derived here.*")
    L.append("")

    out_path = HERE / "ORCHESTRATION_REPORT.md"
    out_path.write_text("\n".join(L), encoding="utf-8")
    (HERE / "orchestration_result.json").write_text(json.dumps(results, indent=2, default=str),
                                                      encoding="utf-8")
    return out_path


def main() -> int:
    results: dict = {}
    try:
        results["m0"] = stage_m0()
    except Exception as exc:  # noqa: BLE001
        log(f"M0 FAILED FATALLY: {exc}")
        traceback.print_exc()
        results["m0"] = {"status": "FAILED", "error": str(exc)}
        write_report(results)
        return 1

    try:
        results["m1_m2"] = stage_m1_m2()
    except Exception as exc:  # noqa: BLE001
        log(f"M1+M2 FAILED FATALLY: {exc}")
        traceback.print_exc()
        results["m1_m2"] = {"m1": {"row": "FAILED", "reason": str(exc)},
                             "m2": {"verdict": "FAILED", "reason": str(exc)}}
        write_report(results)
        return 1

    m1_row = results["m1_m2"]["m1"].get("row", "FAILED")

    try:
        results["m3"] = stage_m3()
    except Exception as exc:  # noqa: BLE001
        log(f"M3 FAILED: {exc}")
        traceback.print_exc()
        results["m3"] = {"status": "FAILED", "error": str(exc)}

    try:
        results["m4"] = stage_m4(m1_row)
    except Exception as exc:  # noqa: BLE001
        log(f"M4 FAILED: {exc}")
        traceback.print_exc()
        results["m4"] = {"status": "FAILED", "error": str(exc)}

    report_path = write_report(results)
    log(f"DONE. Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
