import sys, numpy as np
from collections import defaultdict
R="D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/"
def load(p):
    rows={}
    with open(p, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            f=ln.split()
            if len(f)<8 or f[2]!="Rx" or f[3]!="FT8": continue
            try:
                snr=float(f[4]); dt=float(f[5]); fr=float(f[6])
            except ValueError: continue
            msg=" ".join(f[7:]).strip()
            rows.setdefault((f[0],msg),(snr,dt,fr))
    return rows
w=load(R+"wsjtx-1-ft991a/ALL.TXT")
o=load(R+"openwsfz/ALL.TXT")
print("rows: wsjtx=%d openwsfz=%d"%(len(w),len(o)))
common=set(w)&set(o)
print("matched (ts,msg) pairs: %d"%len(common))
d=np.array([w[k][1]-o[k][1] for k in common])
df=np.array([w[k][2]-o[k][2] for k in common])
print("DT_wsjtx - DT_openwsfz : median=%+.4f s  mean=%+.4f  sd=%.4f  p05=%+.4f p95=%+.4f"%(
    np.median(d),d.mean(),d.std(),np.percentile(d,5),np.percentile(d,95)))
print("  |dev from median| p90 = %.4f s"%np.percentile(np.abs(d-np.median(d)),90))
print("freq_wsjtx - freq_openwsfz: median=%+.3f Hz sd=%.3f"%(np.median(df),df.std()))
print("DT_wsjtx  : median=%+.3f  range [%+.3f,%+.3f]"%(np.median([w[k][1] for k in common]),min(w[k][1] for k in common),max(w[k][1] for k in common)))
print("DT_owsfz  : median=%+.3f  range [%+.3f,%+.3f]"%(np.median([o[k][1] for k in common]),min(o[k][1] for k in common),max(o[k][1] for k in common)))
