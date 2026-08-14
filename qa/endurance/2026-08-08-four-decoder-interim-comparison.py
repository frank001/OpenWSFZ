#!/usr/bin/env python3
"""Interim four-decoder comparison for the 2026-08-08 live run.

EXPLORATORY, NOT A PRE-REGISTERED GATE (HK-021). No thresholds, no ROW
assignment -- this reports counts and stratifications only, so that a proper
gate can be drafted afterwards against numbers somebody has actually seen.

Sources (all four decoders, one split antenna, one shared USB Audio CODEC):
  OpenWSFZ 8080 / 8081  -- same build, same device (self-consistency control)
  WSJT-X FT991A / FT991A-Copy -- the reference pair

Usage:  python 2026-08-08-four-decoder-interim-comparison.py [LO_TS] [HI_TS]
        timestamps in ALL.TXT form, e.g. 260808_004000 260808_111500
"""
import io
import re
import sys

SOURCES = {
    "OWSFZ-8080": "D:/Projects/claude/OpenWSFZ-8080-capture/ALL.TXT",
    "OWSFZ-8081": "D:/Projects/claude/OpenWSFZ-8081-capture/ALL.TXT",
    "WSJTX-FT991A": "C:/Users/Frank/AppData/Local/WSJT-X - FT991A/ALL.TXT",
    "WSJTX-Copy": "C:/Users/Frank/AppData/Local/WSJT-X - FT991A-Copy/ALL.TXT",
}

DIAL_PREFIX = "14.074"
# Callsign shape, deliberately permissive; used only as a plausibility proxy.
CALLSIGN_RE = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z]{1,3}(/[A-Z0-9]{1,2})?$")

# Stratification edges. Chosen to be read, not to gate on.
DF_EDGES = [(0, 200), (200, 400), (400, 1000), (1000, 1600),
            (1600, 2000), (2000, 2500), (2500, 3000), (3000, 6000)]
SNR_EDGES = [(-30, -21), (-21, -18), (-18, -15), (-15, -10),
             (-10, -5), (-5, 0), (0, 40)]


def load(path, lo, hi):
    """(ts, message) -> (snr, df) for Rx FT8 lines on the dial freq in window."""
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(DIAL_PREFIX):
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                snr, df = int(f[4]), int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, df)
    return out


def histogram(rows, idx, edges, label):
    print("   ", label)
    for lo, hi in edges:
        n = sum(1 for r in rows if lo <= r[idx] < hi)
        print("      %6s..%-6s %6d (%5.1f%%)" % (lo, hi, n, 100.0 * n / max(len(rows), 1)))


def callsigns(messages):
    found = set()
    for _, msg in messages:
        for token in msg.split():
            token = token.strip("<>")
            if CALLSIGN_RE.match(token):
                found.add(token)
    return found


def plausibility(label, messages, known):
    """Share of decodes whose every callsign was heard by WSJT-X somewhere in
    the window. Near-100% for real traffic; near-floor for fabricated text."""
    total = ok = 0
    for _, msg in messages:
        cs = [t.strip("<>") for t in msg.split() if CALLSIGN_RE.match(t.strip("<>"))]
        if not cs:
            continue
        total += 1
        if all(c in known for c in cs):
            ok += 1
    print("   %-34s n=%5d  all-callsigns-known: %5d (%5.1f%%)"
          % (label, total, ok, 100.0 * ok / max(total, 1)))


def main():
    lo = sys.argv[1] if len(sys.argv) > 1 else "260808_004000"
    hi = sys.argv[2] if len(sys.argv) > 2 else "260808_111500"
    data = {name: load(path, lo, hi) for name, path in SOURCES.items()}
    A, B = set(data["OWSFZ-8080"]), set(data["OWSFZ-8081"])
    W1, W2 = set(data["WSJTX-FT991A"]), set(data["WSJTX-Copy"])
    Wboth = W1 & W2

    print("window %s .. %s UTC\n" % (lo, hi))
    print("1. VOLUME")
    for name in SOURCES:
        s = set(data[name])
        cycles = len(set(t for t, _ in s))
        print("   %-13s decodes=%6d  cycles=%4d  per-cycle=%4.1f"
              % (name, len(s), cycles, len(s) / max(cycles, 1)))

    print("\n2. SELF-CONSISTENCY (the two controls)")
    for a, b, lbl in ((W1, W2, "WSJT-X vs WSJT-X"), (A, B, "OpenWSFZ vs OpenWSFZ")):
        print("   %-22s agreement=%5.1f%%  (both=%d, disagree=%d)"
              % (lbl, 100.0 * len(a & b) / max(len(a | b), 1), len(a & b), len(a ^ b)))

    print("\n3. RECOVERY of decodes BOTH WSJT-X instances made (n=%d)" % len(Wboth))
    print("   by 8080 alone : %6d (%5.1f%%)" % (len(A & Wboth), 100.0 * len(A & Wboth) / max(len(Wboth), 1)))
    print("   by 8080|8081  : %6d (%5.1f%%)" % (len((A | B) & Wboth), 100.0 * len((A | B) & Wboth) / max(len(Wboth), 1)))

    W = W1 | W2
    missed = [data["WSJTX-FT991A"][k] for k in (W1 - A)]
    matched = [data["WSJTX-FT991A"][k] for k in (W1 & A)]
    print("\n4. WHERE THE MISSES LIE (WSJT-X's own SNR/df, not OpenWSFZ's)")
    print("   MISSED by OpenWSFZ, n=%d" % len(missed))
    histogram(missed, 1, DF_EDGES, "by audio freq (Hz)")
    histogram(missed, 0, SNR_EDGES, "by SNR (dB)")
    print("   MATCHED, n=%d" % len(matched))
    histogram(matched, 1, DF_EDGES, "by audio freq (Hz)")
    histogram(matched, 0, SNR_EDGES, "by SNR (dB)")

    print("\n   recovery rate by SNR band:")
    for lo_s, hi_s in SNR_EDGES:
        m = sum(1 for r in matched if lo_s <= r[0] < hi_s)
        x = sum(1 for r in missed if lo_s <= r[0] < hi_s)
        print("      %4d..%-4d  %6d/%-6d = %5.1f%%" % (lo_s, hi_s, m, m + x, 100.0 * m / max(m + x, 1)))

    print("\n5. DECODES OPENWSFZ MADE THAT NEITHER WSJT-X DID (n=%d)" % len(((A | B) - W)))
    known = callsigns(W)
    print("   distinct callsigns in the WSJT-X corpus: %d" % len(known))
    print("   NOTE: 'matched' is tautologically 100%% -- it IS the WSJT-X corpus.")
    print("   NOTE: both OpenWSFZ instances run the SAME build on the SAME audio,")
    print("         so agreement between them does NOT validate a decode; a")
    print("         deterministic false positive appears in both.")
    plausibility("matched (OpenWSFZ AND WSJT-X)", A & W, known)
    plausibility("novel, corroborated 8080+8081", (A & B) - W, known)
    plausibility("novel, single-instance only", (A | B) - W - (A & B), known)


if __name__ == "__main__":
    main()
