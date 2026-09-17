"""ARCHITECT ad-hoc (HK-018): with the time origin CORRECTED (+0.48 s), does the
FULL re-encoded message correlate?  That is the other branch of spec Sec.11.4.
NFR-021: numbers only, no callsigns/message text printed."""
import numpy as np, sys
sys.path.insert(0,".")
from synth.estimator import extract_channel_gains, rho1
from synth.encoder import message_to_tones
from synth.wavio import read_wav
from synth.constants import NUM_SYMBOLS
R="D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/"
COSTAS=(3,1,4,0,6,5,2); STARTS=(0,36,72); IDX=[i for s in STARTS for i in range(s,s+7)]
def load(p):
    rows={}
    for ln in open(p,encoding="utf-8",errors="replace"):
        f=ln.split()
        if len(f)<8 or f[2]!="Rx" or f[3]!="FT8": continue
        try: snr=float(f[4]); dt=float(f[5]); fr=float(f[6])
        except ValueError: continue
        rows.setdefault((f[0]," ".join(f[7:]).strip()),(snr,dt,fr))
    return rows
w=load(R+"wsjtx-1-ft991a/ALL.TXT")
keys=sorted(k for k in w if k[0]>="260908_193645" and w[k][0]>=10.0)
rng=np.random.default_rng(20260917)
sel=[keys[i] for i in sorted(rng.choice(len(keys),size=30,replace=False))]
DTG=np.arange(0.38,0.585,0.01); FG=np.arange(-2.0,2.01,0.25)
ok=enc_fail=0; res=[]
for (ts,msg) in sel:
    snr,dtw,frw=w[(ts,msg)]
    try: tones=message_to_tones(msg)
    except Exception: enc_fail+=1; continue
    if len(tones)!=NUM_SYMBOLS: enc_fail+=1; continue
    if [tones[s+j] for s in STARTS for j in range(7)]!=list(COSTAS)*3:
        print("  !! costas mismatch in re-encode"); continue
    try: audio,fs=read_wav(R+"cycle-audio/%s.wav"%ts)
    except Exception: continue
    best=None; P=[]
    for ddt in DTG:
        dt=dtw+ddt
        if dt<0 or dt>2.36: continue
        for df in FG:
            try: g=extract_channel_gains(audio,tones,frw+df,dt_s=dt,sample_rate_hz=fs)
            except Exception: continue
            p=float(np.sum(np.abs(g)**2)); P.append(p)
            if best is None or p>best[0]: best=(p,dt,frw+df,g)
    if best is None: continue
    p,bdt,bfr,g=best; med=float(np.median(P)); r=rho1(g)
    cp=float(np.sum(np.abs(g[IDX])**2))/21.0; dp=float(np.sum(np.abs(g)**2)-np.sum(np.abs(g[IDX])**2))/58.0
    res.append((r,p/med,bdt-dtw,dp/cp if cp>0 else np.nan)); ok+=1
    print("  snr=%+3.0f dt_off=%+.2f df=%+.2f  sharp=%.1fx  rho1=%.3f  data/costas power=%.2f"%(snr,bdt-dtw,bfr-frw,p/med,r,dp/cp if cp>0 else -1))
a=np.array(res)
print("\nn=%d re-encoded OK (%d pack failures)"%(ok,enc_fail))
print("rho1 FULL-message: median=%.3f  p10=%.3f p90=%.3f   share < rho*=0.577 : %.3f"%(
    np.median(a[:,0]),np.percentile(a[:,0],10),np.percentile(a[:,0],90),(a[:,0]<0.577).mean()))
print("median sharpness=%.1fx   median dt offset=%+.3f s   median data/costas per-symbol power ratio=%.2f"%(
    np.median(a[:,1]),np.median(a[:,2]),np.nanmedian(a[:,3])))
