import subprocess, sys, json, time
TREE = r"D:\Projects\claude\_qa-scratch\xc-review\tree"
OUT = r"D:\Projects\claude\_qa-scratch\xc-review\mutants.json"
FILTER = "FullyQualifiedName~CrossCycle"
S = "src/OpenWSFZ.Ft8/CrossCyclePriorStore.cs"
T = "src/OpenWSFZ.Ft8/CrossCycleTemplateStage.cs"
D = "src/OpenWSFZ.Ft8/Ft8Decoder.cs"
M = [
 ("M01", S, "(cycleStart.Ticks + period / 2) / period", "cycleStart.Ticks / period", "slot rounding to nearest -> floor"),
 ("M02", S, "RetainedCycles = 6;", "RetainedCycles = 5;", "retain 6 -> 5 cycles"),
 ("M03", S, "key < slot - RetainedCycles ||", "key <= slot - RetainedCycles ||", "off-by-one at 90 s eviction"),
 ("M04", S, " || key > slot) _byCycle", ") _byCycle", "future-slot eviction removed"),
 ("M05", S, "_byCycle.Clear();", "_ = 0;", "no clear on band change"),
 ("M06", S, "LiveAges = [2, 4, 6]", "LiveAges = [2, 4, 5]", "live age 6 -> 5"),
 ("M07", S, "ShadowAges = [1, 3, 5]", "ShadowAges = [1, 3, 4]", "shadow age 5 -> 4"),
 ("M08", S, "if (seen.Add(prior.Text)) result.Add(new Candidate(prior, age));", "{ seen.Add(prior.Text); result.Add(new Candidate(prior, age)); }", "no text dedup"),
 ("M09", T, "if (publishedThisCycle.Contains(text))", "if (publishedThisCycle.Count < 0)", "already-published exclusion off"),
 ("M10", T, "if (text.Contains('<'))", "if (text.Length < 0)", "hashed exclusion off"),
 ("M11", T, "if (tones.Length != CrossCycleTemplateDetector.SymbolCount) { refused++; continue; }", "", "tone-length guard removed"),
 ("M12", T, "catch (Exception) { refused++; continue; }", "catch (Exception) { continue; }", "refused not counted"),
 ("M13", T, "r.SStar >= threshold", "r.SStar > threshold", ">= -> >"),
 ("M14", T, "t.Dt - PublishedMinusWsjtxDtS, t.Tones", "t.Dt, t.Tones", "dt not converted in"),
 ("M15", T, "r.Dt + PublishedMinusWsjtxDtS, detected", "r.Dt, detected", "dt not converted back"),
 ("M16", T, "if (budgetExpired()) return;", "", "budget check removed"),
 ("M17", T, "n - tested)", "0)", "abandoned always 0"),
 ("M18", T, "if (i >= n) return;", "if (i >= n + 1) return;", "index bound off by one"),
 ("M19", D, "bool xcOn          = cohOn && _crossCyclePrior;", "bool xcOn          = _crossCyclePrior;", "xcOn ignores fallback"),
 ("M20", D, "if (xcBatch > 0 && xcPublished is not null)", "if (xcBatch >= 0 && xcPublished is not null)", "batch 6 enters store"),
 ("M21", D, "xcBatch: 3);", "xcBatch: 0);", "batch 3 not stored"),
 ("M22", D, "xcBatch: LateRoundBatch);", "xcBatch: 0);", "batch 5 not stored"),
 ("M23", D, "xcBatch: batchNumber);", "xcBatch: 0);", "batch 4 not stored"),
 ("M24", D, "MapNative(newFromResidual, PathResidual, xcBatch: 2)", "MapNative(newFromResidual, PathResidual, xcBatch: 0)", "batch 2 not stored"),
 ("M25", D, "MapNative(native, xcBatch: 1)", "MapNative(native, xcBatch: 0)", "batch 1 not stored"),
 ("M26", D, "bool xcShadowOn    = xcOn && _crossCyclePriorShadow;", "bool xcShadowOn    = _crossCyclePriorShadow;", "shadow without prior on"),
 ("M27", D, "Candidates(shadow: true)", "Candidates(shadow: false)", "shadow uses live priors"),
 ("M28", D, "FreqHz = (int)Math.Round(o.FreqHz)", "FreqHz = (int)o.FreqHz", "freq truncated not rounded"),
 ("M29", D, "if (batch6.Count > 0)\n", "if (batch6.Count >= 0)\n", "empty batch 6 published"),
 ("M30", D, "if (!choice.IsResidual) { outcome = XcOutcomeNoResidual; return; }", "", "residual guard removed"),
 ("M31", D, "SubtractionCycleBudget - CoherentFallbackPublishReserve;", "SubtractionCycleBudget;", "publish reserve dropped"),
 ("M32", D, "MapNative(natives.ToArray(), PathTemplate)", "MapNative(natives.ToArray(), PathResidual)", "wrong provenance tag"),
 ("M33", D, "if (!o.Tested) continue;\n                var t = run.Templates[i];", "var t = run.Templates[i];", "probe reports untested"),
 ("M34", D, "catch (Exception ex) { _logger?.LogWarning(ex, \"Cycle {Time}: the cross-cycle diagnostic sink", "catch (InvalidCastException ex) { _logger?.LogWarning(ex, \"Cycle {Time}: the cross-cycle diagnostic sink", "probe exception not swallowed"),
 ("M35", D, "if (xcShadowOn && live is not null)", "if (xcShadowOn)", "shadow runs when live failed"),
 ("M36", D, "o.FreqHz - t.FreqHz, o.Dt - t.Dt", "o.FreqHz, o.Dt", "probe offsets absolute"),
 ("M37", D, "if (xcOn) _crossCycleStore.BeginCycle(cycleStart, currentBand);", "_crossCycleStore.BeginCycle(cycleStart, currentBand);", "store written while OFF"),
 ("M38", D, "xcOn ? Volatile.Read(ref _crossCyclePriorThreshold) : CrossCyclePriorThresholdDefault", "CrossCyclePriorThresholdDefault", "set threshold ignored"),
]

