"""S6 playback step (QA tooling; spec 2026-10-13-1625 + amendment 1): off-air WAVs, K = 3, both appraisers listening at once.

    python s6_play.py --run-dir <dir> --tier standard --corpus <rr-s6-refset-corpus> --device "RR-ALSA" \\
        --wsjt-all-txt <p> --owsfz-all-txt <p> [--ows-lib <libft8>] [--wsjtx-exe <p>] [--dry-run]

What it does, in order (any failure stops S6 ONLY; the exit code says which row failed):
  S6-V1  the frozen corpus verifies and every WAV of the tier is the one in s6-wavlist.json
  S6-V5  (start) SHA-256 of the OpenWSFZ native library and of the WSJT-X executable
  S6-V3  mechanical warm-up: one synthetic Q-prefix cycle; both ALL.TXT must gain >= 1 line stamped with that slot (3 attempts)
  plays  K = 3 trials; each trial is a seeded shuffle of the tier's WAVs (seed = sha256("S6,<trial>") mod 2^31, the corpus_replay
         rule); one WAV per 15 s slot, consecutive slots; the next WAV is rendered while the current one plays
  S6-V5  (end) the same hashes again
Writes <run-dir>/s6/s6_playlog.jsonl (one row per play, flushed as it goes), s6_pins.json, s6_window.json, s6_validity.json.
There is NO per-cycle snapshot of either ALL.TXT and no settle sleep: the analysis parses both logs once, after the last play,
and attributes every line by its slot stamp (the way the S1-S8 matcher does). Stdout carries counts only (NFR-021): the audio is real
off-air material, the logs it produces hold real callsigns, and neither enters the run directory (see s6_split.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RR = os.path.dirname(HERE)
for p in (HERE, RR):
    if p not in sys.path:
        sys.path.insert(0, p)

import s6_design as D  # noqa: E402

SLOT_S = 15
PREWARM_S = 0.5                 # = harness.run_scenario._CYCLE_PREWARM_S (asserted by the unit test)
OFFSET_NOMINAL_S = -PREWARM_S   # a play starts PREWARM_S before its slot boundary
OFFSET_TOLERANCE_S = 0.25       # S6-V2 (1): |start - boundary - nominal| <= this. A DESIGN number (half the prewarm), not measured;
                                # the dry run reports the observed distribution and the Architect re-sets the bar before any real row.
LEAD_S = 45                     # first boundary at least this far ahead (the first render is done by then)
WARMUP_SETTLE_S = 22.0          # after the warm-up slot's end: both decoders have written their lines
WARMUP_ATTEMPTS = 3
FINAL_WAIT_S = 30.0             # after the last slot's end: the last decodes land
EXIT_V1, EXIT_V3, EXIT_V5, EXIT_OTHER = 2, 4, 5, 6


def trial_seed(trial: int) -> int:
    return int(hashlib.sha256(("S6,%d" % trial).encode("utf-8")).hexdigest(), 16) % (2 ** 31)


def make_schedule(items: list, k_trials: int = D.K_TRIALS) -> list:
    """[(play_index, trial, order_in_trial, item), ...]: every item exactly once per trial, each trial a seeded shuffle."""
    out, n = [], 0
    for t in range(k_trials):
        order = list(range(len(items)))
        random.Random(trial_seed(t)).shuffle(order)
        for o, i in enumerate(order):
            out.append((n, t, o, items[i]))
            n += 1
    return out


def slot_stamp(boundary_ts: float) -> str:
    return datetime.fromtimestamp(boundary_ts, tz=timezone.utc).strftime("%y%m%d_%H%M%S")


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def next_boundary(now: float) -> float:
    return float(int(now) // SLOT_S * SLOT_S + SLOT_S)


def lines_for_slot(path: str, pos: int, stamp: str) -> int:
    """Lines appended to an ALL.TXT since byte position `pos` whose first token is the slot stamp. A count only."""
    if not os.path.isfile(path):
        return 0
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(pos)
        for line in fh:
            t = line.split(None, 1)
            if t and t[0] == stamp:
                n += 1
    return n


def file_size(path: str) -> int:
    return os.path.getsize(path) if os.path.isfile(path) else 0


def sha_or_none(path):
    return D.sha256_file(path) if path and os.path.isfile(path) else None


def pins(a) -> dict:
    return {"ows_lib": a.ows_lib, "ows_lib_sha256": sha_or_none(a.ows_lib),
            "wsjtx_exe": a.wsjtx_exe, "wsjtx_exe_sha256": sha_or_none(a.wsjtx_exe)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--tier", default="standard", choices=sorted(D.TIERS))
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--wavlist", default=os.path.join(HERE, "s6-wavlist.json"))
    ap.add_argument("--device", default="CABLE Input")
    ap.add_argument("--wsjt-all-txt", required=True)
    ap.add_argument("--owsfz-all-txt", required=True)
    ap.add_argument("--ows-lib", default=None, help="the OpenWSFZ native library the daemon loaded (hashed at start and end)")
    ap.add_argument("--wsjtx-exe", default=None, help="the WSJT-X executable (hashed at start and end)")
    ap.add_argument("--dry-run", action="store_true", help="no sound, no waiting: a fake clock (tests and desk checks only)")
    ap.add_argument("--skip-verify", action="store_true", help="DEV ONLY: skips the corpus verification; S6-V1 is then recorded as SKIPPED = not PASS")
    a = ap.parse_args()

    out = os.path.join(a.run_dir, "s6")
    os.makedirs(out, exist_ok=True)
    wl = json.load(open(a.wavlist, encoding="utf8"))
    items = D.tier_items(wl, a.tier)
    validity: dict = {"tier": a.tier, "plays_planned": len(items) * D.K_TRIALS}

    def save_validity(exit_code: int, note: str = "") -> None:
        validity["exit_code"], validity["note"] = exit_code, note
        with open(os.path.join(out, "s6_validity.json"), "w", encoding="utf8", newline="\n") as fh:
            json.dump(validity, fh, indent=1)

    # --- S6-V1
    if a.skip_verify:
        validity["S6-V1"] = {"result": "SKIPPED", "problems": ["--skip-verify"]}
    else:
        ok, problems = D.verify(a.corpus, a.wavlist, a.tier)
        validity["S6-V1"] = {"result": "PASS" if ok else "FAIL", "problems": problems[:10]}
        if not ok:
            print("S6-V1 FAIL: %d problems; S6 stops (S1-S8 stand)" % len(problems), flush=True)
            save_validity(EXIT_V1, "corpus or wavlist verification failed")
            sys.exit(EXIT_V1)
    print("S6-V1 %s; tier %s: %d WAVs x %d trials = %d plays" % (validity["S6-V1"]["result"], a.tier, len(items), D.K_TRIALS, len(items) * D.K_TRIALS), flush=True)

    pins_start = pins(a)

    sd = dev = None
    if not a.dry_run:
        from harness import run_scenario as rs
        assert rs._CYCLE_PREWARM_S == PREWARM_S
        import sounddevice as sd  # noqa: F811
        dev = rs._select_device(a.device)

    # fake clock for --dry-run
    clock = {"t": time.time()}

    def now() -> float:
        return clock["t"] if a.dry_run else time.time()

    def sleep_until(t: float) -> None:
        if a.dry_run:
            clock["t"] = max(clock["t"], t)
        else:
            d = t - time.time()
            if d > 0:
                time.sleep(d)

    def play(buf) -> float:
        started = now()
        if not a.dry_run:
            sd.play(buf, samplerate=D.PLAY_FS, device=dev, blocking=False)
        return started

    def wait_end() -> None:
        if not a.dry_run:
            sd.wait()

    # --- S6-V3 mechanical warm-up
    sys.path.insert(0, RR)
    from harness.warmup import _render_warmup_cycle  # noqa: E402
    warm = _render_warmup_cycle() if not a.dry_run else None
    warm_rows, v3_ok, next_b = [], False, next_boundary(now() + LEAD_S)
    for attempt in range(1, WARMUP_ATTEMPTS + 1):
        wpos, opos = file_size(a.wsjt_all_txt), file_size(a.owsfz_all_txt)
        b = next_b
        sleep_until(b - PREWARM_S)
        started = play(warm)
        wait_end()
        stamp = slot_stamp(b)
        sleep_until(b + SLOT_S + WARMUP_SETTLE_S)
        cw, co = (1, 1) if a.dry_run else (lines_for_slot(a.wsjt_all_txt, wpos, stamp), lines_for_slot(a.owsfz_all_txt, opos, stamp))
        warm_rows.append({"kind": "warmup", "attempt": attempt, "boundary_utc": iso(b), "slot_stamp": stamp,
                          "offset_s": round(started - b, 3), "wsjtx_lines": cw, "owsfz_lines": co})
        print("S6 warm-up attempt %d slot %s: WSJT-X %d line(s), OpenWSFZ %d line(s)" % (attempt, stamp, cw, co), flush=True)
        next_b = next_boundary(now() + 1)
        if cw >= 1 and co >= 1:
            v3_ok = True
            break
    validity["S6-V3"] = {"result": "PASS" if v3_ok else "FAIL", "attempts": warm_rows}
    if not v3_ok:
        save_validity(EXIT_V3, "warm-up cycle not decoded by both appraisers")
        print("S6-V3 FAIL: warm-up not decoded by both; S6 stops (S1-S8 stand)", flush=True)
        sys.exit(EXIT_V3)

    # --- the plays
    sched = make_schedule(items)
    logp = os.path.join(out, "s6_playlog.jsonl")
    fh = open(logp, "w", encoding="utf8", newline="\n")
    for w in warm_rows:
        fh.write(json.dumps(w) + "\n")
    fh.flush()

    def render(item):
        s16 = D.read_wav_int16(D.wav_path(a.corpus, item["run"], item["stamp"])) if not a.dry_run else None
        return D.render_48k(s16)[0] if s16 is not None else None

    first_b = next_boundary(now() + 20)
    buf = render(sched[0][3])
    b, slips = first_b, 0
    for (n, trial, order, item) in sched:
        # a boundary already too close or past (a slow render, a stalled system): move to the next free slot, and say so
        while b - PREWARM_S <= now():
            b += SLOT_S
            slips += 1
        sleep_until(b - PREWARM_S)
        started = play(buf)
        nxt = sched[n + 1][3] if n + 1 < len(sched) else None
        buf = render(nxt) if nxt else None          # render the next WAV while this one plays
        wait_end()
        row = {"kind": "play", "play_index": n, "trial": trial, "order": order, "wav_id": item["id"], "band": item["band"], "sun": item["sun"],
               "gain": item["gain"], "boundary_utc": iso(b), "slot_stamp": slot_stamp(b), "offset_s": round(started - b, 3), "slips_so_far": slips}
        fh.write(json.dumps(row) + "\n")
        fh.flush()
        if (n + 1) % 20 == 0 or n + 1 == len(sched):
            print("S6 play %d/%d slot %s" % (n + 1, len(sched), row["slot_stamp"]), flush=True)
        b += SLOT_S
    fh.close()
    last_b = b - SLOT_S
    sleep_until(last_b + SLOT_S + FINAL_WAIT_S)

    pins_end = pins(a)
    equal = pins_start == pins_end and (pins_start["ows_lib_sha256"] is not None)
    validity["S6-V5"] = {"result": "PASS" if equal else ("FAIL" if pins_start["ows_lib_sha256"] is not None else "NOT PINNED"),
                         "start": pins_start, "end": pins_end}
    with open(os.path.join(out, "s6_pins.json"), "w", encoding="utf8", newline="\n") as f2:
        json.dump({"start": pins_start, "end": pins_end}, f2, indent=1)
    with open(os.path.join(out, "s6_window.json"), "w", encoding="utf8", newline="\n") as f3:
        json.dump({"tier": a.tier, "wavlist_sha256": D.sha256_file(a.wavlist), "wavlist_seed": wl["seed"], "k_trials": D.K_TRIALS,
                   "first_warmup_slot": warm_rows[0]["slot_stamp"], "first_play_slot": slot_stamp(first_b), "last_play_slot": slot_stamp(last_b),
                   "plays": len(sched), "slips": slips, "end_utc": iso(now())}, f3, indent=1)
    validity["S6-V4-plays_completed"] = len(sched)
    save_validity(0 if validity["S6-V5"]["result"] == "PASS" else EXIT_V5)
    print("S6 playback done: %d plays, %d slip(s); V5 %s" % (len(sched), slips, validity["S6-V5"]["result"]), flush=True)
    sys.exit(0 if validity["S6-V5"]["result"] == "PASS" else EXIT_V5)


if __name__ == "__main__":
    main()
