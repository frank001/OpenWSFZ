"""HK-039 mutation pass on the default-ON items commit 42f6a390 (D1 QSO queue capacity 14, D2 PSK Reporter excludes template rows).  Each mutant is applied to the scratch tree, the Daemon tests for the touched
area run, the tree restored.  KILLED = a test failed (good); SURVIVED = all green (a gap or an equivalent mutant, classified by hand).
Usage: python xc_mutate3.py check | run     (resumable: results in mutants3.json)"""
import json
import subprocess
import sys

TREE = r"D:\Projects\claude\_qa-scratch\xc-remedy-build\tree"
OUT = r"D:\Projects\claude\_qa-scratch\xc-remedy-build\mutants3.json"
FILTER = "FullyQualifiedName~XcBatch6|FullyQualifiedName~LateBatch|FullyQualifiedName~PskReporter"
L = "src/OpenWSFZ.Daemon/LateBatch.cs"
E = "src/OpenWSFZ.Daemon/PskReporter/PskReporterEngine.cs"
A = "src/OpenWSFZ.Abstractions/DecodeResult.cs"
S = "src/OpenWSFZ.Abstractions/IPskReporterStatusSource.cs"
M = [
 ("D01", L, "public const int BatchesPerCycleFallbackOn = 6;", "public const int BatchesPerCycleFallbackOn = 5;", "capacity 6 -> 5 batches (12)"),
 ("D02", L, "public const int BatchesPerCycleFallbackOn = 6;", "public const int BatchesPerCycleFallbackOn = 7;", "capacity 6 -> 7 batches (16)"),
 ("D03", L, "_fallbackOn() ? LateBatch.QsoChannelCapacityFallbackOn : LateBatch.QsoChannelCapacity", "LateBatch.QsoChannelCapacity", "flag ON still gets the OFF capacity"),
 ("D04", L, "_fallbackOn() ? LateBatch.QsoChannelCapacityFallbackOn : LateBatch.QsoChannelCapacity", "LateBatch.QsoChannelCapacityFallbackOn", "flag OFF gets the ON capacity"),
 ("D05", L, "public const int QsoChannelCapacityFallbackOn = BatchesPerCycleFallbackOn * QsoCyclesQueued + QsoChannelSpare;", "public const int QsoChannelCapacityFallbackOn = BatchesPerCycleFallbackOn * QsoCyclesQueued;", "no spare slots at the ON capacity"),
 ("D06", E, "if (r.Path == DecodeResult.PathTemplate) { _exTemplate++; _window.Template++; continue; }", "if (r.Path != DecodeResult.PathTemplate) { _exTemplate++; _window.Template++; continue; }", "template filter inverted"),
 ("D07", E, "if (r.Path == DecodeResult.PathTemplate) { _exTemplate++; _window.Template++; continue; }", "if (r.Path == DecodeResult.PathTemplate) { _exTemplate++; _window.Template++; }", "template counted but still uploaded"),
 ("D08", E, "if (r.Path == DecodeResult.PathTemplate) { _exTemplate++; _window.Template++; continue; }", "if (r.Path == DecodeResult.PathFallbackNotTemplate) { _exTemplate++; _window.Template++; continue; }", "(placeholder, BUILDFAIL expected)"),
 ("D09", E, "{ _exTemplate++; _window.Template++; continue; }", "{ _window.Template++; continue; }", "datagram-line template count not incremented"),
 ("D10", E, "{ _exTemplate++; _window.Template++; continue; }", "{ _exTemplate++; continue; }", "window template count not incremented"),
 ("D11", A, "public const int PathTemplate = 3;", "public const int PathTemplate = 4;", "constant 3 -> 4"),
 ("D12", E, "public PskReporterWindowCounts ToCounts() => new(Seen, Reported, Region, NoDial, Identity, Hashed, OwnCall, Dedup, Ap, Template);", "public PskReporterWindowCounts ToCounts() => new(Seen, Reported, Region, NoDial, Identity, Hashed, OwnCall, Dedup, Ap);", "status window omits template"),
 ("D13", E, "Template = _window.Template + _lastWindow.Template,", "Template = _window.Template,", "combined window drops the last window's template count"),
 ("D14", E, "_exDedup = _exDropped = _exAp = _exTemplate = 0;", "_exDedup = _exDropped = _exAp = 0;", "datagram line's template count never reset"),
 ("D15", E, "_identityRefused = _exAp = _exTemplate = 0;", "_identityRefused = _exAp = 0;", "template count not reset on engine reset"),
 ("D16", E, "dedup={Dedup}, ap={Ap}, template={Template}\",", "dedup={Dedup}, ap={Ap}\",", "window log line drops template"),
 ("D17", E, "nowUtc, datagram.Spots.Count, _exRegion, _exHashed, _exUnparseable, _exOwn, _exNoDial, _exDedup, _exAp, _exTemplate, _exDropped, _sequence);", "nowUtc, datagram.Spots.Count, _exRegion, _exHashed, _exUnparseable, _exOwn, _exNoDial, _exDedup, _exAp, _exDropped, _exTemplate, _sequence);", "datagram line: template and queue-dropped swapped"),
 ("D18", S, "int Dedup, int Ap = 0, int Template = 0);", "int Dedup, int Ap = 0, int Template = 1);", "template default 1"),
]


def sh(args):
    return subprocess.run(args, cwd=TREE, capture_output=True, text=True)


def read(f):
    p = TREE + "\\" + f.replace("/", "\\")
    return p, open(p, encoding="utf-8", newline="").read()


def main(mode):
    if mode == "check":
        bad = 0
        for mid, f, old, new, desc in M:
            p, src = read(f)
            o = old.replace("\n", "\r\n") if "\r\n" in src else old
            c = src.count(o)
            if c != 1:
                bad += 1
                print(mid, "ANCHOR COUNT", c, desc)
        print("check done, bad anchors:", bad)
        return
    res = {}
    try:
        res = json.load(open(OUT))
    except Exception:
        pass
    for mid, f, old, new, desc in M:
        if mid in res or mid == "D08":
            continue
        p, src = read(f)
        o = old.replace("\n", "\r\n") if "\r\n" in src else old
        n = new.replace("\n", "\r\n") if "\r\n" in src else new
        if src.count(o) != 1:
            res[mid] = dict(desc=desc, status="NOAPPLY", count=src.count(o))
            json.dump(res, open(OUT, "w"), indent=1)
            continue
        open(p, "w", encoding="utf-8", newline="").write(src.replace(o, n))
        try:
            r = sh(["dotnet", "test", "tests/OpenWSFZ.Daemon.Tests", "-c", "Release", "--filter", FILTER])
            txt = r.stdout + r.stderr
            if "error CS" in txt or "Build FAILED" in txt:
                st = "BUILDFAIL"
            elif "Failed!" in txt:
                st = "KILLED"
            elif "Passed!" in txt:
                st = "SURVIVED"
            else:
                st = "UNKNOWN"
            fails = [l.strip() for l in txt.splitlines() if l.strip().startswith("Failed ")][:4]
            res[mid] = dict(desc=desc, status=st, file=f, failing=fails)
        finally:
            open(p, "w", encoding="utf-8", newline="").write(src)
        json.dump(res, open(OUT, "w"), indent=1)
        print(mid, res[mid]["status"], desc, flush=True)
    print("DONE", sh(["git", "status", "--short"]).stdout or "tree clean", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
