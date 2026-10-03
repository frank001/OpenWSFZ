# Independent recount: does NOT import analysis.py / design.py. Counts only; planted texts only (HK-037).
import json, csv, collections, statistics, pathlib
HERE=pathlib.Path(__file__).resolve().parent
from datetime import datetime, timezone
R='D:/Projects/claude/OpenWSFZ/artefacts/20261002_2115_lateness_edge_run/'
m=json.load(open(str(HERE.parent/'manifest.json')))
bnd={}
for r in csv.DictReader(open(R+'playback_log.csv')):
    bnd[int(r['cycle_index'])]=r['boundary_utc'].replace('-','').replace(':','')[2:].replace('T','_').rstrip('Z')  # yymmdd_hhmmss
sig={s['text']:s for s in m['signals']}
def load(p):
    hit=collections.defaultdict(list)
    for line in open(p,encoding='utf-8',errors='replace'):
        t=line.split()
        if len(t)<8: continue
        txt=' '.join(t[7:])
        if txt in sig: hit[(t[0],txt)].append((float(t[4]),float(t[5]),float(t[6])))
    return hit
out={}
for name,p in (('wsjtx','ALL.wsjtx.TXT'),('owsfz','ALL.TXT')):
    h=load(R+p); cell=collections.Counter(); dts=collections.defaultdict(list)
    for s in m['signals']:
        for (snr,dt,f) in h.get((bnd[s['cycle']],s['text']),[]):
            if abs(f-s['freq_hz'])<=10:
                cell[s['cell']]+=1; dts[s['cell']].append(dt); break
    out[name]=(cell,dts)
res=json.load(open(str(HERE/'analysis_result_engineer_rerun.json')))
bad=0
for d in out:
    for c,v in res['cells'][d].items():
        if out[d][0][c]!=v['k']: bad+=1; print('MISMATCH',d,c,out[d][0][c],v['k'])
print('cells compared:',sum(len(res['cells'][d]) for d in out),'mismatches:',bad)
def grid(block,Ls):
    for snr in (-8,-16):
        print(f'\n{block} {snr} dB   L:   '+' '.join(f'{L:+.2f}' for L in Ls))
        for d in ('wsjtx','owsfz'):
            print(f'  {d:6} k/32:      '+' '.join(f'{out[d][0][f"{block}_L{L:+.2f}_S{snr}"]:5d}' for L in Ls))
late=[i*0.25 for i in range(25)]; early=[-3+i*0.25 for i in range(13)]
grid('LATE',late); grid('EARLY',early)
print('\nmedian reported DT of matched signals at cells near the edges (n):')
for d,blk,Ls in (('wsjtx','LATE',[2.0,2.25,2.5,2.75]),('owsfz','LATE',[2.0,2.25,2.5,2.75]),('wsjtx','EARLY',[-2.25,-2.0,-1.75,-1.0,0.0]),('owsfz','EARLY',[-2.0,-1.75,-1.0,0.0])):
    for snr in (-8,-16):
        print(' ',d,blk,snr,[(L,statistics.median(out[d][1][f"{blk}_L{L:+.2f}_S{snr}"]) if out[d][1][f"{blk}_L{L:+.2f}_S{snr}"] else None,len(out[d][1][f"{blk}_L{L:+.2f}_S{snr}"])) for L in Ls])
json.dump({d:dict(out[d][0]) for d in out},open(str(HERE/'recount_cells.json'),'w'),indent=0,sort_keys=True)
