#!/usr/bin/env python3
"""LC-BASE: assembles qa/decoder-rebuild/lc-base-result.md from the prose template and the generated tables (aggregates only).

  python -I lc_base_assemble.py

Inputs: _qa-scratch/lc-base/template.md (the prose, with {{T..}} placeholders), tables.json (lc_base_report.py), the score files.
The key figures quoted in the prose are asserted against the score files first (a typo in the template stops the build).
"""
import json
import math
import os
import re

SC = r"D:\Projects\claude\_qa-scratch\lc-base"
OUT = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\decoder-rebuild\lc-base-result.md"
FILES = {"S40": "score_reuse_S40.json", "H40": "score_full_H40.json", "H20": "score_full_H20.json"}
BUILD = {("S40", "C"): "shipped `66b3ddf1` (DR-0's A6)", ("S40", "L"): "`fc4fb788` (DR-2e's L5)", ("H40", "C"): "main `546ad125`", ("H40", "L"): "main `546ad125`",
         ("H20", "C"): "main `546ad125`", ("H20", "L"): "main `546ad125`"}
THREADS = {"C": "classic, 8 threads", "L": "lean, 16 threads"}


def main():
    D = {k: json.load(open(os.path.join(SC, f))) for k, f in FILES.items()}
    # --- the prose's key numbers, asserted ------------------------------------------------------------------------------------------------------------------
    diff = {k: round(D[k]["arm"]["L"]["rate_pct"] - D[k]["arm"]["C"]["rate_pct"], 2) for k in D}
    assert diff == {"S40": -2.88, "H40": -1.02, "H20": 0.78}, diff
    cpu = {k: round(100 * (1 - D[k]["arm"]["L"]["cpu_s_per_cycle"] / D[k]["arm"]["C"]["cpu_s_per_cycle"])) for k in D}
    assert cpu == {"S40": 47, "H40": 30, "H20": 30}, cpu
    for k, (m, se, n) in {"S40": (-1.15, 0.18, 170), "H40": (-0.38, 0.14, 240), "H20": (0.30, 0.11, 240)}.items():
        g = [v["l"] - v["c"] for v in D[k]["per_cycle"].values()]
        mm = sum(g) / len(g)
        s = math.sqrt(sum((x - mm) ** 2 for x in g) / (len(g) - 1)) / math.sqrt(len(g))
        assert len(g) == n and round(mm, 2) == m and round(s, 2) == se, (k, mm, s)
    assert [sum(D[k]["overlap"].values()) for k in D] == [6773, 8983, 9154]
    assert [D[k]["overlap"]["neither"] for k in D] == [871, 986, 1358]
    assert [D[k]["overlap"]["c_only"] + D[k]["overlap"]["neither"] for k in D] == [1252, 1413, 1645]
    assert [D[k]["arm"]["L"]["last_p95_ms"] for k in D] == [2053, 2108, 2053] and [D[k]["arm"]["C"]["last_p95_ms"] for k in D] == [7332, 6527, 6162]
    assert all(D[k]["arm"][a]["abandoned_cycles"] == 0 for k in D for a in "CL")
    assert [D[k]["ours_only"]["L"]["same_text_decoded_elsewhere_by_wsjtx"] for k in D] == [14, 10, 0] and all(D[k]["ours_only"]["C"]["same_text_decoded_elsewhere_by_wsjtx"] == 0 for k in D)

    T = json.load(open(os.path.join(SC, "tables.json")))
    rows = ["| Slice | Arm | Engine | Build | Cycles | Wall (s) | Process CPU (s) | Exit code |", "|---|---|---|---|---:|---:|---:|---:|"]
    for k in D:
        for a in "CL":
            x = D[k]["arm"][a]
            rows.append("| %s | %s | %s | %s | %d | %s | %s | %s |" % (k if a == "C" else "", a, THREADS[a], BUILD[(k, a)], D[k]["cycles"], "{:,.1f}".format(x["wall_s"]),
                                                                  "{:,.1f}".format(x["cpu_total_s"]), x.get("rc", 0)))
    T["T6"] = "\n".join(rows)
    text = open(os.path.join(SC, "template.md"), encoding="utf-8").read()
    for key in re.findall(r"\{\{(\w+)\}\}", text):
        assert key in T, key
        text = text.replace("{{%s}}" % key, T[key])
    assert "{{" not in text
    open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    print("written", OUT, len(text.splitlines()), "lines")


if __name__ == "__main__":
    main()