def sh(args):
    return subprocess.run(args, cwd=TREE, capture_output=True, text=True)

res = {}
try: res = json.load(open(OUT))
except Exception: pass
for mid, f, old, new, desc in M:
    if mid in res: continue
    p = TREE + "\\" + f.replace("/", "\\")
    src = open(p, encoding="utf-8", newline="").read()
    o = old.replace("\n", "\r\n") if "\r\n" in src else old
    n = new.replace("\n", "\r\n") if "\r\n" in src else new
    if src.count(o) != 1:
        res[mid] = dict(desc=desc, status="NOAPPLY", count=src.count(o)); json.dump(res, open(OUT, "w"), indent=1); continue
    open(p, "w", encoding="utf-8", newline="").write(src.replace(o, n))
    try:
        r = sh(["dotnet", "test", "tests/OpenWSFZ.Ft8.Tests", "-c", "Release", "--filter", FILTER])
        txt = r.stdout + r.stderr
        if "error CS" in txt or "Build FAILED" in txt: st = "BUILDFAIL"
        elif "Failed!" in txt: st = "KILLED"
        elif "Passed!" in txt: st = "SURVIVED"
        else: st = "UNKNOWN"
        fails = [l.strip() for l in txt.splitlines() if l.strip().startswith("Failed ")][:4]
        res[mid] = dict(desc=desc, status=st, file=f, failing=fails)
    finally:
        open(p, "w", encoding="utf-8", newline="").write(src)
    json.dump(res, open(OUT, "w"), indent=1)
    print(mid, res[mid]["status"], desc, flush=True)
print("DONE", sh(["git", "status", "--short"]).stdout or "tree clean", flush=True)
