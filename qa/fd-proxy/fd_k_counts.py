import collections, re, sys
ARM="D:/Projects/claude/_qa-scratch/xc-live-free/ON/nc.tsv"
ALL="D:/Projects/claude/OpenWSFZ/artefacts/20261114_2312_endurance_run-gathered/wsjt-x/ALL.TXT"
CALL=re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z](/[A-Z0-9]{1,4})?$")
def judge(text):
    t=text.split()
    if not t or any("<" in x for x in t) or ";" in text: return None
    if t[0]=="CQ":
        c=[x for x in t[1:] if CALL.match(x)]
        return "CQ" if len(c)==1 and len(t)<=4 else None
    if len(t)>=2 and CALL.match(t[0]) and CALL.match(t[1]) and len(t)<=3: return "STD"
    return None
def band(s): return "<=-18" if s<=-18 else "-17..-10" if s<=-10 else ">=-9"
W=collections.defaultdict(list); nW=0
for ln in open(ALL,encoding="utf-8",errors="replace"):
    f=ln.split()
    if len(f)<8 or f[2]!="Rx" or f[3]!="FT8": continue
    try: W[f[0]].append((int(f[4]),int(f[6])," ".join(f[7:]).strip()))
    except ValueError: continue
    nW+=1
rows=[]; cols=collections.Counter(); stamps=set()
for ln in open(ARM,encoding="utf-8",errors="replace"):
    p=ln.rstrip("\n").split("\t")
    if len(p)<11: continue
    cols[len(p)]+=1; stamps.add(p[0])
    rows.append(dict(st=p[0],k=int(p[1]),m=int(p[2]),f=int(p[3]),snr=int(p[5]),tx=p[10].strip(),ap=int(p[11]) if len(p)>11 else None))
order=sorted(stamps); pil=set(order[:283])
print("WSJT-X rows in E",nW,"stamps with E",len(W)); print("nc cols",dict(cols)); print("rows",len(rows),"cycles",len(stamps),"pilot cycles",len(pil))
def buried(r):
    for (s,f,t) in W.get(r["st"],[]):
        if abs(f-r["f"])<50 and s>=r["snr"]:
            if r["m"] and t==r["tx"] and abs(f-r["f"])<=10: continue   # own matched row excluded
            return True
    return False
print("per kind: n, matched, unconfirmed, judgeable-unconf, ap-tagged(unconf)")
for k in range(1,7):
    R=[r for r in rows if r["k"]==k]; U=[r for r in R if not r["m"]]
    ju=[r for r in U if judge(r["tx"])]; ap=[r for r in U if r["ap"]==1]
    print(k,len(R),sum(r["m"] for r in R),len(U),len(ju),(len(ap) if R and R[0]["ap"] is not None else "no-col"))
def tab(sel,name):
    c=collections.Counter()
    for r in sel: c[(band(r["snr"]),"buried" if buried(r) else "isolated")]+=1
    print(name,"n",len(sel),dict(sorted(c.items())))
for nm,ks in (("batch4+5",(4,5)),("batch2-6",(2,3,4,5,6))):
    Q=[r for r in rows if r["k"] in ks and not r["m"] and judge(r["tx"])]
    P=[r for r in rows if r["k"] in ks and r["m"] and judge(r["tx"])]
    tab(Q,nm+" Q judgeable unconfirmed"); tab(P,nm+" P judgeable confirmed")
    Qp=[r for r in Q if r["st"] in pil]; Pp=[r for r in P if r["st"] in pil]
    print(nm,"pilot-cycle Q",len(Qp),"P",len(Pp))
    iso=[r for r in Q if not buried(r)]; print(nm,"isolated unconfirmed judgeable",len(iso),"outside pilot",sum(1 for r in iso if r["st"] not in pil))
for nm,ks in (("batch2-5 (no b6)",(2,3,4,5)),("batch6 only",(6,))):
    Q=[r for r in rows if r["k"] in ks and not r["m"] and judge(r["tx"])]
    iso=[r for r in Q if not buried(r)]; print(nm,"judgeable unconf",len(Q),"isolated",len(iso),"outside pilot",sum(1 for r in iso if r["st"] not in pil))
