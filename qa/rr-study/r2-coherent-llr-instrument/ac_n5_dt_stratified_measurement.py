#!/usr/bin/env python3
"""tasks.md Sec.17.4 -- AC-N5, THE MEASUREMENT. REPORTED, NOT GATED (Amendment 3
Sec.5, replacing Amendment 2's crowding-framed version in full).

Runs S3 (the DT sweep) and S8 (band scene). For every decode, reports signal_db,
local_noise_db, the reconstructed SNR, and true_dt -- stratified by true_dt, not by
scenario or neighbour density. The question is specific: at true_dt == 0, which of
the two terms moves?

Reuses run_scenario.py's own render functions (_load_scenario/_load_messages/
_render_single/_render_band_scene) and harness.common.compute_seed VERBATIM (HK-018)
-- the SAME deterministic synthesis pipeline run_study.py's live playback path uses,
just called directly against ft8_decode_all + the new ft8_get_last_snr_terms getter
instead of played through VB-CABLE and read back from ALL.TXT. This is a genuine
methodology change from the live B-dt-A run (2026-08-22-d4ce254), forced by the fact
that ft8_get_last_snr_terms has NO production call site (task 14.4) -- the live
daemon's own ALL.TXT can never carry these two terms no matter how the audio reaches
it, so an offline direct-decode harness is the only way to pair them with a KNOWN
true_dt at all. Flagged plainly in the report, not smoothed over.

S3 parts 8/9 (dt_s 2.4/2.7) are SKIPPED: the scenario sets requires_extended_dt=true
scenario-wide, and the extended=True contract only grows the buffer past one slot for
those two parts. Decoding a grown, non-nominal buffer through ft8_decode_all is a
separate methodology question this measurement does not need to answer (the dt==0 vs
dt>0 question is already fully posed by parts 0-7). Do not extrapolate this
measurement to dt_s > 2.1 (HK-026).

RATE CORRECTION (recorded per HK-022, not silently fixed): run_scenario.py's own
_render_single/_render_band_scene render at synth.constants.DEFAULT_SAMPLE_RATE_HZ =
48000 Hz -- correct for their actual job (playback into VB-CABLE, real 48 kHz audio
hardware). ft8_decode_all takes a fixed 180,000-sample buffer at 12,000 Hz
(BUFFER_SAMPLES, extract_llrs_ctypes.py/p23_common.py). Calling those two functions
directly produced 720,000-sample buffers decode_all cannot consume. Fixed by NOT
reusing those two functions' bodies, and instead calling the lower-level
synth.encoder.encode_message / synth.channel.mix_to_shared_floor directly at
sample_rate_hz=12000 -- the SAME functions _render_single/_render_band_scene
themselves call, just parameterised to the decoder's own native rate rather than the
playback rate. This is not a novel construction: it is the exact pattern
row0g_instrument_gain_check.py's own _run_clean_trials already established (SAMPLE_
RATE_HZ = 12000, encoder.encode_message(..., sample_rate_hz=SAMPLE_RATE_HZ)) for the
same reason (HK-018) -- reused here rather than re-derived.
"""
from __future__ import annotations

import os
import statistics as st
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_QA_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, _QA_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))  # p23_common.write_json
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402 -- write_json only
from harness.common import compute_seed  # noqa: E402
from harness.run_scenario import _load_messages, _load_scenario  # noqa: E402
from snr_terms_ctypes import SnrTermsDecoder, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

SCENARIOS_DIR = Path(_QA_ROOT) / "scenarios"
S3_MAX_PART_DT_S = 2.1  # parts 0-7 only; see module docstring
SNR_FORMULA_OFFSET = 26.5
FREQ_MATCH_TOLERANCE_HZ = 30.0  # generous vs. FT8's own tone spacing (6.25 Hz);
                                 # S8's closest pair (E/F) is 12 Hz apart, so this
                                 # tolerance can be ambiguous there -- ambiguous
                                 # matches are flagged, not silently resolved

DECODE_SAMPLE_RATE_HZ = 12_000   # ft8_decode_all's own native rate (BUFFER_SAMPLES
                                  # = 180_000 @ 12 kHz), matches row0g's own
                                  # SAMPLE_RATE_HZ precedent -- see module docstring
