# Q2 on-air extraction. Aggregates only; the daemon lines parsed carry no message text (HK-037).
import re, json, statistics, glob, sys, pathlib
HERE=pathlib.Path(__file__).resolve().parent
from datetime import datetime, timedelta, timezone
D='D:/Projects/claude/OpenWSFZ/artefacts/20260930_1930_endurance_run/daemon-logs/'
files=['openswfz-20260930T193054Z.log','openswfz-20260930T235959Z.log','openswfz-20261001T000000Z.log']
ts=re.compile(r'^(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d\.\d{3}) ([+-]\d\d):(\d\d) ')
cyc=re.compile(r'\] Cycle (\d\d:\d\d:\d\d): (\d+) decode\(s\) found, elapsed=(\d+) ms\.')
res=re.compile(r'\] Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) deadlineAbandoned=(\w+) containedException=(\w+) fittedSignals=(\d+)')
def utc(line):
    m=ts.match(line); off=timedelta(hours=int(m.group(3)),minutes=int(m.group(4)) * (1 if m.group(3)[0]!='-' else -1))
    return datetime.strptime(m.group(1)+' '+m.group(2),'%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc)-off
rows=[]; cur=None; n_cyc=0; unmatched=0
for fn in files:
    for ln,line in enumerate(open(D+fn,encoding='utf-8',errors='replace'),1):
        c=cyc.search(line)
        if c:
            n_cyc+=1; t=utc(line)
            lab=datetime.strptime(c.group(1),'%H:%M:%S').replace(year=t.year,month=t.month,day=t.day,tzinfo=timezone.utc)
            if lab>t: lab-=timedelta(days=1)
            if cur is not None and 'res' not in cur: unmatched+=1
            cur={'file':fn,'cyc_line':ln,'label':lab,'b1_log':t,'n_b1':int(c.group(2)),'b1_ms':int(c.group(3))}
            continue
        r=res.search(line)
        if r and cur is not None and 'res' not in cur:
            t=utc(line); cur['res']=dict(line=ln,log=t,n=int(r.group(1)),ms=int(r.group(2)),aband=r.group(3),exc=r.group(4),fit=int(r.group(5)))
            rows.append(cur)
print('Cycle lines',n_cyc,' residual lines paired',len(rows),' Cycle lines without a residual line',n_cyc-len(rows))
def pct(v,p):
    v=sorted(v); i=(len(v)-1)*p; lo=int(i); hi=min(lo+1,len(v)-1); return v[lo]+(v[hi]-v[lo])*(i-lo)
allms=[r['res']['ms'] for r in rows]
print('check vs report: n',len(allms),'p50',statistics.median(allms),'p95~',round(pct(allms,.95)),'max',max(allms),'resid decodes',sum(r['res']['n'] for r in rows),'mean',round(sum(r['res']['n'] for r in rows)/len(rows),2),'abandoned',sum(r['res']['aband']!='false' for r in rows),'exc',sum(r['res']['exc']!='false' for r in rows))
sel=[r for r in rows if r['res']['n']>=1]
print('cycles with >=1 residual decode:',len(sel),'of',len(rows))
for r in rows:
    slot_end=r['label']+timedelta(seconds=15)
    r['start_off']=(r['b1_log']-slot_end).total_seconds()-r['b1_ms']/1000     # decode start, s after reply-slot start
    r['T2_sum']=r['start_off']+r['b1_ms']/1000+r['res']['ms']/1000            # spec formula
    r['T2_log']=(r['res']['log']-slot_end).total_seconds()                    # log stamp of the residual line
    r['b1_pub']=(r['b1_log']-slot_end).total_seconds()
def q(v): return f"min {min(v):.3f} p5 {pct(v,.05):.3f} p50 {pct(v,.5):.3f} p95 {pct(v,.95):.3f} max {max(v):.3f}"
for name,key in (('decode-start offset (derived: Cycle-line stamp - elapsed - slot end)','start_off'),('batch-1 publish (Cycle-line stamp - slot end)','b1_pub'),('T2 = start + b1 + residual elapsed (spec formula)','T2_sum'),('T2 from residual-line stamp (check)','T2_log')):
    print(f'{name}: sel n={len(sel)}: '+q([r[key] for r in sel]))
print('max |T2_sum - T2_log| s:',max(abs(r['T2_sum']-r['T2_log']) for r in rows))
# edges from my independent analysis run
e=json.load(open(str(HERE/'analysis_result_engineer_rerun.json')))['edges']['wsjtx']
dtE={s:e[f'E50(snr={s})']['dt_edge'] for s in (-8,-16)}; LE={s:e[f'E50(snr={s})']['edge'] for s in (-8,-16)}
print('WSJT-X E50 L',LE,'DT_edge',dtE)
print('\nQ2 fraction of cycles-with->=1-residual-decode with T2+k-0.5 <= edge  (n=%d)'%len(sel))
out={}
for k in (0.0,0.5,1.0):
    for s in (-16,-8):
        for form,edge in (('DT_edge',dtE[s]),('L_edge',LE[s])):
            kcount=sum(1 for r in sel if r['T2_sum']+k-0.5<=edge)
            out[f'k={k} snr={s} {form}']=(kcount,len(sel))
            print(f'  k={k:3.1f}  SNR {s:3d}  vs {form}={edge:+.2f}:  {kcount}/{len(sel)} = {100*kcount/len(sel):.3f} %')
print('\nshortest T2 and the L it would give at k=0:',round(min(r['T2_sum'] for r in sel),3),round(min(r['T2_sum'] for r in sel)-0.5,3))
print('how many T2 values below 3.25 s (any k=0 L<=2.75 would need T2<=3.25):',sum(1 for r in sel if r['T2_sum']<=3.25))
# per hour-of-night stability of T2 median
import collections
by=collections.defaultdict(list)
for r in sel: by[r['label'].hour].append(r['T2_sum'])
print('median T2 by UTC hour:',{h:round(statistics.median(v),2) for h,v in sorted(by.items())})
print('FILE:LINE first/last cycle line:',rows[0]['file'],rows[0]['cyc_line'],rows[-1]['file'],rows[-1]['cyc_line'])
json.dump({'n_cycle_lines':n_cyc,'n_pairs':len(rows),'n_sel':len(sel),'fractions':{k:list(v) for k,v in out.items()}},open(str(HERE/'q2_result.json'),'w'),indent=1)
print('\nBY UTC HOUR: n, median T2, in-time share k=0 DT form')
for h,v in sorted(by.items()):
    print(f'  {h:02d}Z n={len(v):4d} med={statistics.median(v):.2f} in-time(k=0,DT)={sum(1 for t in v if t-0.5<=dtE[-8])}/{len(v)}')
