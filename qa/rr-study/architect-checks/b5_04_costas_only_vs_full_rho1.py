"""Does a COSTAS-ONLY rho1 (message-independent, zero dropped rows) track the
full-message rho1?  Decides B5's design.  NFR-021: numbers only."""
import numpy as np, sys
sys.path.insert(0,".")
from synth.estimator import extract_channel_gains, rho1
from synth.encoder import message_to_tones
from synth.wavio import read_wav
from synth.constants import NUM_SYMBOLS
R="D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/"
COSTAS=(3,1,4,0,6,5,2); STARTS=(0,36,72)
BLOCKS=[list(range(s,s+7)) for s in STARTS]
def costas_rho1(g):
    num=0j; den=0.0
    for b in BLOCKS:
        gg=g[b]; num+=np.sum(gg[1:]*np.conj(gg[:-1])); den+=np.sum(np.abs(gg)**2)
    return float(abs(num)/den)
# null for the 18-pair / 21-sample Costas statistic
rng=np.random.default_rng(20260917)
null=np.array([costas_rho1((rng.normal(size=79)+1j*rng.normal(size=79))) for _ in range(30000)])
print("COSTAS-ONLY rho1 NULL (uncorrelated gains): median=%.3f p90=%.3f p99=%.3f"%(
    np.median(null),np.percentile(null,90),np.percentile(null,99)))
full79=np.array([rho1(rng.normal(size=79)+1j*rng.normal(size=79)) for _ in range(30000)])
print("FULL-79   rho1 NULL                        : median=%.3f p90=%.3f p99=%.3f"%(
    np.median(full79),np.percentile(full79,90),np.percentile(full79,99)))
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
keys=sorted(k for k in w if k[0]>="260908_193645" and -10.0<=w[k][0])
r2=np.random.default_rng(4242); sel=[keys[i] for i in sorted(r2.choice(len(keys),size=40,replace=False))]
DTG=np.arange(0.40,0.601,0.01); FG=np.arange(-2.0,2.01,0.25)
tonesC=[0]*NUM_SYMBOLS
for s in STARTS:
    for j,v in enumerate(COSTAS): tonesC[s+j]=v
pairs=[]; ndrop=0
for (ts,msg) in sel:
    snr,dtw,frw=w[(ts,msg)]
    try: audio,fs=read_wav(R+"cycle-audio/%s.wav"%ts)
    except Exception: continue
    best=None
    for ddt in DTG:
        dt=dtw+ddt
        if dt<0 or dt>2.36: continue
        for df in FG:
            try: g=extract_channel_gains(audio,tonesC,frw+df,dt_s=dt,sample_rate_hz=fs)
            except Exception: continue
            p=sum(float(np.sum(np.abs(g[b])**2)) for b in BLOCKS)
            if best is None or p>best[0]: best=(p,dt,frw+df,g)
    if best is None: continue
    _,bdt,bfr,gC=best
    rc=costas_rho1(gC)
    try:
        tf=message_to_tones(msg)
        gF=extract_channel_gains(audio,tf,bfr,dt_s=bdt,sample_rate_hz=fs)
        rf=rho1(gF)
    except Exception:
        ndrop+=1; rf=np.nan
    pairs.append((snr,rc,rf))
a=np.array(pairs)
m=~np.isnan(a[:,2])
print("\nn=%d rows (>=-10dB), %d non-re-encodable (%.1f%%)"%(len(a),ndrop,100*ndrop/len(a)))
print("COSTAS-only rho1 : median=%.3f  share<0.577=%.3f"%(np.median(a[:,1]),(a[:,1]<0.577).mean()))
print("FULL-msg   rho1 : median=%.3f  share<0.577=%.3f  (n=%d)"%(np.nanmedian(a[m,2]),(a[m,2]<0.577).mean(),m.sum()))
print("Pearson r(costas, full) = %.3f   Spearman-ish = %.3f"%(
    np.corrcoef(a[m,1],a[m,2])[0,1],
    np.corrcoef(np.argsort(np.argsort(a[m,1])),np.argsort(np.argsort(a[m,2])))[0,1]))
