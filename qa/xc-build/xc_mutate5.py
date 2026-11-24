"""HK-039 mutation pass on the threshold-freeze commit 4fe85cc5: the two shipped constants and their pin.  Each mutant is applied to the scratch tree, the CrossCycle tests run, the tree restored.
KILLED = a test failed (good); SURVIVED = all green.  Usage: python xc_mutate5.py run  (results in mutants5.json)"""
import json
import subprocess
import sys

TREE = r"D:\Projects\claude\_qa-scratch\xc-remedy-build\tree"
OUT = r"D:\Projects\claude\_qa-scratch\xc-remedy-build\mutants5.json"
F = "src/OpenWSFZ.Ft8/Ft8Decoder.cs"
TE = "internal const double CrossCyclePriorThresholdDefault = 3.076041980658299;"
TP = "internal const double CrossCyclePriorParityThresholdDefault = 2.2220253019230114;"
M = [
 ("T01", TE, TE.replace("3.076041980658299", "3.08"), "T_E default 3.08 (rounded)"),
 ("T02", TE, TE.replace("3.076041980658299", "3.076041980658298"), "T_E default off in the last digit"),
 ("T03", TE, TE.replace("3.076041980658299", "double.PositiveInfinity"), "T_E default back to +infinity"),
 ("T04", TP, TP.replace("2.2220253019230114", "2.23"), "T_P default 2.23 (rounded)"),
 ("T05", TP, TP.replace("2.2220253019230114", "2.2220253019230115"), "T_P default off in the last digit"),
 ("T06", TP, TP.replace("2.2220253019230114", "0.0"), "T_P default back to 0.0"),
 ("T07", TP, TP.replace("2.2220253019230114", "1.899"), "T_P default the desk value 1.899"),
]


def sh(args):
    return subprocess.run(args, cwd=TREE, capture_output=True, text=True)


def main():
    res = {}
    try:
        res = json.load(open(OUT))
    except Exception:
        pass
    p = TREE + "\\" + F.replace("/", "\\")
    for mid, old, new, desc in M:
        if mid in res:
            continue
        src = open(p, encoding="utf-8", newline="").read()
        o = old
        if src.count(o) != 1:
            res[mid] = dict(desc=desc, status="NOAPPLY", count=src.count(o))
            continue
        open(p, "w", encoding="utf-8", newline="").write(src.replace(o, new))
        try:
            r = sh(["dotnet", "test", "tests/OpenWSFZ.Ft8.Tests", "-c", "Release", "--filter", "FullyQualifiedName~CrossCycle"])
            txt = r.stdout + r.stderr
            st = "BUILDFAIL" if ("error CS" in txt or "Build FAILED" in txt) else "KILLED" if "Failed!" in txt else "SURVIVED" if "Passed!" in txt else "UNKNOWN"
            res[mid] = dict(desc=desc, status=st, failing=[l.strip()[:150] for l in txt.splitlines() if l.strip().startswith("Failed ")][:3])
        finally:
            open(p, "w", encoding="utf-8", newline="").write(src)
        json.dump(res, open(OUT, "w"), indent=1)
        print(mid, res[mid]["status"], desc, flush=True)
    print("DONE", sh(["git", "status", "--short"]).stdout or "tree clean", flush=True)


if __name__ == "__main__":
    main()
