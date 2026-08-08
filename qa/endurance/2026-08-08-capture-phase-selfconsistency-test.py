#!/usr/bin/env python3
"""Does OpenWSFZ's self-consistency depend on the two instances' capture START PHASE?

Registered 2026-08-08 13:07Z, BEFORE the intervention, and before any post-restart data
existed. Thresholds below are fixed and must not be edited after the fact.

BACKGROUND
  20m leg (2026-08-08 00:40-11:15Z): OpenWSFZ 8080 vs 8081 agreed  94.2%
  17m leg (2026-08-08 12:00-13:07Z): the same pair agreed          99.6%
  ...at the SAME per-cycle density (15.5 vs 14.5), so density does not explain it.
  Ruled out by measurement, not argument:
    - density      : flat 93.0-94.7% across all five 20m quintiles (15.5 -> 37.7 dec/cycle)
    - run length   : flat 93.3-95.4% across all 11 hours of the 20m leg
  Remaining difference between the legs: the band, AND the fact that the 20m pair was
  started 21 minutes apart (incidentally -- the second instance was an idea that arrived
  late that night) while the 17m pair started in the same second.

INTERVENTION
  8081 alone was killed and relaunched at 13:08:24Z, giving it a fresh, arbitrary capture
  phase. 8080 was left running untouched since 11:54:43Z. Same band, same binaries, same
  audio device, same configs. Nothing else changed.

  Cost to the host leg: ~nil. The primary measurement is 8080 vs WSJT-X, which 8081 does not
  touch, and both ROW 0 gates are computed from the WSJT-X reference alone.

READING RULE (first match wins)
  post-restart agreement <  97.0%  -> ROW A: START PHASE IMPLICATED. The 20m 94.2% is
                                     substantially an artefact of the staggered start, not a
                                     decoder property. Operational consequence: every future
                                     paired run must start both instances together, and the
                                     20m corpus's self-consistency figure carries a permanent
                                     asterisk.
  post-restart agreement >= 99.0%  -> ROW B: START PHASE RULED OUT. The difference between
                                     the legs is about the band and its signal population.
  otherwise (97.0-99.0)            -> ROW C: INCONCLUSIVE. Say so; leave it confounded.

ROW 0 (instrument failure, checked FIRST)
  - fewer than 150 cycles in the post window, or
  - fewer than 1000 decodes in the post window union, or
  - 8080's PID changed during the window (it must NOT have restarted), or
  - the reference density in the post window differs from the baseline window by more than
    a factor of 2 (the band moved too much to compare)
  -> VOID, read nothing, re-run.
"""
import collections
import io
import statistics
import sys

BASELINE = ("260808_120000", "260808_130730")   # same-second-start pair
POST = ("260808_131000", "260808_999999")       # after 8081's 13:08:24Z relaunch, gap excluded
DIAL = "18.100"

SRC = {
    "A": "D:/Projects/claude/OpenWSFZ-8080-capture/ALL.TXT",
    "B": "D:/Projects/claude/OpenWSFZ-8081-capture/ALL.TXT",
    "W1": "C:/Users/Frank/AppData/Local/WSJT-X - FT991A/ALL.TXT",
    "W2": "C:/Users/Frank/AppData/Local/WSJT-X - FT991A-Copy/ALL.TXT",
}


def load(path, lo, hi):
    out = set()
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or not f[1].startswith(DIAL):
                continue
            if not (lo <= f[0] <= hi):
                continue
            out.add((f[0], " ".join(f[7:])))
    return out


def window(lo, hi, label):
    A, B = load(SRC["A"], lo, hi), load(SRC["B"], lo, hi)
    W = load(SRC["W1"], lo, hi) & load(SRC["W2"], lo, hi)
    per = collections.Counter(t for t, _ in W)
    dens = statistics.median(per.values()) if per else 0.0
    agree = 100.0 * len(A & B) / max(len(A | B), 1)
    rec = 100.0 * len(A & W) / max(len(W), 1)
    print("  %-28s cycles=%4d  union=%6d  median-density=%4.1f  "
          "self-consistency=%6.2f%%  recovery=%5.1f%%"
          % (label, len(per), len(A | B), dens, agree, rec))
    return agree, len(per), len(A | B), dens


def main():
    print("CAPTURE-PHASE SELF-CONSISTENCY TEST -- 17m, %s\n" % DIAL)
    base_agree, base_cyc, base_n, base_d = window(*BASELINE, "BASELINE (same-second start)")
    post_agree, post_cyc, post_n, post_d = window(*POST, "POST (8081 rephased 13:08:24Z)")

    print("\n  delta = %+.2f points\n" % (post_agree - base_agree))

    void = []
    if post_cyc < 150:
        void.append("post window has only %d cycles (<150)" % post_cyc)
    if post_n < 1000:
        void.append("post window has only %d decodes (<1000)" % post_n)
    if base_d and (post_d / base_d > 2.0 or base_d / max(post_d, 0.01) > 2.0):
        void.append("density moved by more than 2x (%.1f -> %.1f)" % (base_d, post_d))
    if void:
        print("  ROW 0 -- VOID: " + "; ".join(void))
        print("  Read nothing. Re-run.")
        return 0

    if post_agree < 97.0:
        print("  ROW A -- START PHASE IMPLICATED (%.2f%% < 97.0%%)." % post_agree)
        print("  The 20m 94.2%% is substantially an artefact of the staggered start.")
        print("  => every future paired run must start both instances together.")
    elif post_agree >= 99.0:
        print("  ROW B -- START PHASE RULED OUT (%.2f%% >= 99.0%%)." % post_agree)
        print("  The between-leg difference is about the band and its signal population.")
    else:
        print("  ROW C -- INCONCLUSIVE (%.2f%% in 97.0-99.0%%). Leave it confounded." % post_agree)
    return 0


if __name__ == "__main__":
    sys.exit(main())
