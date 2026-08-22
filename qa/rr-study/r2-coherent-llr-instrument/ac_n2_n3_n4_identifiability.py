#!/usr/bin/env python3
"""tasks.md Sec.17.1-17.3 -- AC-N2 (IDENTIFIABILITY), AC-N3 (COUNT CONTRACT),
AC-N4 (CAPACITY), all three GATING, for ft8_get_last_snr_terms (Amendment 2,
corrected by Amendment 3, r2-coherent-llr-instrument, FT8_SHIM_VERSION 20260045).

Runs against the SAME real-corpus window r0_ac1_ac2_replay.py already uses for AC-N1
(artefacts/20260808_live_run_0016-8080/wsjt-x/wav, WINDOW_20M, 2529 files available --
reused verbatim via p23_common's in_window_files/read_wav/normalise_rms, HK-018), so
this run needs no live capture and no hardware.

AC-N2: over every decode in >=100 cycles, abs((signal_db - local_noise_db - 26.5) -
       snr) <= 0.5 + 1e-3. Any violation -> STOP.
AC-N3: returned count == ft8_decode_all's own returned count, every cycle. Mismatch
       -> STOP.
AC-N4: on the first cycle with count >= 3 encountered in the same pass (asserted
       BEFORE the case is evaluated, per the task's own text), exercise capacity
       0 / 1 / (count-1) / negative / both-NULL. Writes exactly `capacity` entries
       (verified by a canary buffer, not merely trusting the trimmed return), returns
       `capacity`; negative capacity returns -1; both-NULL writes nothing and returns
       the count it would have written.
"""
from __future__ import annotations

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, HERE)

import p23_common as P  # noqa: E402 -- WAV corpus helpers only (in_window_files/read_wav/normalise_rms)
from snr_terms_ctypes import SnrTermsDecoder, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

N_CYCLES = 250          # matches AC-N1's own 250-cycle standard on the same corpus
AC_N2_TOL = 0.5 + 1e-3  # Amendment 3 Sec.4(a) -- +1e-3 is a float-representation
                        # allowance for the int-rounding quantum, not a loosened bar
SNR_FORMULA_OFFSET = 26.5


