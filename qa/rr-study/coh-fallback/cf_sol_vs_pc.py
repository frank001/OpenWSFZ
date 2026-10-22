"""COH-FALLBACK step 4: sol (FX-8350, 8 cores, Linux) full replay vs the PC replay, same 961 cycles, same selection, same build b8fc732e.
Descriptive comparison only (no pre-registered row). Usage: python -I cf_sol_vs_pc.py <sol_full dir with full0/ full1/> <pc step4 dir with off/ on/>
Reads numeric columns only; outcomes.csv carries no text (stamp,kind,seq,freq,dt,snr,path)."""
import csv, collections, sys

S, P = sys.argv[1], sys.argv[2]


def rows(p):
    return list(csv.DictReader(open(p, newline="")))


def outs(p):
    d = collections.defaultdict(collections.Counter)
    for r in csv.reader(open(p)):
        if len(r) >= 7:
            d[r[0]][(r[1], r[3], r[4], r[5], r[6])] += 1
    return d


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else None


for arm, sd, pd in (("OFF", "full0", "off"), ("ON", "full1", "on")):
    sr, pr = rows(f"{S}/{sd}/run.csv"), rows(f"{P}/{pd}/run.csv")
    so, po = outs(f"{S}/{sd}/outcomes.csv"), outs(f"{P}/{pd}/outcomes.csv")
    stamps = [r["stamp"] for r in sr]
    same = sum(1 for s in stamps if so[s] == po[s])
    print(f"== {arm}: cycles sol {len(sr)} pc {len(pr)}; exceptions sol {sum(1 for r in sr if r['exception'])}; outcomes (all kinds incl. path) identical to PC: {same}/{len(stamps)}")
    ab_s = sum(1 for r in rows(f"{S}/{sd}/abandon.csv") if r.get("abandoned") == "1")
    ab_p = sum(1 for r in rows(f"{P}/{pd}/abandon.csv") if r.get("abandoned") == "1")
    print("   residual-pass abandoned cycles: sol", ab_s, "pc", ab_p)
    for col in ("tb1_ms", "tb2_ms", "tb3_ms", "elapsed_ms"):
        sv = [float(r[col]) for r in sr if r[col] and float(r[col]) >= 0]
        pv = [float(r[col]) for r in pr if r[col] and float(r[col]) >= 0]
        print(f"   {col}: sol n={len(sv)} med={pct(sv, 50):.0f} p95={pct(sv, 95):.0f} max={max(sv):.0f} | pc med={pct(pv, 50):.0f} p95={pct(pv, 95):.0f}")
c, cp = rows(f"{S}/full1/coh.csv"), rows(f"{P}/on/coh.csv")
b4, b4p = [r for r in c if r["batch4_published"] == "1"], [r for r in cp if r["batch4_published"] == "1"]
t4, t4p = [float(r["batch4_publish_ms"]) for r in b4], [float(r["batch4_publish_ms"]) for r in b4p]
print("== ON batch 4: sol published", len(b4), "of", len(c), "| pc", len(b4p), "of", len(cp))
print(f"   publish ms from decode start: sol med {pct(t4, 50):.0f} p95 {pct(t4, 95):.0f} max {max(t4):.0f} (min margin to the 13 s budget {13000 - max(t4):.0f} ms) | pc med {pct(t4p, 50):.0f} p95 {pct(t4p, 95):.0f} max {max(t4p):.0f}")
fw = [float(r["fb_wall_ms"]) for r in c if float(r["fb_wall_ms"]) > 0]
fwp = [float(r["fb_wall_ms"]) for r in cp if float(r["fb_wall_ms"]) > 0]
print(f"   fallback wall ms: sol med {pct(fw, 50):.0f} p95 {pct(fw, 95):.0f} max {max(fw):.0f} | pc med {pct(fwp, 50):.0f} p95 {pct(fwp, 95):.0f} max {max(fwp):.0f}")
print("   fallback abandoned cycles: sol", sum(1 for r in c if int(r["abandoned"]) > 0), "pc", sum(1 for r in cp if int(r["abandoned"]) > 0))
oo, on = outs(f"{S}/full0/outcomes.csv"), outs(f"{S}/full1/outcomes.csv")
n123 = lambda cc: collections.Counter({k: v for k, v in cc.items() if k[0] in ("b1", "b2", "b3")})
diff = [r["stamp"] for r in rows(f"{S}/full1/run.csv") if n123(oo[r["stamp"]]) != n123(on[r["stamp"]])]
print("== sol ON vs OFF, batches 1-3 differing cycles:", len(diff), "(PC: 0)")
