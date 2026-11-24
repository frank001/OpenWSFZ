import json, os, sys
HERE = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\xc-template"
sys.path.insert(0, HERE)
OUT = r"D:\Projects\claude\_qa-scratch\xc-review\xcmp"

def main():
    import xt_score as S
    t = json.load(open(r"D:/Projects/claude/_qa-scratch/xc-template/frozen/xt_tasks.json"))
    resid = t["resid"]
    e1 = [r for r in t["E1"] if r["tones"] is not None]
    nl = t["NL"]
    # 100 E1 + 100 null, evenly spaced (deterministic, no random draw)
    pick_e = [e1[int(i * len(e1) / 100)] for i in range(100)]
    pick_n = [nl[int(i * len(nl) / 100)] for i in range(100)]
    tasks, meta = [], []
    for kind, rows in (("E1", pick_e), ("NL", pick_n)):
        for r in rows:
            p = resid[r["stamp"]]
            tasks.append({"path": p, "f": r["centre"][0], "dt": r["centre"][1], "tones": r["tones"], "own": None})
            meta.append((kind, r["stamp"]))
    assert len(tasks) == 200
    res = S.run_tasks(tasks, workers=8)
    os.makedirs(OUT, exist_ok=True)
    with open(OUT + "/pairs.tsv", "w") as f:
        for tk in tasks:
            f.write("\t".join([tk["path"], repr(float(tk["f"])), repr(float(tk["dt"])), ",".join(str(x) for x in tk["tones"])]) + "\n")
    json.dump([{"kind": m[0], "stamp": m[1], "S": r["S"], "af": r["af"], "adt": r["adt"]} for m, r in zip(meta, res)], open(OUT + "/desk.json", "w"))
    print("desk done", len(res), "S range", min(r["S"] for r in res), max(r["S"] for r in res))

if __name__ == "__main__":
    main()
