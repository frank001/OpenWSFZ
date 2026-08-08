"""Post-hoc DIAGNOSTIC ONLY -- T2 is closed at ROW 3 and this does not re-read its gate.
Question: is `r` a station-level constant, so that decodes are NOT independent units?
If so every SE in T1/T2 that assumed decode-level independence is understated."""
import random, sys
sys.path.insert(0, "qa/cycleframer-alignment-replay")
from t1_frequency_quantisation import load, residual, has_unresolved_hash, WINDOW_20M, LEG_20M

lo, hi = WINDOW_20M
ow = load(LEG_20M["owsfz"], lo, hi)
wa = load(LEG_20M["wsjtx_a"], lo, hi)
wb = load(LEG_20M["wsjtx_b"], lo, hi)
ref = set(wa) & set(wb)

rows = []
for k in ref:
    if has_unresolved_hash(k[1]):
        continue
    snr, f = wa[k]
    if not (200 <= f <= 3000):
        continue
    rows.append((f, round(round(residual(f)/0.125)*0.125, 3), k in ow))
print("kept population = %d (expect 67243)" % len(rows))

CEN = {0.0, 0.125, 0.25}; INT = {0.875, 1.0, 1.125}; MID = {1.375, 1.5}
def grp(r): return "CEN" if r in CEN else "INT" if r in INT else "MID" if r in MID else None

buckets = {"CEN": [], "INT": [], "MID": []}
for f, r, m in rows:
    g = grp(r)
    if g: buckets[g].append((f, m))

print("\ngroup   decodes  distinct_freqs  decodes/freq   binomial_SE   freq-clustered_SE")
ses = {}
for g in ("CEN", "INT", "MID"):
    b = buckets[g]; n = len(b); freqs = set(f for f, _ in b)
    p = sum(1 for _, m in b if m)/n
    se_bin = (p*(1-p)/n)**0.5*100
    byf = {}
    for f, m in b: byf.setdefault(f, []).append(m)
    keys = list(byf)
    rng = random.Random(20260808); samp = []
    for _ in range(400):
        pick = [rng.choice(keys) for _ in keys]
        tot = ok = 0
        for f in pick:
            v = byf[f]; tot += len(v); ok += sum(v)
        samp.append(100.0*ok/tot)
    mu = sum(samp)/len(samp)
    se_cl = (sum((x-mu)**2 for x in samp)/(len(samp)-1))**0.5
    ses[g] = (se_bin, se_cl)
    print("%-6s %8d %15d %13.1f %13.2f %18.2f" % (g, n, len(freqs), n/len(freqs), se_bin, se_cl))

print("\ndesign effect (clustered SE / binomial SE): " +
      ", ".join("%s=%.1fx" % (g, ses[g][1]/ses[g][0]) for g in ses))
d_bin = (ses["CEN"][0]**2+ses["INT"][0]**2)**0.5
d_cl  = (ses["CEN"][1]**2+ses["INT"][1]**2)**0.5
u_bin = (ses["MID"][0]**2+ses["INT"][0]**2)**0.5
u_cl  = (ses["MID"][1]**2+ses["INT"][1]**2)**0.5
print("\n           binomial   freq-clustered")
print("SE(D_int)  %8.2f %14.2f   -> D_int=4.03 is %.1f sigma (clustered)" % (d_bin, d_cl, 4.03/d_cl))
print("SE(U)      %8.2f %14.2f   -> U=1.85 is %.1f sigma (clustered)" % (u_bin, u_cl, 1.85/u_cl))
print("\nspec S4 predicted SE(U)=0.62 pooled / 0.93 with a x1.5 clustering allowance")
