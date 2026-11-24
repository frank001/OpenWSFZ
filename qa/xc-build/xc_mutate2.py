"""HK-039 mutation pass on the XC remedy commit (Amendment 6: R14 veto, R15 parity gate, sink, log).  Each mutant is applied to a scratch tree, the CrossCycle tests run, the tree restored.
KILLED = a test failed (good); SURVIVED = all green (a test gap or an equivalent mutant, classified by hand); BUILDFAIL / NOAPPLY are reported, not counted.
Usage: python xc_mutate2.py check     (every anchor must occur exactly once)
       python xc_mutate2.py run       (resumable: results in mutants2.json)"""
import json
import subprocess
import sys

TREE = r"D:\Projects\claude\_qa-scratch\xc-review2\tree"
OUT = r"D:\Projects\claude\_qa-scratch\xc-review2\mutants2.json"
FILTER = "FullyQualifiedName~CrossCycle"
S = "src/OpenWSFZ.Ft8/CrossCyclePriorStore.cs"
T = "src/OpenWSFZ.Ft8/CrossCycleTemplateStage.cs"
D = "src/OpenWSFZ.Ft8/Ft8Decoder.cs"
X = "src/OpenWSFZ.Ft8/Dsp/CrossCycleTemplateDetector.cs"
RUNL = "CrossCycleTemplateStage.Run(liveTemplates, choice.Pcm, xcThreshold, workers, Expired, ct, xcParityThreshold, cycleDecodes, xcVetoOn)"
RUNS = "CrossCycleTemplateStage.Run(shadowTemplates, choice.Pcm, xcThreshold, workers, Expired, ct, xcParityThreshold, cycleDecodes, xcVetoOn)"
M = [
 ("R01", T, "ColocationHalfWidthHz + ColocationEdgeToleranceUnits", "6.25", "veto window 3.125 Hz -> 6.25 Hz"),
 ("R02", T, "ColocationHalfWidthHz + ColocationEdgeToleranceUnits", "2.9", "veto window 3.125 Hz -> 2.9 Hz"),
 ("R03", T, "ColocationHalfWidthS + ColocationEdgeToleranceUnits", "0.25", "veto window 0.2 s -> 0.25 s"),
 ("R04", T, "ColocationHalfWidthS + ColocationEdgeToleranceUnits", "0.15", "veto window 0.2 s -> 0.15 s"),
 ("R05", T, "ColocationEdgeToleranceUnits = 1e-9", "ColocationEdgeToleranceUnits = 0.0", "edge tolerance removed"),
 ("R06", T, "if (string.Equals(d.Text, text, StringComparison.Ordinal)) continue;", "", "the same text vetoes"),
 ("R07", T, "if (cycleDecodes is null) return false;", "if (cycleDecodes is null) return true;", "no decode list vetoes"),
 ("R08", T, "double argmaxDt = r.Dt + PublishedMinusWsjtxDtS;", "double argmaxDt = r.Dt;", "argmax not converted back to our dt"),
 ("R09", T, "bool vetoRejected = clearsE && !parityRejected && applyVeto && vetoed;", "bool vetoRejected = clearsE && !parityRejected && vetoed;", "veto applied although the setting is off"),
 ("R10", T, "bool parityRejected = clearsE && !(r.SP >= parityThreshold);", "bool parityRejected = clearsE && !(r.SStar >= parityThreshold);", "T_P tested on S_E* instead of S_P"),
 ("R11", T, "bool parityRejected = clearsE && !(r.SP >= parityThreshold);", "bool parityRejected = clearsE && (r.SP >= parityThreshold);", "parity gate flipped"),
 ("R12", T, "bool parityRejected = clearsE && !(r.SP >= parityThreshold);", "bool parityRejected = false;", "parity gate never rejects"),
 ("R13", T, "bool detected = clearsE && !parityRejected && !vetoRejected;", "bool detected = clearsE && !vetoRejected;", "a parity-rejected template is still detected"),
 ("R14", T, "bool detected = clearsE && !parityRejected && !vetoRejected;", "bool detected = clearsE && !parityRejected;", "a vetoed template is still detected"),
 ("R15", T, "bool vetoRejected = clearsE && !parityRejected && applyVeto && vetoed;", "bool vetoRejected = clearsE && applyVeto && vetoed;", "veto and parity counted together (partition broken)"),
 ("R16", T, "bool vetoed = IsVetoed(t.Text, r.FreqHz, argmaxDt, cycleDecodes);", "bool vetoed = false;", "vetoed flag never computed"),
 ("R17", T, "if (o.ParityRejected) parityCount++;", "", "parity-rejected not counted"),
 ("R18", T, "if (o.VetoRejected) vetoCount++;", "", "veto-rejected not counted"),
 ("R19", T, "c.AgeCycles, c.Prior.Batch));", "c.AgeCycles));", "template loses the prior's batch"),
 ("R20", X, "ParityBlockFirstSymbol = 43, ParityBlockLastSymbol = 71;", "ParityBlockFirstSymbol = 42, ParityBlockLastSymbol = 71;", "block 2 starts at symbol 42"),
 ("R21", X, "ParityBlockFirstSymbol = 43, ParityBlockLastSymbol = 71;", "ParityBlockFirstSymbol = 43, ParityBlockLastSymbol = 72;", "block 2 ends at symbol 72"),
 ("R22", X, "parityRow[k] /= ParityBlockSymbols;", "parityRow[k] /= SymbolCount;", "S_P divided by 79"),
 ("R23", X, "bool inParityBlock = sym >= ParityBlockFirstSymbol && sym <= ParityBlockLastSymbol;", "bool inParityBlock = sym > ParityBlockFirstSymbol && sym <= ParityBlockLastSymbol;", "symbol 43 left out of S_P"),
 ("R24", X, "parityGrid[bestF * DtSteps + bestK]", "parityGrid[0]", "S_P not read at the S_E* argmax"),
 ("R25", X, "parityRatioSum[k] += ratio;", "parityRatioSum[k] += 1.0;", "S_P accumulates 1 instead of the ratio"),
 ("R26", X, "for (int k = ParityBlockFirstSymbol; k <= ParityBlockLastSymbol; k++) sum += Ratio", "for (int k = ParityBlockFirstSymbol; k < ParityBlockLastSymbol; k++) sum += Ratio", "ParityStatisticFromPowers drops symbol 71"),
 ("R27", D, "bool xcVetoOn      = xcOn && _crossCycleColocationVeto;", "bool xcVetoOn      = xcOn;", "veto setting ignored by the decoder"),
 ("R28", D, "internal const bool CrossCyclePriorColocationVetoDefault = true;", "internal const bool CrossCyclePriorColocationVetoDefault = false;", "veto default OFF"),
 ("R29", D, "internal const double CrossCyclePriorParityThresholdDefault = 0.0;", "internal const double CrossCyclePriorParityThresholdDefault = 1.0;", "T_P default 1.0"),
 ("R30", D, "double xcParityThreshold = xcOn ? Volatile.Read(ref _crossCyclePriorParityThreshold) : CrossCyclePriorParityThresholdDefault;", "double xcParityThreshold = CrossCyclePriorParityThresholdDefault;", "set T_P ignored"),
 ("R31", D, RUNL, RUNL.replace("cycleDecodes", "null"), "live run gets no cycle decodes"),
 ("R32", D, RUNS, RUNS.replace("cycleDecodes", "null"), "shadow run gets no cycle decodes"),
 ("R33", D, "parityRejectedLive = live.ParityRejected; vetoedLive = live.VetoRejected;", "parityRejectedLive = 0; vetoedLive = 0;", "live counts not logged"),
 ("R34", D, "parityRejectedShadow = shadow.ParityRejected; vetoedShadow = shadow.VetoRejected;", "parityRejectedShadow = 0; vetoedShadow = 0;", "shadow counts not logged"),
 ("R35", D, "o.SP, t.FreqHz, t.Dt, t.Batch, o.Vetoed)", "0.0, t.FreqHz, t.Dt, t.Batch, o.Vetoed)", "sink S_P zero"),
 ("R36", D, "o.SP, t.FreqHz, t.Dt, t.Batch, o.Vetoed)", "o.SP, 0.0, 0.0, 0, o.Vetoed)", "sink prior position and batch zero"),
 ("R37", D, "o.SP, t.FreqHz, t.Dt, t.Batch, o.Vetoed)", "o.SP, t.FreqHz, t.Dt, t.Batch, false)", "sink vetoed flag false"),
 ("R38", S, "lock (_lock) return _byCycle.TryGetValue(_currentSlot, out var list) ? [.. list] : [];", "return [];", "CurrentCycleDecodes empty"),
 ("R39", D, "vetoedLive, vetoedShadow, parityRejectedLive, parityRejectedShadow, xcVetoOn, xcParityThreshold,", "vetoedShadow, vetoedLive, parityRejectedLive, parityRejectedShadow, xcVetoOn, xcParityThreshold,", "log live and shadow veto counts swapped"),
 ("R40", D, "=> _crossCycleColocationVeto = enabled;", "=> _crossCycleColocationVeto = true;", "veto setter ignores false"),
 ("R41", D, "=> Volatile.Write(ref _crossCyclePriorParityThreshold, threshold);", "=> Volatile.Write(ref _crossCyclePriorParityThreshold, 0.0);", "T_P setter ignores the value"),
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
        if mid in res:
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
            r = sh(["dotnet", "test", "tests/OpenWSFZ.Ft8.Tests", "-c", "Release", "--filter", FILTER])
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
