"""ARCHITECT: how far must an estimator disturbance REACH for P3 to explain a
pedestal at the MEDIAN?  Computed from C2's own occupancy. Numbers only."""
import numpy as np
from collections import defaultdict
R="D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/"
cyc=defaultdict(list)
for ln in open(R+"wsjtx-1-ft991a/ALL.TXT",encoding="utf-8",errors="replace"):
    f=ln.split()
    if len(f)<8 or f[2]!="Rx" or f[3]!="FT8": continue
    if f[0]<"260908_193645": continue
    try: cyc[f[0]].append((float(f[6]),float(f[4])))
    except ValueError: pass
d=[]
for ts,rows in cyc.items():
    fr=np.array([r[0] for r in rows])
    if len(fr)<2: continue
    for i in range(len(fr)):
        o=np.delete(fr,i)
        d.append(np.min(np.abs(o-fr[i])))
d=np.array(d)
print("rows=%d  cycles=%d  median decodes/cycle=%.0f"%(len(d),len(cyc),np.median([len(v) for v in cyc.values()])))
print("nearest-neighbour |Df| : median=%.1f Hz  p25=%.1f  p75=%.1f"%(np.median(d),np.percentile(d,25),np.percentile(d,75)))
print()
for r in (6.25,12.5,18.75,25,31.25,50,100,200,400):
    print("  share of rows with a neighbour within %6.2f Hz : %.3f"%(r,(d<=r).mean()))
print()
print(">>> For P3 to move the MEDIAN, >50%% of rows must be disturbed.")
print(">>> Required reach R such that share>=0.50 : R = %.1f Hz (= %.1f tone spacings)"%(
    np.median(d), np.median(d)/6.25))
