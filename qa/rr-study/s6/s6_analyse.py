"""S6 analysis (QA tooling; spec 2026-10-13-1625 + amendment 1): one parse of both ALL.TXT slices after the last play.

    python s6_analyse.py --run-dir <dir> --scratch <dir holding wsjt-s6.txt / owsfz-s6.txt> [--daemon-log <daemon.stdout.log>]
                         [--series-label "..."]

Reads <run-dir>/s6/{s6_playlog.jsonl, s6_validity.json, s6_window.json, s6_pins.json} and the two S6 log slices (message text: they live in
the scratch dir OUTSIDE git, HK-037) and writes, into <run-dir>/s6/, aggregates only: s6_result.json, s6_section5.md, s6_section6_row.md.
Attribution is by the line's slot stamp. Validity rows (a FAIL voids the S6 block only; S1-S8 stand):
  S6-V1 corpus verified (from the player)         S6-V2 (1) every play starts within OFFSET_TOLERANCE_S of its nominal offset,
  S6-V3 warm-up decoded by both (player)                  (2) 0 decode lines stamped in a slot with no play, 0 slots with two plays
  S6-V4 plays completed = tier x 3                S6-V5 pins equal at start and end (player)
Mandatory field (Architect, amendment 1): the per-play OpenWSFZ abandonment (deadlineAbandoned) from the daemon log; the report gives S6 in
full AND over the WAVs with no abandoned play.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

import s6_play as P  # noqa: E402
import s6_stats as S  # noqa: E402

PASS_LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d) \w+\] Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(True|False) "
                       r"containedException=(True|False) fittedSignals=(\d+)")
MIN_ATTRIBUTED_SHARE = 0.9       # a DESIGN number (Architect 2026-10-13: stays 90 %): the daemon-log attribution is trusted only if this share of the residual-pass LINES in the window maps to a play slot


# ------------------------------------------------------------------ reading the logs (text stays in these functions)

def parse_log(path: str) -> dict:
    """{slot stamp: [(freq_hz, snr_db, text)]} for the FT8 rows of an ALL.TXT slice."""
    from harness.common import parse_all_txt
    out = defaultdict(list)
    if not os.path.isfile(path):
        return out
    recs, _ = parse_all_txt(__import__("pathlib").Path(path))
    for r in recs:
        out[r.utc.strftime("%y%m%d_%H%M%S")].append((float(r.freq_hz), float(r.snr_db), " ".join(r.message.split()).upper()))
    return out


def key_rows(rows: list) -> tuple:
    """-> ({key: snr} for the non-hashed rows, n_hashed). key = (text, rank among same-text rows by frequency)."""
    hashed = sum(1 for _, _, t in rows if "<" in t)
    seen, out = Counter(), {}
    for f, snr, t in sorted((r for r in rows if "<" not in r[2]), key=lambda r: (r[2], r[0])):
        out[(t, seen[t])] = snr
        seen[t] += 1
    return out, hashed


def build_obs(plays: list, wsjt: dict, owsfz: dict, abandoned: dict) -> dict:
    obs = {}
    for p in plays:
        w, hw = key_rows(wsjt.get(p["slot_stamp"], []))
        o, ho = key_rows(owsfz.get(p["slot_stamp"], []))
        d = obs.setdefault(p["wav_id"], {"band": p["band"], "sun": p["sun"], "trials": {}})
        d["trials"][p["trial"]] = {"w": w, "o": o, "hw": hw, "ho": ho, "order": p["order"], "abandoned": bool(abandoned.get(p["slot_stamp"]))}
    return obs


# ------------------------------------------------------------------ the daemon log: per-play abandonment

def read_pass_lines(path: str) -> list:
    out = []
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = PASS_LINE.match(line)
                if m:
                    h, mi, s, rd, ms, ab, ce, fs = m.groups()
                    out.append({"sod": int(h) * 3600 + int(mi) * 60 + int(s), "elapsed_ms": int(ms), "abandoned": ab == "True",
                                "exception": ce == "True", "fitted": int(fs), "residual_decodes": int(rd)})
    return out


def attribute_pass_lines(lines: list, play_slots: list, tz_offset_s: int | None = None) -> dict:
    """Pass-log lines carry a local time of day only. A residual pass starts after the slot it decodes has ended, so a line stamped T that took
    `elapsed` ms belongs to the slot  floor((T - offset - elapsed) / 15) * 15 - 15 (a pass-0 time before it is a few seconds and never a slot).
    The local-to-UTC offset is the one the SYSTEM reported at S6 start (`tz_offset_s`, from s6_tz.json); the offset that attributes the most lines
    (whole hours) is computed only as a CROSS-CHECK. Trusted only if (1) the system offset attributes at least MIN_ATTRIBUTED_SHARE of the plays and
    (2) the inferred whole-hour offset equals it; otherwise the abandonment field reads UNKNOWN (amendment 2 (b)).
    -> {"offset_h", "tz_offset_s", "inferred_offset_h", "attributed_plays", "by_slot": {slot_stamp: line}, "trusted", "reason"}"""
    slot_sod = {}
    for st in play_slots:
        d = datetime.strptime(st, "%y%m%d_%H%M%S")
        slot_sod[st] = d.hour * 3600 + d.minute * 60 + d.second
    sod_to_slot = defaultdict(list)
    for st, sod in slot_sod.items():
        sod_to_slot[sod].append(st)
    def attribute(off_s: int) -> dict:
        got = {}
        for ln in lines:
            utc_sod = (ln["sod"] - off_s) % 86400
            start = utc_sod - ln["elapsed_ms"] / 1000.0
            slot_sod_c = int(math.floor(start / 15.0) * 15 - 15) % 86400
            for st in sod_to_slot.get(slot_sod_c, []):
                got.setdefault(st, ln)
        return got

    best = (-1, None, {})
    for off in range(-14, 15):                                     # the cross-check
        got = attribute(3600 * off)
        if len(got) > best[0]:
            best = (len(got), off, got)
    inferred = best[1]
    if tz_offset_s is None:
        return {"offset_h": None, "tz_offset_s": None, "inferred_offset_h": inferred, "attributed_plays": 0, "by_slot": {}, "trusted": False,
                "reason": "no system time zone recorded at S6 start (s6_tz.json missing)"}
    got = attribute(tz_offset_s)
    n = len(got)
    # Architect, 2026-10-13 (ruling on the S6 dry run, 1b): the floor is read on the residual-pass LINES inside the S6 window, not on plays: a pass runs on only
    # some cycles, so most plays have no line, and "no line" means "no pass ran" (the play is not abandoned). Share = lines mapped to a play slot / lines whose
    # pass started inside the window of the plays. Source of the floor: the dry run (26 of 27 = 96.3 %), HK-038.
    first, last = min(slot_sod.values()), max(slot_sod.values())
    in_window = [ln for ln in lines if first <= ((ln["sod"] - tz_offset_s) % 86400) - ln["elapsed_ms"] / 1000.0 - P.SLOT_S <= last + 2 * P.SLOT_S]
    mapped_ids = {id(v) for v in got.values()}
    mapped_lines = sum(1 for ln in in_window if id(ln) in mapped_ids)
    share = mapped_lines / len(in_window) if in_window else None
    enough = share is not None and share >= MIN_ATTRIBUTED_SHARE
    agrees = tz_offset_s % 3600 == 0 and tz_offset_s // 3600 == inferred
    reason = "" if (enough and agrees) else ("%d of %d pass lines in the window map to a play slot" % (mapped_lines, len(in_window)) if not enough else
                                              "the system offset (%+d s) and the inferred offset (%+d h) disagree" % (tz_offset_s, inferred))
    return {"offset_h": tz_offset_s / 3600.0, "tz_offset_s": tz_offset_s, "inferred_offset_h": inferred, "attributed_plays": n, "by_slot": got,
            "lines_in_window": len(in_window), "lines_mapped": mapped_lines, "line_share": share, "trusted": enough and agrees, "reason": reason}


# ------------------------------------------------------------------ validity rows

def v2_rows(plays: list, warm_slots: list, wsjt: dict, owsfz: dict) -> dict:
    offs = [p["offset_s"] for p in plays]
    bad_off = [o for o in offs if abs(o - P.OFFSET_NOMINAL_S) > P.OFFSET_TOLERANCE_S]
    play_slots = [p["slot_stamp"] for p in plays]
    dup = [s for s, c in Counter(play_slots).items() if c > 1]
    ok_slots = set(play_slots) | set(warm_slots)
    stray = {a: sum(len(rows) for s, rows in log.items() if s not in ok_slots) for a, log in (("wsjtx", wsjt), ("owsfz", owsfz))}
    passed = not bad_off and not dup and stray["wsjtx"] == 0 and stray["owsfz"] == 0
    return {"result": "PASS" if passed else "FAIL",
            "offset_tolerance_s": P.OFFSET_TOLERANCE_S, "offset_nominal_s": P.OFFSET_NOMINAL_S,
            "offset_min_s": min(offs) if offs else None, "offset_max_s": max(offs) if offs else None, "plays_outside_tolerance": len(bad_off),
            "slots_with_two_plays": len(dup), "stray_lines": stray}


def decode_summary(tallies_all: list) -> dict:
    return S.pool(tallies_all)


# ------------------------------------------------------------------ report text

def pct(x, d=1):
    return "n/a" if x is None else ("%.*f %%" % (d, 100 * x))


def ci_txt(c, scale=100.0, d=1, unit=" %"):
    return "" if not c else " [%.*f, %.*f]" % (d, c[0] * scale, d, c[1] * scale) if unit == " %" else " [%.*f, %.*f]" % (d, c[0], d, c[1])


def fmt_block(res: dict, label: str) -> str:
    L = []
    A = L.append
    v = res["validity"]
    A("### S6 — Off-air WAV replay (K = 3, WSJT-X and OpenWSFZ listening to each playback at once)")
    A("")
    A("**%s.** Tier **%s**: %d WAVs x %d trials = %d plays on the 15 s grid; source = the WSJT-X-side WAV of the frozen reference-set corpus; peak-normalised to 0.9 as every scenario. "
      "No truth is assumed: the figures measure repeatability and reproducibility, not recall. Informational on its first battery." % (label, res["tier"], res["wavs"], S.K, res["plays"]))
    A("")
    A("**Validity** (a FAIL withholds this block only, the rest of the battery stands): " + "; ".join("%s %s" % (k, v[k]["result"]) for k in ("S6-V1", "S6-V2", "S6-V3", "S6-V4", "S6-V5")))
    A("")
    if res["status"] != "VALID":
        A("**S6 block WITHHELD: %s.** The rows above say which check failed; the figures below are not to be read." % res["status"])
        return "\n".join(L) + "\n"
    full = res["full"]
    A("**CPU and chain label:** %s. OpenWSFZ ran the product path with the subtraction deadline ON (per-play abandonment: %s). Load average (1 / 5 / 15 min) at the start of the plays %s and at the end %s." % (
        res["cpu_chain_label"], res["abandonment"]["summary"], res["pins"].get("start", {}).get("loadavg_1_5_15"), res["pins"].get("end", {}).get("loadavg_1_5_15")))
    ab = res["abandonment"]
    A("")
    A("*Daemon-log attribution: %s of %s residual-pass lines in the window map to a play slot = %s (floor %.0f %%, read on lines, ruled 2026-10-13; a pass runs on only some cycles, here %s of %s plays have a line, and no line means no pass ran). Play-start offset, player call time (S6-V2 a; it cannot see the sound's onset, see the onset row): min %s s, max %s s, tolerance ±%.2f s (a design number).*" % (
        ab.get("pass_lines_mapped"), ab.get("pass_lines_in_window"), pct(ab.get("pass_line_share")), 100 * MIN_ATTRIBUTED_SHARE,
        ab["plays_with_pass_line"], res["plays"], v["S6-V2"]["offset_min_s"], v["S6-V2"]["offset_max_s"], P.OFFSET_TOLERANCE_S))
    if not v["S6-V5"].get("wsjtx_exe_pinned", False):
        A("")
        A("*The WSJT-X executable was not pinned by hash on this row (no path given): only the OpenWSFZ library is pinned.*")
    A("")
    for name, blk, boot in (("All plays", full, res["bootstrap_full"]), ("Sensitivity: WAVs with no abandoned play", res.get("no_abandon"), res.get("bootstrap_no_abandon"))):
        if not blk or not blk.get("headline"):
            A("**%s:** not available (%s)." % (name, res.get("no_abandon_note", "no data")))
            A("")
            continue
        h, b = blk["headline"], boot["headline"] if boot else {}
        A("**%s** (%d WAVs, %d signals in the non-hashed universe; WAV-clustered 95 %% CIs)" % (name, h["wavs"], h["signals_in_universe"]))
        A("")
        A("| figure | WSJT-X | OpenWSFZ |")
        A("|---|---|---|")
        A("| within-appraiser consistency, own universe (decoded in all 3 of the trials it decoded in at least once) | %s%s | %s%s |" % (
            pct(h["consistency_own_wsjtx"]), ci_txt(b.get("consistency_own_wsjtx")), pct(h["consistency_own_owsfz"]), ci_txt(b.get("consistency_own_owsfz"))))
        A("| within-appraiser consistency, legacy (union universe; comparable with the 2026-06/07 rows) | %s%s | %s%s |" % (
            pct(h["consistency_legacy_wsjtx"]), ci_txt(b.get("consistency_legacy_wsjtx")), pct(h["consistency_legacy_owsfz"]), ci_txt(b.get("consistency_legacy_owsfz"))))
        A("| decodes per WAV (non-hashed, mean of 3 trials) | %.2f%s | %.2f%s |" % (
            h["decodes_per_wav_wsjtx"], ci_txt(b.get("decodes_per_wav_wsjtx"), 1, 2, ""), h["decodes_per_wav_owsfz"], ci_txt(b.get("decodes_per_wav_owsfz"), 1, 2, "")))
        A("")
        A("- **Positive agreement between the appraisers** (rows both decoded / rows either decoded, per trial): **%s%s**." % (pct(h["positive_agreement"]), ci_txt(b.get("positive_agreement"))))
        A("- Decodes per WAV, OpenWSFZ minus WSJT-X: %+.2f%s." % (h["decodes_per_wav_diff_owsfz_minus_wsjtx"], ci_txt(b.get("decodes_per_wav_diff_owsfz_minus_wsjtx"), 1, 2, "")))
        if h.get("snr_delta_mean") is not None:
            A("- SNR delta (OpenWSFZ − WSJT-X) over %d matched pairs: mean %+.2f dB%s, SD %.2f dB." % (h["snr_delta_n"], h["snr_delta_mean"], ci_txt(b.get("snr_delta_mean"), 1, 2, ""), h.get("snr_delta_sd", float("nan"))))
        k = blk["kappa"]
        A("- Cohen's κ (union universe over trials): %s %s (rows %s). *The both-negative cell exists only through trial-to-trial flicker, so κ mostly measures that; read it with the positive-agreement share.*" % (k.get("kappa"), k.get("ci95_asymptotic"), k.get("rows")))
        g = h.get("anova")
        if g and "error" not in g:
            sv, bb = g["pct_study_var"], boot["anova"] if boot else {}
            A("")
            A("**Gage R&R ANOVA on SNR** (AIAG crossed, with interaction): %d parts of %d candidate signals (those both appraisers decoded in every trial; *conditional on detection, so repeatability is understated and ndc overstated*)." % (h["anova_parts"], h["signals_in_universe"]))
            A("")
            A("| component | %StudyVar | 95 % CI |")
            A("|---|---|---|")
            for key, nm in (("EV", "repeatability (EV)"), ("AV", "appraiser (AV)"), ("INT", "part × appraiser (INT)"), ("RR", "total R&R"), ("PV", "part-to-part (PV)")):
                A("| %s | %.1f %% | %s |" % (nm, sv[key], ("[%.1f, %.1f]" % tuple(bb["pct_study_var/" + key])) if bb.get("pct_study_var/" + key) else "n/a"))
            A("")
            A("ndc %.1f%s; appraiser means %.2f / %.2f dB (WSJT-X / OpenWSFZ)." % (g["ndc"], (" [%.1f, %.1f]" % tuple(bb["ndc"])) if bb.get("ndc") else "", g["appraiser_means_db"][0], g["appraiser_means_db"][1]))
        A("")
    on = res.get("onset")
    A("")
    if on and "error" not in on and on.get("plays_with_median"):
        pm = on["per_play_median_shift_s"]
        A("**Sound onset, from WSJT-X's own DT** (DT of the replay minus DT of the live decode of the same recording, per play; the delay the replay chain added; positive = later): median of the per-play medians **%+.2f s** (P10 %+.2f, P90 %+.2f, min %+.2f, max %+.2f) over %d plays with at least %d matched rows (%d rows in all). Descriptive, no bar yet; the keep-up run read +0.1 s." % (
            pm["median"], pm["p10"], pm["p90"], pm["min"], pm["max"], on["plays_with_median"], on["min_rows_per_play"], on["rows_matched"]))
    else:
        A("**Sound onset, from WSJT-X's own DT:** not computed (%s)." % (("error " + on["error"]) if on and "error" in on else "no corpus or too few matched rows"))
    A("")
    A("**Hashed rows** (excluded from every figure above): WSJT-X %.2f and OpenWSFZ %.2f per play." % (res["hashed_per_play"]["wsjtx"], res["hashed_per_play"]["owsfz"]))
    oe, te = res["order_effect"], res["trial_effect"]
    A("")
    A("**Order effect** (Spearman, position in trial vs decodes per play): WSJT-X ρ %s (p %s), OpenWSFZ ρ %s (p %s)." % (oe["wsjtx"]["rho"], oe["wsjtx"]["p"], oe["owsfz"]["rho"], oe["owsfz"]["p"]))
    A("")
    A("**Trial-index effect** (mean non-hashed decodes per play, trial 1 / 2 / 3): WSJT-X %s; OpenWSFZ %s. Paired difference trial 3 − trial 1: WSJT-X %+.2f %s, OpenWSFZ %+.2f %s." % (
        te["wsjtx"]["mean_by_trial"], te["owsfz"]["mean_by_trial"], te["wsjtx"]["diff_trial2_minus_trial0"]["mean"], te["wsjtx"]["diff_trial2_minus_trial0"]["ci95"],
        te["owsfz"]["diff_trial2_minus_trial0"]["mean"], te["owsfz"]["diff_trial2_minus_trial0"]["ci95"]))
    if res.get("per_band"):
        A("")
        A("**Per band** (descriptive; %s):" % res["per_band_note"])
        A("")
        A("| band | WAVs | consistency WSJT-X | consistency OpenWSFZ | positive agreement | decodes/WAV WSJT-X | decodes/WAV OpenWSFZ |")
        A("|---|---|---|---|---|---|---|")
        for band, r in res["per_band"].items():
            A("| %s | %d | %s | %s | %s | %.2f | %.2f |" % (band, r["wavs"], pct(r["consistency_own_wsjtx"]), pct(r["consistency_own_owsfz"]), pct(r["positive_agreement"]), r["decodes_per_wav_wsjtx"], r["decodes_per_wav_owsfz"]))
    A("")
    if res.get("figure"):
        A("")
        A("![S6 six-panel figure](s6/%s)" % res["figure"])
        A("")
    A("Counts by sun state of the WAVs played: %s. Per-WAV gain applied before playback is in `s6-wavlist.json`." % res["sun_counts"])
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main

def describe_chain(run_dir: str) -> str:
    """The CPU / thread label of the block, from the RUN'S OWN arm_config.json and /proc/cpuinfo (never typed): the Architect's rule (2026-10-13) is that the
    dry run says 'subtractionMaxThreads N (station value, not auto)' and claims nothing about the default set-up."""
    cpus = os.cpu_count() or 0
    model = ""
    try:
        with open("/proc/cpuinfo", encoding="utf8", errors="replace") as fh:
            for line in fh:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    threads = None
    try:
        threads = json.load(open(os.path.join(run_dir, "arm_config.json"), encoding="utf8"))["daemon"]["decoder_readback"].get("subtractionMaxThreads")
    except (OSError, KeyError, ValueError, TypeError):
        pass
    auto = max(1, cpus - 2) if cpus else None
    if threads is None:
        t = "subtractionMaxThreads NOT READ BACK"
    elif threads == 0:
        t = "subtractionMaxThreads 0 (auto = %s on %s CPUs)" % (auto, cpus)
    else:
        t = "subtractionMaxThreads %s on %s CPUs (as configured; auto would give %s)%s" % (threads, cpus, auto, " (station value, not auto)" if threads != auto else " (= auto)")
    return "%s, subtraction deadline ON, %s, WSJT-X decoding on the same CPUs; a drop on the capture path would be SILENT (no counter or log line exists)" % (model or "host CPU unknown", t)


def run(run_dir: str, scratch: str, daemon_log: str | None, series_label: str, cpu_chain_label: str | None = None, n_boot: int = S.BOOT_N,
        corpus: str | None = None, wavlist_path: str | None = None) -> dict:
    s6 = os.path.join(run_dir, "s6")
    rows = [json.loads(x) for x in open(os.path.join(s6, "s6_playlog.jsonl"), encoding="utf8")]
    plays = [r for r in rows if r["kind"] == "play"]
    warm_slots = [r["slot_stamp"] for r in rows if r["kind"] == "warmup"]
    vp = os.path.join(s6, "s6_validity.json")
    # the player writes s6_validity.json on every exit it controls; a killed or crashed player leaves none: the block is VOID, not a crash
    validity = json.load(open(vp, encoding="utf8")) if os.path.isfile(vp) else {"tier": "unknown", "plays_planned": 0, "player_did_not_finish": True}
    window = json.load(open(os.path.join(s6, "s6_window.json"), encoding="utf8")) if os.path.isfile(os.path.join(s6, "s6_window.json")) else {}
    slices_present = os.path.isfile(os.path.join(scratch, "wsjt-s6.txt")) and os.path.isfile(os.path.join(scratch, "owsfz-s6.txt"))
    wsjt, owsfz = parse_log(os.path.join(scratch, "wsjt-s6.txt")), parse_log(os.path.join(scratch, "owsfz-s6.txt"))
    pins_file = os.path.join(s6, "s6_pins.json")
    pins = json.load(open(pins_file, encoding="utf8")) if os.path.isfile(pins_file) else {}
    cpu_chain_label = cpu_chain_label or describe_chain(run_dir)
    tier = validity["tier"]
    expected = validity["plays_planned"]
    v = {"S6-V1": validity.get("S6-V1", {"result": "MISSING"}), "S6-V3": validity.get("S6-V3", {"result": "MISSING"}), "S6-V5": validity.get("S6-V5", {"result": "MISSING"})}
    v["S6-V2"] = v2_rows(plays, warm_slots, wsjt, owsfz)
    # a block built on NO log lines is not a result: the split step may have failed (the first dry run's KeyError left the slices missing and the block read VALID)
    if not slices_present or sum(len(r) for r in wsjt.values()) + sum(len(r) for r in owsfz.values()) == 0:
        v["S6-V2"]["result"] = "FAIL"
        v["S6-V2"]["logs"] = "S6 log slices missing" if not slices_present else "both S6 log slices are empty"
    v["S6-V4"] = {"result": "PASS" if (len(plays) == expected and not validity.get("player_did_not_finish")) else "FAIL", "plays": len(plays), "expected": expected,
                  **({"note": "the player did not finish (no s6_validity.json)"} if validity.get("player_did_not_finish") else {})}
    ok = all(v[k]["result"] == "PASS" for k in v)
    status = "VALID" if ok else "VOID: " + ", ".join("%s %s" % (k, v[k]["result"]) for k in v if v[k]["result"] != "PASS")
    res = {"tier": tier, "status": status, "validity": v, "plays": len(plays), "wavs": len({p["wav_id"] for p in plays}), "series_label": series_label,
           "cpu_chain_label": cpu_chain_label, "window": window, "pins": pins}
    if ok:
        tzp = os.path.join(s6, "s6_tz.json")
        tz_s = json.load(open(tzp, encoding="utf8"))["gmtoff_s"] if os.path.isfile(tzp) else None
        pl = (attribute_pass_lines(read_pass_lines(daemon_log), [p["slot_stamp"] for p in plays], tz_s) if daemon_log
              else {"trusted": False, "by_slot": {}, "attributed_plays": 0, "offset_h": None, "inferred_offset_h": None, "reason": "no daemon log"})
        ab = {s: ln["abandoned"] for s, ln in pl["by_slot"].items()} if pl["trusted"] else {}
        n_ab = sum(1 for x in ab.values() if x)
        res["abandonment"] = {"daemon_log_attributed": pl["trusted"], "plays_with_pass_line": pl["attributed_plays"], "pass_lines_in_window": pl.get("lines_in_window"), "pass_lines_mapped": pl.get("lines_mapped"),
                              "pass_line_share": pl.get("line_share"), "plays_abandoned": n_ab if pl["trusted"] else None,
                              "tz_offset_h_system": pl["offset_h"], "tz_offset_h_inferred": pl.get("inferred_offset_h"), "not_trusted_because": pl.get("reason", ""),
                              "elapsed_ms_median": float(np.median([ln["elapsed_ms"] for ln in pl["by_slot"].values()])) if pl["trusted"] and pl["by_slot"] else None,
                              "fitted_signals_median": float(np.median([ln["fitted"] for ln in pl["by_slot"].values()])) if pl["trusted"] and pl["by_slot"] else None}
        res["abandonment"]["summary"] = ("%d of %d plays abandoned" % (n_ab, len(plays))) if pl["trusted"] else "UNKNOWN (%s): no sensitivity is given" % (pl.get("reason") or "the log could not be matched to the plays")
        obs = build_obs(plays, wsjt, owsfz, ab)
        tallies_by_wav = {w: S.wav_tally(o["trials"]) for w, o in obs.items()}
        tall = [tallies_by_wav[w] for w in sorted(tallies_by_wav)]
        res["full"] = {"headline": S.pool(tall), "kappa": S.kappa_legacy(tall)}
        res["bootstrap_full"] = S.bootstrap(tall, n_boot)
        if pl["trusted"]:
            keep = [w for w in sorted(obs) if not any(t["abandoned"] for t in obs[w]["trials"].values())]
            res["no_abandon_wavs"] = {"kept": len(keep), "of": len(obs)}
            if len(keep) >= 8:
                tk = [tallies_by_wav[w] for w in keep]
                res["no_abandon"] = {"headline": S.pool(tk), "kappa": S.kappa_legacy(tk)}
                res["bootstrap_no_abandon"] = S.bootstrap(tk, n_boot)
            else:
                res["no_abandon_note"] = "only %d WAVs have no abandoned play" % len(keep)
        else:
            res["no_abandon_note"] = res["abandonment"]["summary"]
        res["hashed_per_play"] = {"wsjtx": sum(t["hw"] for o in obs.values() for t in o["trials"].values()) / max(1, len(plays)),
                                  "owsfz": sum(t["ho"] for o in obs.values() for t in o["trials"].values()) / max(1, len(plays))}
        try:
            import s6_figure
            res["figure"] = s6_figure.make_figure(os.path.join(s6, "s6_figure.png"), obs, tall, res["full"]["headline"], res["bootstrap_full"])
        except Exception as exc:                                            # a figure problem never costs the numbers
            res["figure"] = None
            res["figure_error"] = type(exc).__name__
        res["onset"] = None
        if corpus and wavlist_path and os.path.isfile(wavlist_path) and slices_present:
            try:                                                    # the onset row (Architect 2026-10-13, 1a): WSJT-X's DT replay minus live, per play; descriptive
                import s6_onset
                res["onset"] = s6_onset.onset_row(plays, os.path.join(scratch, "wsjt-s6.txt"), corpus, json.load(open(wavlist_path, encoding="utf8")))
            except Exception as exc:                                # never costs the other numbers
                res["onset"] = {"error": type(exc).__name__}
        res["order_effect"], res["trial_effect"] = S.order_effect(obs), S.trial_effect(obs, n_boot)
        res["sun_counts"] = dict(Counter(o["sun"] for o in obs.values()))
        if tier in ("standard", "extended"):
            res["per_band_note"] = "%d WAVs per band at the %s tier: wide intervals, no comparison between bands" % (len(obs) // 4, tier)
            res["per_band"] = {}
            for band in ("17m", "20m", "40m", "80m"):
                tb = [tallies_by_wav[w] for w in sorted(obs) if obs[w]["band"] == band]
                if tb:
                    res["per_band"][band] = S.pool(tb)
        else:
            res["per_band_note"] = "not given at the quick tier: too small"
    with open(os.path.join(s6, "s6_result.json"), "w", encoding="utf8", newline="\n") as fh:
        json.dump(res, fh, indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else (o.tolist() if hasattr(o, "tolist") else str(o)))
    with open(os.path.join(s6, "s6_section5.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(fmt_block(res, series_label))
    row = "| S6 | %s | tier %s | %s | %s |" % (status, tier, series_label, (pct(res["full"]["headline"].get("positive_agreement")) + " positive agreement") if ok else "withheld")
    with open(os.path.join(s6, "s6_section6_row.md"), "w", encoding="utf8", newline="\n") as fh:
        fh.write(row + "\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--daemon-log", default=None)
    ap.add_argument("--series-label", default="First S6 row of the LINUX series")
    ap.add_argument("--corpus", default=None, help="the frozen corpus (live WSJT-X ALL.TXT of the source runs) for the onset row")
    ap.add_argument("--wavlist", default=os.path.join(HERE, "s6-wavlist.json"))
    ap.add_argument("--cpu-chain-label", default=None, help="default: built from the run's own arm_config.json and /proc/cpuinfo (describe_chain)")
    a = ap.parse_args()
    r = run(a.run_dir, a.scratch, a.daemon_log, a.series_label, a.cpu_chain_label, corpus=a.corpus, wavlist_path=a.wavlist)
    print("S6 analysis:", r["status"], "tier", r["tier"], "plays", r["plays"])
    sys.exit(0)


if __name__ == "__main__":
    main()
