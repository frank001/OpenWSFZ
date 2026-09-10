"""Is the effect CURRENT or STALE, and what separates S4/S8 from S7/S8HN?

(a) kill rate by sweep date, for the scenarios that show it
(b) true-SNR distribution per scenario -- does S7 simply never visit the danger zone?
"""
import csv
import glob
import re
from collections import defaultdict

CUT = -24.0
by_date = defaultdict(lambda: defaultdict(lambda: [0, 0]))   # date -> scen -> [n, killed]
snr_support = defaultdict(lambda: defaultdict(int))          # scen -> true_snr -> n

for path in glob.glob("qa/rr-study/**/*_matched.csv", recursive=True):
    if ".venv" in path:
        continue
    m = re.search(r"(20\d\d-\d\d-\d\d)", path.replace("\\", "/"))
    date = m.group(1) if m else "undated"
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("appraiser") or "").strip() != "OpenWSFZ":
                continue
            if (r.get("matched") or "").strip() != "True":
                continue
            sid = (r.get("scenario_id") or "").strip()
            try:
                t = float(r["true_snr_db"]); rep = float(r["reported_snr_db"])
            except (ValueError, KeyError, TypeError):
                continue
            snr_support[sid][t] += 1
            e = by_date[date][sid]
            e[0] += 1
            if rep <= CUT:
                e[1] += 1

print("(b) true-SNR support per scenario -- does the scenario even VISIT the danger zone?")
print(f"{'scen':<7}{'min':>7}{'max':>7}{'n<=-6':>9}{'n total':>9}")
for sid in sorted(snr_support):
    s = snr_support[sid]
    lo, hi = min(s), max(s)
    low = sum(v for k, v in s.items() if k <= -6)
    print(f"{sid:<7}{lo:>7.0f}{hi:>7.0f}{low:>9}{sum(s.values()):>9}")

print("\n(a) kill rate by sweep date, S4/S8 only (the scenarios showing the effect)")
print(f"{'date':<13}{'S4 n':>7}{'S4 kill':>9}{'S8 n':>7}{'S8 kill':>9}")
for date in sorted(by_date):
    s4 = by_date[date].get("S4", [0, 0]); s8 = by_date[date].get("S8", [0, 0])
    if s4[0] == 0 and s8[0] == 0:
        continue
    f4 = f"{100*s4[1]/s4[0]:.1f}%" if s4[0] else "-"
    f8 = f"{100*s8[1]/s8[0]:.1f}%" if s8[0] else "-"
    print(f"{date:<13}{s4[0]:>7}{f4:>9}{s8[0]:>7}{f8:>9}")