def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("tasks.md 17.1-17.3 -- AC-N2/AC-N3/AC-N4 (all GATING)")
    log("=" * 90)

    dll_path = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
    log("Loading DLL: %s (pinned to Amendment 2/3, shim %d)" % (dll_path, CURRENT_SHIM_VERSION))
    try:
        dec = SnrTermsDecoder(dll_path, verify=True, expected_sha256=CURRENT_DLL_SHA256,
                               expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("DLL PIN/EXPORT CHECK FAILED: %s" % e)
        log("STOP. No verdict.")
        _write(out_dir, {"final": "dll_pin_fail", "error": str(e)}, log_lines)
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], dec.version))

    files = P.in_window_files()
    subset = files[:N_CYCLES]
    log("Corpus: WINDOW_20M, %d/%d cycles available, using first %d (%s .. %s)"
        % (len(subset), len(files), len(subset), subset[0][0], subset[-1][0]))

    n_cycles_run = 0
    n_cycles_av = 0
    n_cycles_zero_decode = 0
    n_decodes_total = 0
    n2_max_abs_err = 0.0
    n2_violations: list[dict] = []
    n3_mismatches: list[dict] = []
    ac_n4_result: "dict | None" = None

    for ts, path in subset:
        pcm = P.read_wav(path)
        pcm = P.normalise_rms(pcm, P.PROD_TARGET_RMS)

        results = dec.decode_all(pcm)
        if results is None:
            n_cycles_av += 1
            continue
        n_cycles_run += 1
        n_expected = len(results)
        if n_expected == 0:
            n_cycles_zero_decode += 1

        n_got, sig, noise = dec.get_last_snr_terms(capacity=300)

        # ── AC-N3: count contract ────────────────────────────────────────────
        if n_got != n_expected:
            n3_mismatches.append({"ts": ts, "n_expected": n_expected, "n_got": n_got})
            log("\nAC-N3 VIOLATION at ts=%s: ft8_get_last_snr_terms returned %d, "
                "ft8_decode_all returned %d -- STOP." % (ts, n_got, n_expected))
            _write(out_dir, {
                "final": "AC-N3_FIRES", "ts": ts, "n_expected": n_expected, "n_got": n_got,
                "n_cycles_checked_before_failure": n_cycles_run,
            }, log_lines)
            return 3

        # ── AC-N2: identifiability ───────────────────────────────────────────
        for i in range(n_expected):
            recon = sig[i] - noise[i] - SNR_FORMULA_OFFSET
            err = abs(recon - results[i]["snr"])
            n2_max_abs_err = max(n2_max_abs_err, err)
            n_decodes_total += 1
            if err > AC_N2_TOL:
                n2_violations.append({
                    "ts": ts, "i": i, "signal_db": sig[i], "local_noise_db": noise[i],
                    "reconstructed_snr": recon, "reported_snr": results[i]["snr"], "err": err,
                })
                log("\nAC-N2 VIOLATION at ts=%s decode[%d]: |%.4f - %d| = %.4f > %.4f -- STOP."
                    % (ts, i, recon, results[i]["snr"], err, AC_N2_TOL))
                _write(out_dir, {
                    "final": "AC-N2_FIRES", "violation": n2_violations[-1],
                    "n_cycles_checked_before_failure": n_cycles_run,
                    "n_decodes_checked_before_failure": n_decodes_total,
                }, log_lines)
                return 4

        # ── AC-N4: capacity contract, first cycle with count >= 3 ────────────
        if ac_n4_result is None and n_expected >= 3:
            log("\nAC-N4: first count>=3 cycle found at ts=%s (count=%d) -- running capacity cases."
                % (ts, n_expected))
            ac_n4_result = _run_ac_n4(dec, ts, n_expected, log)

    log("\n" + "-" * 90)
    log("AC-N2/AC-N3 summary: %d cycles decoded (%d AV-skipped, %d zero-decode), "
        "%d total decodes checked, max |reconstructed - reported| = %.5f dB (tol %.4f)"
        % (n_cycles_run, n_cycles_av, n_cycles_zero_decode, n_decodes_total,
           n2_max_abs_err, AC_N2_TOL))
    ac_n2_pass = len(n2_violations) == 0
    ac_n3_pass = len(n3_mismatches) == 0
    log("AC-N2: %s (0 violations across %d decodes)" % ("PASS" if ac_n2_pass else "FAIL", n_decodes_total))
    log("AC-N3: %s (0 mismatches across %d cycles)" % ("PASS" if ac_n3_pass else "FAIL", n_cycles_run))

    if ac_n4_result is None:
        log("\nAC-N4: NO CYCLE WITH count>=3 FOUND in %d cycles -- report and do not fabricate "
            "a degenerate-case result. Would need a denser scenario/re-run on a larger window."
            % n_cycles_run)
        ac_n4_pass = None
    else:
        ac_n4_pass = ac_n4_result["passed"]
        log("AC-N4: %s (ts=%s, count=%d)"
            % ("PASS" if ac_n4_pass else "FAIL", ac_n4_result["ts"], ac_n4_result["count"]))

    bundle = {
        "final": "gates_evaluated",
        "n_cycles_run": n_cycles_run, "n_cycles_av": n_cycles_av,
        "n_cycles_zero_decode": n_cycles_zero_decode, "n_decodes_total": n_decodes_total,
        "n2_max_abs_err": n2_max_abs_err, "ac_n2_pass": ac_n2_pass, "ac_n2_tol": AC_N2_TOL,
        "ac_n3_pass": ac_n3_pass,
        "ac_n4": ac_n4_result, "ac_n4_pass": ac_n4_pass,
        "window": {"first_ts": subset[0][0], "last_ts": subset[-1][0], "n_cycles_offered": len(subset)},
    }
    _write(out_dir, bundle, log_lines)
    log("=" * 90)
    return 0


