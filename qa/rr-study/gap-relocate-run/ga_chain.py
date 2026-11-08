import re, csv, collections, sys
sys.path.insert(0,'.')
import ga_analyze as A
R=A.R
def logsum(arm,key):
    t=open(f"{R}/raw/{arm}/log.log",encoding="utf-8",errors="replace").read()
    return sum(int(x) for x in re.findall(key+r"=(\d+)",t))
res={}
for arm in ("off","on"):
    runs=list(csv.DictReader(open(f"{R}/raw/{arm}/run.csv")))
    res[arm]={"published_log_sum":logsum(arm,r"(?<![A-Za-z])published"),"b4_n_run_csv":sum(int(r["b4_n"]) for r in runs),
              "ungated_log_sum":logsum(arm,"ungated") if arm=="on" else 0}
off=A.load_nc("off"); on=A.load_nc("on")
tot=dict(on_b4=0,off_b4=0,same_text_same_freq=0,same_text_moved_freq=0,new_text=0,new_text_hashed=0,off_rows_not_in_on=0)
for s in set(off)|set(on):
    o=[(f,t) for k,f,t in off.get(s,[]) if k==4]; n=[(f,t) for k,f,t in on.get(s,[]) if k==4]
    ot={t for _,t in o}; oset=set(o)
    tot["on_b4"]+=len(n); tot["off_b4"]+=len(o)
    for f,t in n:
        if (f,t) in oset: tot["same_text_same_freq"]+=1
        elif t in ot: tot["same_text_moved_freq"]+=1
        else:
            tot["new_text"]+=1; tot["new_text_hashed"]+= bool(A.HASHED.search(t))
    nset=set(n); nt={t for _,t in n}
    tot["off_rows_not_in_on"]+=sum(1 for f,t in o if (f,t) not in nset)
res["rows"]=tot
print(res)
