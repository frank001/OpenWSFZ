"""ARCHITECT ad-hoc check (HK-018): does a WIDE DT sweep recover a Costas peak
on real C2 rows?  Numbers only -- no callsigns, no message text (NFR-021)."""
import numpy as np, sys
sys.path.insert(0,".")
from synth.estimator import extract_channel_gains, rho1
from synth.wavio import read_wav
from synth.constants import NUM_SYMBOLS

R="D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/"
COSTAS=(3,1,4,0,6,5,2); STARTS=(0,36,72)
IDX=[i for s in STARTS for i in range(s,s+7)]
def tones():
    t=[0]*NUM_SYMBOLS
    for s in STARTS:
        for j,v in enumerate(COSTAS): t[s+j]=v
    return t
def load(p):
    rows={}
    for ln in open(p,encoding="utf-8",errors="replace"):
        f=ln.split()
        if len(f)<8 or f[2]!="Rx" or f[3]!="FT8": continue
        try: snr=float(f[4]); dt=float(f[5]); fr=float(f[6])
        except ValueError: continue
        rows.setdefault((f[0]," ".join(f[7:]).strip()),(snr,dt,fr))
    return rows
w=load(R+"wsjtx-1-ft991a/ALL.TXT"); o=load(R+"openwsfz/ALL.TXT")
lo,hi="260908_193645","260909_999999"
keys=[k for k in (set(w)&set(o)) if lo<=k[0]<=hi and w[k][0]>=10.0]
keys.sort(); rng=np.random.default_rng(20260917)
sel=[keys[i] for i in sorted(rng.choice(len(keys),size=min(12,len(keys)),replace=False))]
print("strong (>=+10dB) rows decoded by BOTH: %d ; using %d"%(len(keys),len(sel)))
T=tones()
DTG=np.arange(-0.30,1.41,0.02); FG=np.arange(-3.0,3.01,0.5)
hits=[]
for (ts,msg) in sel:
    snr,dtw,frw=w[(ts,msg)]; _,dto,fro=o[(ts,msg)]
    try: audio,fs=read_wav(R+"cycle-audio/%s.wav"%ts)
    except Exception as e: print("  skip",ts,e); continue
    best=None; P=[]
    for ddt in DTG:
        dt=dtw+ddt
        if dt<0 or dt>2.36: continue
        for df in FG:
            try: g=extract_channel_gains(audio,T,frw+df,dt_s=dt,sample_rate_hz=fs)
            except Exception: continue
            p=float(np.sum(np.abs(g[IDX])**2)); P.append(p)
            if best is None or p>best[0]: best=(p,dt,frw+df,g)
    if best is None: continue
    p,bdt,bfr,g=best; med=float(np.median(P))
    hits.append((bdt-dtw,bdt-dto,p/med))
    print("  snr=%+3.0f  peak@dt=%.3f  dt-DTwsjtx=%+.3f  dt-DTowsfz=%+.3f  df=%+.1fHz  sharp=%.1fx  rho1(peak)=%.3f"
          %(snr,bdt,bdt-dtw,bdt-dto,bfr-frw,p/med,rho1(g)))
a=np.array(hits)
if len(a):
    print("\nn=%d  median (peak - DT_wsjtx) = %+.3f s   median (peak - DT_owsfz) = %+.3f s   median sharpness = %.1fx"
          %(len(a),np.median(a[:,0]),np.median(a[:,1]),np.median(a[:,2])))