S8_NOISE_CUTOFF_HZ = 4700.0      # identical value to run_scenario.py's own
                                  # _NOISE_CUTOFF_HZ (still < 6000 Hz Nyquist at 12 kHz)


def _decode_and_get_terms(dec: SnrTermsDecoder, pcm) -> "tuple[list[dict], list[float], list[float]]":
    import numpy as np  # noqa: PLC0415

    pcm = np.ascontiguousarray(pcm, dtype=np.float32)
    results = dec.decode_all(pcm)
    if results is None:
        return [], [], []
    n, sig, noise = dec.get_last_snr_terms(capacity=max(50, len(results) + 10))
    assert n == len(results), (
        "AC-N3 already gated this contract at tasks.md 17.2 -- a mismatch here would "
        "mean the pinned binary changed between runs; STOP: n=%d len(results)=%d" % (n, len(results)))
    return results, sig, noise


def run_s3(dec: SnrTermsDecoder, log) -> list[dict]:
    from synth import channel, encoder  # noqa: PLC0415 -- lazy, matches this programme's own convention

    messages = _load_messages(SCENARIOS_DIR)
    scenario = _load_scenario(SCENARIOS_DIR / "s3-dt-offset.json", messages)
    parts = [p for p in scenario["parts"] if float(p["dt_s"]) <= S3_MAX_PART_DT_S]
    n_trials = scenario["trials"]
    log("S3: %d/%d parts in scope (dt_s <= %.1f), %d trials each, rendered at %d Hz "
        "(decoder-native rate, see module docstring)"
        % (len(parts), len(scenario["parts"]), S3_MAX_PART_DT_S, n_trials, DECODE_SAMPLE_RATE_HZ))

    msg_ids = list(scenario["message_texts"].keys())
    text = scenario["message_texts"][msg_ids[0]]
    fixed = scenario["fixed"]
    true_freq_hz = float(fixed["base_freq_hz"])
    snr_db = float(fixed["snr_db"])

    rows: list[dict] = []
    for part in parts:
        true_dt = float(part["dt_s"])
        for trial in range(n_trials):
            seed = compute_seed("S3", part["part_index"], trial)
            # Mirrors _render_single's own single-signal, non-extended path exactly
            # (encode clean, then wideband AWGN -- see that function's own docstring
            # for why single-signal scenarios use wideband, not band-limited, noise),
            # parameterised to the decoder's native sample rate instead of the
            # playback rate.
            clean = encoder.encode_message(
                text, base_freq_hz=true_freq_hz, dt_s=true_dt, snr_db=None,
                sample_rate_hz=DECODE_SAMPLE_RATE_HZ, extended=False)
            samples = channel.add_noise(clean, snr_db, seed, sample_rate_hz=DECODE_SAMPLE_RATE_HZ)
            assert len(samples) == 180_000, (
                "part %d produced an unexpected buffer length %d -- scope violation, "
                "see module docstring" % (part["part_index"], len(samples)))

            results, sig, noise = _decode_and_get_terms(dec, samples)
            if not results:
                rows.append({"scenario": "S3", "part_index": part["part_index"], "trial": trial,
                              "true_dt": true_dt, "true_freq_hz": true_freq_hz, "matched": False,
                              "reason": "no_decode"})
                continue
            # Single-signal scenario: take the decode nearest the known true frequency.
            i = min(range(len(results)), key=lambda k: abs(results[k]["freq_hz"] - true_freq_hz))
            freq_err = abs(results[i]["freq_hz"] - true_freq_hz)
            recon_snr = sig[i] - noise[i] - SNR_FORMULA_OFFSET
            rows.append({
                "scenario": "S3", "part_index": part["part_index"], "trial": trial,
                "true_dt": true_dt, "true_freq_hz": true_freq_hz,
                "reported_freq_hz": results[i]["freq_hz"], "freq_err_hz": freq_err,
                "reported_snr": results[i]["snr"], "signal_db": sig[i], "local_noise_db": noise[i],
                "reconstructed_snr": recon_snr, "n_decodes_this_trial": len(results),
                "matched": freq_err <= FREQ_MATCH_TOLERANCE_HZ,
            })
    n_matched = sum(1 for r in rows if r.get("matched"))
    log("S3: %d/%d (part,trial) cells produced a matched decode" % (n_matched, len(rows)))
    return rows


