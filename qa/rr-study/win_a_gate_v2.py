"""WIN-A gate predicate, AMENDMENT A1 -- shipped as code, not prose (HK-021(r)).

Spec:      qa/rr-study/2026-08-29-1400-architect-to-qa-spec-win-a-analysis-window-sidelobe-ladder.md
Amendment: qa/rr-study/2026-08-29-1859-architect-to-qa-amendment-a1-win-a-rearm-spec.md  (Sec. 5)

The original spec Sec.6 hard-coded thresholds derived from a historical baseline of
c_hit_base = 169. Amendment A1 re-measures the baseline in the arm itself, so the
thresholds now track the measured value. Substituting c_hit_base = 169 reproduces the
original predicate exactly -- verified over the full input domain by self_test() below.

Run `python win_a_gate_v2.py` to re-execute every claim the amendment makes.
ASCII only -- Windows console is cp1252 (HK-009).
"""


def win_a_gate_v2(w_hit, c_hit, w11, c_hit_base):
    """WIN-A verdict, AMENDMENT A1: baseline RE-MEASURED in this arm.

    w_hit      -- OpenWSFZ weak-signal recoveries in P12/P13/P14, treatment leg. Pop 15.
    c_hit      -- OpenWSFZ recoveries over the other 200 S7 observations, treatment leg.
    w11        -- OpenWSFZ weak-signal recoveries in P11, treatment leg. Pop 5.
    c_hit_base -- mean of the two baseline legs' c_hit, rounded half to even.

    Preconditions, asserted by ROW 0b BEFORE this is called (never inside it):
        baseline w_hit == 0 on both legs
        baseline w11  == 5 on both legs
        abs(c_hit_1 - c_hit_2) <= 4

    Evaluated in strict order; first true row wins. Signed throughout (HK-021(l)).
    """

    # ROW 2 -- HARM. Checked FIRST so a benefit cannot mask a material cost.
    if c_hit <= c_hit_base - 12:
        return "ROW 2 -- HARM"

    # ROW 1 -- BENEFIT. Both limbs required (HK-021(t)).
    if w_hit >= 5 and c_hit >= c_hit_base - 4 and w11 == 5:
        return "ROW 1 -- BENEFIT"

    # ROW 3 -- PARTIAL.
    if w_hit >= 1:
        return "ROW 3 -- PARTIAL"

    # ROW 4 -- NULL.
    return "ROW 4 -- NULL"


def _win_a_gate_original(w_hit, c_hit, w11):
    """Spec Sec.6 as ratified, retained ONLY so self_test can prove A1 generalises it."""
    if c_hit <= 157:
        return "ROW 2 -- HARM"
    if w_hit >= 5 and c_hit >= 165 and w11 == 5:
        return "ROW 1 -- BENEFIT"
    if w_hit >= 1:
        return "ROW 3 -- PARTIAL"
    return "ROW 4 -- NULL"


def self_test():
    """Every claim Amendment A1 Sec.5 makes, executed. Returns True if all hold."""
    ok = True

    # Sec.5.2 boundary table.
    table = [
        (0, 160, 5, 160, "ROW 4 -- NULL"),
        (0, 148, 5, 160, "ROW 2 -- HARM"),
        (0, 149, 5, 160, "ROW 4 -- NULL"),
        (5, 156, 5, 160, "ROW 1 -- BENEFIT"),
        (5, 155, 5, 160, "ROW 3 -- PARTIAL"),
        (1, 160, 5, 160, "ROW 3 -- PARTIAL"),
        (0, 159, 5, 169, "ROW 4 -- NULL"),   # 08-29 treatment vs historical baseline
        (0, 159, 5, 171, "ROW 2 -- HARM"),   # the only baseline value that flips it
    ]
    print("== Sec.5.2 boundary table ==")
    for w, c, w11, base, want in table:
        got = win_a_gate_v2(w, c, w11, base)
        flag = "OK " if got == want else "!! "
        ok &= got == want
        print("  %sw=%2d c=%3d w11=%d base=%3d -> %s" % (flag, w, c, w11, base, got))

    # Sec.5.1 -- A1 is a strict generalisation of the ratified predicate.
    bad = [(w, c, w11)
           for w in range(16) for c in range(201) for w11 in range(6)
           if win_a_gate_v2(w, c, w11, 169) != _win_a_gate_original(w, c, w11)]
    ok &= not bad
    print("\n== Sec.5.1 strict generalisation at c_hit_base=169, full domain ==")
    print("  inputs checked: %d   mismatches: %d" % (16 * 201 * 6, len(bad)))

    # ROW 1 / ROW 2 mutual exclusivity, for every plausible measured baseline.
    both = [(base, w, c, w11)
            for base in range(140, 201) for w in range(16)
            for c in range(201) for w11 in (4, 5)
            if (c <= base - 12) and (w >= 5 and c >= base - 4 and w11 == 5)]
    ok &= not both
    print("\n== ROW 1 / ROW 2 mutual exclusivity, c_hit_base 140-200 ==")
    print("  inputs satisfying BOTH: %d" % len(both))

    # Amendment Sec.1 -- at w_hit = 0 the verdict is constrained to ROW 2 or ROW 4.
    reach = sorted(set(win_a_gate_v2(0, c, 5, b)
                       for b in range(140, 201) for c in range(201)))
    ok &= reach == ["ROW 2 -- HARM", "ROW 4 -- NULL"]
    print("\n== Sec.1: verdicts reachable at w_hit=0 (any baseline) ==")
    print("  %s" % reach)

    flip = [b for b in range(150, 201) if win_a_gate_v2(0, 159, 5, b) == "ROW 2 -- HARM"]
    print("  ROW 2 fires on the 08-29 treatment leg iff c_hit_base >= %d" % min(flip))

    print("\n%s" % ("ALL CLAIMS HOLD" if ok else "!! A CLAIM FAILED -- do not arm"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