def _run_ac_n4(dec: SnrTermsDecoder, ts: str, count: int, log) -> dict:
    """Runs the five AC-N4 capacity cases against the TLS state left by the decode_all
    call that just produced `count` decodes (no further decode_all call happens between
    here and the caller resuming its loop -- read-only, non-mutating getter)."""
    cases: dict[str, dict] = {}
    all_pass = True

    def _no_overrun_check(capacity: int) -> bool:
        """Bypasses SnrTermsDecoder's wrapper: pre-fills a canary buffer well beyond
        `capacity` with a sentinel, calls the raw binding directly, and confirms nothing
        past index `capacity` was touched -- the direct proof 'writes exactly capacity
        entries' asks for, not merely trusting the trimmed-to-n return."""
        SENTINEL = -999.0
        buf_size = capacity + 50 if capacity > 0 else 50
        sig_buf = (ctypes.c_float * buf_size)(*([SENTINEL] * buf_size))
        noise_buf = (ctypes.c_float * buf_size)(*([SENTINEL] * buf_size))
        n = dec.dll.ft8_get_last_snr_terms(sig_buf, noise_buf, capacity)
        untouched = all(sig_buf[j] == SENTINEL and noise_buf[j] == SENTINEL
                         for j in range(capacity, buf_size))
        return n, untouched

    # capacity = 0
    n0, sig0, noise0 = dec.get_last_snr_terms(capacity=0)
    n0_over, no_overrun_0 = _no_overrun_check(0)
    ok0 = (n0 == 0 and sig0 == [] and noise0 == [] and no_overrun_0)
    cases["capacity_0"] = {"n": n0, "sig_len": len(sig0), "noise_len": len(noise0),
                            "no_overrun": no_overrun_0, "passed": ok0}
    all_pass &= ok0

    # capacity = 1
    n1, sig1, noise1 = dec.get_last_snr_terms(capacity=1)
    _, no_overrun_1 = _no_overrun_check(1)
    ok1 = (n1 == 1 and len(sig1) == 1 and len(noise1) == 1 and no_overrun_1)
    cases["capacity_1"] = {"n": n1, "sig_len": len(sig1), "noise_len": len(noise1),
                            "no_overrun": no_overrun_1, "passed": ok1}
    all_pass &= ok1

    # capacity = count - 1 (degenerate below count>=3, guarded by the caller's own gate)
    cap_cm1 = count - 1
    n_cm1, sig_cm1, noise_cm1 = dec.get_last_snr_terms(capacity=cap_cm1)
    _, no_overrun_cm1 = _no_overrun_check(cap_cm1)
    ok_cm1 = (n_cm1 == cap_cm1 and len(sig_cm1) == cap_cm1 and len(noise_cm1) == cap_cm1
              and no_overrun_cm1)
    cases["capacity_count_minus_1"] = {"capacity": cap_cm1, "n": n_cm1, "sig_len": len(sig_cm1),
                                        "noise_len": len(noise_cm1), "no_overrun": no_overrun_cm1,
                                        "passed": ok_cm1}
    all_pass &= ok_cm1

    # negative capacity
    n_neg, sig_neg, noise_neg = dec.get_last_snr_terms(capacity=-5)
    ok_neg = (n_neg == -1 and sig_neg is None and noise_neg is None)
    cases["negative_capacity"] = {"n": n_neg, "passed": ok_neg}
    all_pass &= ok_neg

    # both-NULL, capacity >= count -> writes nothing (want_signal/want_noise False means
    # NULL is passed), returns the count it would have written
    n_null, sig_null, noise_null = dec.get_last_snr_terms(capacity=count + 10,
                                                            want_signal=False, want_noise=False)
    ok_null = (n_null == count and sig_null is None and noise_null is None)
    cases["both_null"] = {"n": n_null, "passed": ok_null}
    all_pass &= ok_null

    for name, c in cases.items():
        log("  %-24s -> %s  %s" % (name, "PASS" if c["passed"] else "FAIL", c))

    return {"ts": ts, "count": count, "cases": cases, "passed": bool(all_pass)}


def _write(out_dir: str, bundle: dict, log_lines: list[str]) -> None:
    P.write_json(os.path.join(out_dir, "ac_n2_n3_n4_report.json"), bundle)
    with open(os.path.join(out_dir, "ac_n2_n3_n4_run.log"), "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