def run_s8(dec: SnrTermsDecoder, log) -> list[dict]:
    from synth import channel, encoder  # noqa: PLC0415

    messages = _load_messages(SCENARIOS_DIR)
    scenario = _load_scenario(SCENARIOS_DIR / "s8-band-scene.json", messages)
    n_trials = scenario["trials"]
    signals = scenario["signals"]
    log("S8: %d trials, %d stations/trial, rendered at %d Hz (decoder-native rate, "
        "see module docstring)" % (n_trials, len(signals), DECODE_SAMPLE_RATE_HZ))

    rows: list[dict] = []
    for trial in range(n_trials):
        seed = compute_seed("S8", 0, trial)
        # Mirrors _render_band_scene's own body exactly (encode each station clean,
        # scale/sum/single-shared-floor via mix_to_shared_floor), parameterised to
        # the decoder's native sample rate instead of the playback rate.
        clean_signals = []
        snr_list: list[float] = []
        signals_meta: list[dict] = []
        for s in signals:
            clean_signals.append(encoder.encode_message(
                s["message_text"], base_freq_hz=float(s["freq_hz"]), dt_s=float(s["dt_s"]),
                snr_db=None, sample_rate_hz=DECODE_SAMPLE_RATE_HZ))
            snr_list.append(float(s["snr_db"]))
            signals_meta.append({"message_text": s["message_text"], "freq_hz": float(s["freq_hz"]),
                                  "dt_s": float(s["dt_s"]), "snr_db": float(s["snr_db"]),
                                  "station": s.get("station", "?")})
        samples = channel.mix_to_shared_floor(
            clean_signals, snr_list, seed, sample_rate_hz=DECODE_SAMPLE_RATE_HZ,
            noise_cutoff_hz=S8_NOISE_CUTOFF_HZ)
        assert len(samples) == 180_000, (
            "S8 trial %d produced an unexpected buffer length %d" % (trial, len(samples)))

        results, sig, noise = _decode_and_get_terms(dec, samples)
        matched_true_freqs: set[float] = set()
        for i, r in enumerate(results):
            # Nearest-frequency match against the 12 known truth stations. Flag (not
            # silently resolve) any decode whose two nearest truth stations are both
            # within FREQ_MATCH_TOLERANCE_HZ -- ambiguous under the near-collision pair
            # (E/F, 12 Hz apart) and the co-frequency capture pair (G/H, identical freq).
            dists = sorted(((abs(r["freq_hz"] - s["freq_hz"]), s) for s in signals_meta),
                           key=lambda t: t[0])
            best_dist, best_station = dists[0]
            ambiguous = len(dists) > 1 and dists[1][0] <= FREQ_MATCH_TOLERANCE_HZ
            recon_snr = sig[i] - noise[i] - SNR_FORMULA_OFFSET
            rows.append({
                "scenario": "S8", "trial": trial, "station": best_station["station"],
                "true_dt": float(best_station["dt_s"]), "true_freq_hz": float(best_station["freq_hz"]),
                "reported_freq_hz": r["freq_hz"], "freq_err_hz": best_dist,
                "reported_snr": r["snr"], "signal_db": sig[i], "local_noise_db": noise[i],
                "reconstructed_snr": recon_snr, "ambiguous_match": ambiguous,
                "matched": best_dist <= FREQ_MATCH_TOLERANCE_HZ,
            })
            if best_dist <= FREQ_MATCH_TOLERANCE_HZ:
                matched_true_freqs.add(best_station["freq_hz"])
    n_matched = sum(1 for r in rows if r.get("matched"))
    n_ambiguous = sum(1 for r in rows if r.get("ambiguous_match"))
    log("S8: %d decodes across %d trials, %d matched to a truth station (%d ambiguous)"
        % (len(rows), n_trials, n_matched, n_ambiguous))
    return rows


def _stratum_stats(rows: list[dict], field: str) -> dict:
    vals = [r[field] for r in rows]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "mean": float(st.mean(vals)), "median": float(st.median(vals)),
            "min": float(min(vals)), "max": float(max(vals)),
            "stdev": float(st.stdev(vals)) if len(vals) > 1 else 0.0}


