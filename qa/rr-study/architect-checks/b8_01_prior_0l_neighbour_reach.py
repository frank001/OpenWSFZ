"""ARCHITECT prior-setting run for ROW 0l-A (NOT the row itself).
Victim + ONE equal-level neighbour, NO fading. Does the ESTIMATOR's rho1 fall
with Df, and how far does the disturbance reach?  Numbers only."""
import numpy as np, sys
sys.path.insert(0,".")
from synth.encoder import message_to_tones, render_tones
from synth.estimator import extract_channel_gains, rho1
from synth.constants import NUM_SYMBOLS, DEFAULT_SAMPLE_RATE_HZ as FS
COSTAS=(3,1,4,0,6,5,2); STARTS=(0,36,72); IDX=[i for s in STARTS for i in range(s,s+7)]
tC=[0]*NUM_SYMBOLS
for s in STARTS:
    for j,v in enumerate(COSTAS): tC[s+j]=v
MSGS=["CQ QA1AAA JO21","QA1AAA QB2BBB JO22","QB2BBB QA1AAA -12","QA1AAA QB2BBB R-08",
      "QB2BBB QA1AAA RRR","CQ QC3CCC JO33","QC3CCC QD4DDD -05","QD4DDD QC3CCC R+01",
      "CQ QE5EEE JO44","QE5EEE QF6FFF 73","QF6FFF QE5EEE RR73","CQ QG7GGG JO55"]
DTG=np.arange(-0.04,0.0401,0.005); FG=np.arange(-2.0,2.01,0.25)
def locate_and_rho(audio,tones,f0,dt0):
    best=None
    for ddt in DTG:
        for df in FG:
            try: g=extract_channel_gains(audio,tC,f0+df,dt_s=dt0+ddt,sample_rate_hz=FS)
            except Exception: continue
            p=float(np.sum(np.abs(g[IDX])**2))
            if best is None or p>best[0]: best=(p,dt0+ddt,f0+df)
    _,bdt,bf=best
    return rho1(extract_channel_gains(audio,tones,bf,dt_s=bdt,sample_rate_hz=FS))
F0=1500.0; DT=0.5; SNR=15.0
for dfreq in (6.25,12.5,18.75,25.0,31.25,50.0,100.0,200.0,None):
    vals=[]
    for k in range(12):
        tv=message_to_tones(MSGS[k]); tn=message_to_tones(MSGS[(k+5)%12])
        a=render_tones(tv,F0,dt_s=DT,snr_db=SNR,seed=1000+k)
        if dfreq is not None:
            b=render_tones(tn,F0+dfreq,dt_s=DT,snr_db=None,seed=2000+k)
            m=min(len(a),len(b)); a=a[:m].copy(); a[:m]+=b[:m]
        vals.append(locate_and_rho(a,tv,F0,DT))
    v=np.array(vals)
    lab="none" if dfreq is None else "%6.2f"%dfreq
    print("  neighbour Df=%s Hz : median rho1 = %.4f   min=%.4f max=%.4f"%(lab,np.median(v),v.min(),v.max()))
