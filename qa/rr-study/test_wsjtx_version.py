"""Checks for wsjtx_version.py. Run:  python test_wsjtx_version.py   (exit 0 = pass)."""
import sys

import wsjtx_version as W

CASES = [
    # text, parsed, recorded, supports_q_prefix
    ("2.7.0", "2.7.0", True, True),
    ("WSJT-X 2.7.0 (inferred from binary date 2025-02-04)", "2.7.0", True, True),
    ("WSJT-X 2.7.0, built from source on sol (wsjtx-2.7.0.tgz ...; conda-forge Qt 5.15)", "2.7.0", True, True),
    ("2.6.1", "2.6.1", True, True),
    ("2.7.0-rc8", "2.7.0", True, True),
    ("3.0.0", "3.0.0", True, False),
    ("WSJT-X v3.0.2", "3.0.2", True, False),
    ("3.1.0_p260522 (wsjtx_improved)", "3.1.0", True, False),
    ("10.2", "10.2.0", True, False),
    ("", None, False, False),
    (None, None, False, False),
    ("unknown", None, False, False),
    ("3", None, False, False),
]


def main():
    bad = 0
    for text, parsed, rec, q in CASES:
        r = W.check(text)
        got = (r["parsed"], r["checks"]["wsjtx_version_recorded"], r["checks"]["wsjtx_version_supports_q_prefix"])
        if got != (parsed, rec, q):
            bad += 1
            print("FAIL", repr(text), "expected", (parsed, rec, q), "got", got)
    # the boundary itself
    assert W.parse_version("2.99.99") < W.Q_PREFIX_MAX_EXCLUSIVE <= W.parse_version("3.0.0")
    print("OK" if not bad else "%d FAILED" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
