"""Architect-exploratory (A-prime review, 2026-10-06): recall of OpenWSFZ vs WSJT-X by WSJT-X SNR.

Re-asks C-GAP-D's 2026-08-22 shape question on a post-subtraction night. HK-037: message text never
leaves load_and_match(); only numeric aggregates are returned and printed. No clustering, no CI:
EXPLORATORY, one night, one band.
Usage: python -I recall_shape.py <wsjtx ALL.TXT> <owsfz ALL.TXT>
"""
import sys
from collections import defaultdict


def load_and_match(ws_path, ow_path, dhz=10.0):
    def parse(path):
        per = defaultdict(list)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                p = ln.split()
                if len(p) < 8 or p[3] != "FT8":
                    continue
                try:
                    snr, f = int(p[4]), float(p[6])
                except ValueError:
                    continue
                per[p[0]].append((snr, f, " ".join(p[7:])))
        return per

    ws, ow = parse(ws_path), parse(ow_path)
    common = set(ws) & set(ow)  # cycles both logged (window overlap)
    rows = []  # (ws_snr, hit, cycle_load) -- numeric only leaves this function
    for ts in common:
        avail = list(ow[ts])
        load = len(ws[ts])
        for snr, f, msg in sorted(ws[ts], key=lambda r: -r[0]):
            best, bi = None, -1
            for i, (s2, f2, m2) in enumerate(avail):
                if m2 == msg and abs(f2 - f) <= dhz and (best is None or abs(f2 - f) < best):
                    best, bi = abs(f2 - f), i
            hit = bi >= 0
            if hit:
                avail.pop(bi)
            rows.append((snr, hit, load))
    return rows, len(common)


def main():
    rows, ncyc = load_and_match(sys.argv[1], sys.argv[2])
    n = len(rows)
    print(f"cycles both logged {ncyc}; WSJT-X decodes {n}; matched {sum(h for _, h, _ in rows)} "
          f"({100*sum(h for _, h, _ in rows)/n:.2f} %)")
    bins = defaultdict(lambda: [0, 0])
    for s, h, _ in rows:
        b = max(-24, min(20, (s // 2) * 2))
        bins[b][0] += 1
        bins[b][1] += h
    print("\nrecall by WSJT-X SNR (2 dB bins, edges clipped at -24/+20):")
    print(" snr   n      recall")
    for b in sorted(bins):
        t, h = bins[b]
        print(f"{b:+4d} {t:6d}  {h/t:6.3f}")
    # C-GAP-D shift estimator: credit every row at SNR x with recall r(x+s). Upper bound by construction.
    rec = {b: bins[b][1] / bins[b][0] for b in bins}
    keys = sorted(rec)
    def r_at(x):  # linear interpolation between bin centres, clamped at the ends
        x = max(keys[0], min(keys[-1], x))
        lo = max(k for k in keys if k <= x)
        hi = min(k for k in keys if k >= x)
        if hi == lo:
            return rec[lo]
        return rec[lo] + (rec[hi] - rec[lo]) * (x - lo) / (hi - lo)
    base = sum(bins[b][1] for b in bins) / n
    print("\nshift estimator (C-GAP-D method; upper bound): gain in pp of WSJT-X decodes")
    for s in (1, 2, 3, 4.8, 6, 10):
        g = sum(bins[b][0] * max(0.0, r_at(b + s) - rec[b]) for b in bins) / n
        print(f"  +{s:>4} dB -> +{100*g:5.2f} pp   (gap now {100*(1-base):.2f} pp)")
    # interference signature: high-SNR recall by cycle-load quintile
    loads = sorted(l for _, _, l in rows)
    qs = [loads[int(len(loads) * k / 5)] for k in range(1, 5)]
    def qi(l):
        return sum(l > q for q in qs)
    hi = defaultdict(lambda: [0, 0])
    for s, h, l in rows:
        if s >= 0:
            hi[qi(l)][0] += 1
            hi[qi(l)][1] += h
    print("\nrecall of WSJT-X decodes at SNR >= 0 dB, by cycle-load quintile (WSJT-X decodes/cycle):")
    for k in sorted(hi):
        t, h = hi[k]
        print(f"  Q{k+1}  n {t:6d}  recall {h/t:6.3f}")
    print(f"  quintile cut points: {qs}")


if __name__ == "__main__":
    main()
