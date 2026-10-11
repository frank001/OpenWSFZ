"""Checks for wsjtx_version.py. Run:  python test_wsjtx_version.py   (exit 0 = pass).
Pure-logic checks only; the measurement itself (probe) is exercised against real installs, see the commit message."""
import sys

import wsjtx_version as W

PARSE = [
    ("2.7.0", "2.7.0"), ("WSJT-X 2.7.0 (inferred from binary date 2025-02-04)", "2.7.0"), ("2.6.1", "2.6.1"), ("2.7.0-rc8", "2.7.0"),
    ("3.0.0", "3.0.0"), ("WSJT-X v3.0.2", "3.0.2"), ("3.1.0_p260522 (wsjtx_improved)", "3.1.0"), ("10.2", "10.2.0"),
    ("", None), (None, None), ("unknown", None), ("3", None),
]

JT9_OUT_DECODED = "000000  20 -0.5 1500 ~  CQ Q1ABC FN42\n<DecodeFinished>   0   1        0\n"
JT9_OUT_NONE = "<DecodeFinished>   0   0        0\n"
JT9_OUT_OTHER = "000000  20 -0.5 1500 ~  CQ K1ABC FN42\n<DecodeFinished>   0   1        0\n"


def measured(found=True, jt9=True, decoded=True):
    return {"found": found, "exe": "x", "exe_sha256": "0" * 64, "jt9": "j" if jt9 else None, "canary_decoded": decoded, "reason": ""}


def main():
    bad = 0

    def expect(ok, what):
        nonlocal bad
        if not ok:
            bad += 1
            print("FAIL", what)

    for text, parsed in PARSE:
        v = W.parse_version(text)
        expect((".".join(map(str, v)) if v else None) == parsed, "parse %r" % (text,))
    expect(W.parse_version("2.99.99") < W.Q_PREFIX_MAX_EXCLUSIVE <= W.parse_version("3.0.0"), "boundary")

    expect(W.canary_decoded_in(JT9_OUT_DECODED), "decode line recognised")
    expect(not W.canary_decoded_in(JT9_OUT_NONE), "no decode")
    expect(not W.canary_decoded_in(JT9_OUT_OTHER), "a different message is not the canary")
    expect(not W.canary_decoded_in(None) and not W.canary_decoded_in(""), "empty output")

    def c(stated, m):
        return W.check(stated, m)["checks"]

    # measurement is what gates
    ok = c(None, measured())
    expect(all(ok.values()), "measured decode, nothing stated: pass")
    expect(not c(None, measured(decoded=False))["wsjtx_q_prefix_canary_decodes"], "no decode: refused")
    expect(not c(None, measured(decoded=None))["wsjtx_q_prefix_canary_decodes"], "measurement not possible: refused")
    expect(not c(None, measured(found=False, jt9=False, decoded=None))["wsjtx_found_running"], "not found: refused")
    expect(not c(None, measured(jt9=False))["wsjtx_found_running"], "no jt9: refused")
    # a typed version can never rescue a failed measurement, and must agree with a good one
    expect(not c("2.7.0", measured(decoded=False))["wsjtx_q_prefix_canary_decodes"], "typed 2.7.0 on a 3.x install: still refused by the measurement")
    expect(not c("2.7.0", measured(decoded=False))["wsjtx_stated_version_consistent"], "typed 2.7.0 contradicts a failed canary")
    expect(c("2.7.0", measured(decoded=True))["wsjtx_stated_version_consistent"], "typed 2.7.0 agrees with a decode")
    expect(not c("3.0.2", measured(decoded=True))["wsjtx_stated_version_consistent"], "typed 3.0.2 contradicts a decode")
    expect(not c("unknown", measured(decoded=True))["wsjtx_stated_version_consistent"], "unparseable stated version is inconsistent")
    expect(c("3.0.2", measured(decoded=False))["wsjtx_stated_version_consistent"], "typed 3.0.2 agrees with no decode (still refused by the measurement)")

    print("OK" if not bad else "%d FAILED" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