def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("tasks.md 17.4 -- AC-N5, THE DT-STRATIFIED MEASUREMENT (REPORTED, NOT GATED)")
    log("=" * 90)

    dll_path = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
    log("Loading DLL: %s (pinned to Amendment 2/3, shim %d)" % (dll_path, CURRENT_SHIM_VERSION))
    try:
        dec = SnrTermsDecoder(dll_path, verify=True, expected_sha256=CURRENT_DLL_SHA256,
                               expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("DLL PIN/EXPORT CHECK FAILED: %s" % e)
        _write(out_dir, {"final": "dll_pin_fail", "error": str(e)}, log_lines)
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], dec.version))

    log("\n" + "-" * 90)
    s3_rows = run_s3(dec, log)
    log("\n" + "-" * 90)
    s8_rows = run_s8(dec, log)

    all_rows = [r for r in (s3_rows + s8_rows) if r.get("matched")]
    dt0 = [r for r in all_rows if r["true_dt"] == 0.0]
    dtpos = [r for r in all_rows if r["true_dt"] > 0.0]

    log("\n" + "=" * 90)
    log("STRATIFIED BY true_dt (matched decodes only: %d of %d total rows)"
        % (len(all_rows), len(s3_rows) + len(s8_rows)))
    log("=" * 90)

    strat = {
        "true_dt_eq_0": {
            "signal_db": _stratum_stats(dt0, "signal_db"),
            "local_noise_db": _stratum_stats(dt0, "local_noise_db"),
            "reconstructed_snr": _stratum_stats(dt0, "reconstructed_snr"),
            "reported_snr": _stratum_stats(dt0, "reported_snr"),
        },
        "true_dt_gt_0": {
            "signal_db": _stratum_stats(dtpos, "signal_db"),
            "local_noise_db": _stratum_stats(dtpos, "local_noise_db"),
            "reconstructed_snr": _stratum_stats(dtpos, "reconstructed_snr"),
            "reported_snr": _stratum_stats(dtpos, "reported_snr"),
        },
    }

    for term in ("signal_db", "local_noise_db", "reconstructed_snr", "reported_snr"):
        a = strat["true_dt_eq_0"][term]
        b = strat["true_dt_gt_0"][term]
        if a["n"] and b["n"]:
            log("  %-20s  dt=0 (n=%2d) mean=%8.3f median=%8.3f  |  dt>0 (n=%2d) mean=%8.3f median=%8.3f  |  delta(mean)=%+.3f"
                % (term, a["n"], a["mean"], a["median"], b["n"], b["mean"], b["median"], a["mean"] - b["mean"]))
        else:
            log("  %-20s  dt=0 n=%d, dt>0 n=%d -- insufficient for a delta" % (term, a["n"], b["n"]))

    log("\nBy scenario (informational, not the stratifying variable per Amendment 3 Sec.5):")
    for scen in ("S3", "S8"):
        scen_rows = [r for r in all_rows if r["scenario"] == scen]
        log("  %s: n=%d matched decodes" % (scen, len(scen_rows)))

    n_unmatched = len([r for r in (s3_rows + s8_rows) if not r.get("matched")])
    n_ambiguous = len([r for r in s8_rows if r.get("ambiguous_match")])
    if n_unmatched:
        log("\n%d row(s) failed to match a truth station within %.0f Hz -- excluded from the "
            "stratified stats above, listed in the JSON report's own rows array."
            % (n_unmatched, FREQ_MATCH_TOLERANCE_HZ))
    if n_ambiguous:
        log("%d S8 decode(s) had two truth stations within tolerance (near-collision/capture "
            "pairs) -- flagged, nearest-frequency match used, not silently resolved."
            % n_ambiguous)

    log("\nNo threshold, no pass/fail (Amendment 3 Sec.5). Do not extrapolate beyond "
        "dt_s in {0.0 .. %.1f} (S3) / {0.0, 0.5} (S8) -- HK-026." % S3_MAX_PART_DT_S)
    log("=" * 90)

    bundle = {
        "final": "measured", "strat": strat,
        "n_s3_rows": len(s3_rows), "n_s8_rows": len(s8_rows),
        "n_matched": len(all_rows), "n_unmatched": n_unmatched, "n_ambiguous": n_ambiguous,
        "rows": s3_rows + s8_rows,
    }
    _write(out_dir, bundle, log_lines)
    return 0


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "ac_n5_report.json"), bundle)
    with open(os.path.join(out_dir, "ac_n5_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
