"""HK-039 mutation pass on the QSO template-batch commit 3add5442 (Q1 answerer Idle, Q2 caller WaitAnswer, Q4 the new outcome and token), plus a re-run of the three observability survivors of 42f6a390 (D14, D15, D18)
against the Developer's tests-only commit.  Each mutant is applied to the scratch tree, the tests for the touched area run, the tree restored.
KILLED = a test failed (good); SURVIVED = all green (a gap or an equivalent mutant, classified by hand).
Usage: python xc_mutate4.py check | run     (resumable: results in mutants4.json)"""
import json
import subprocess
import sys

TREE = r"D:\Projects\claude\_qa-scratch\xc-remedy-build\tree"
OUT = r"D:\Projects\claude\_qa-scratch\xc-remedy-build\mutants4.json"
DAEMON = ("tests/OpenWSFZ.Daemon.Tests", "FullyQualifiedName~XcTemplateBatchQso|FullyQualifiedName~XcBatch6|FullyQualifiedName~LateBatch|FullyQualifiedName~PskReporter")
WEB = ("tests/OpenWSFZ.Web.Tests", "FullyQualifiedName~PskReporter")
A = "src/OpenWSFZ.Daemon/QsoAnswererService.cs"
C = "src/OpenWSFZ.Daemon/QsoCallerService.cs"
L = "src/OpenWSFZ.Daemon/LateBatch.cs"
E = "src/OpenWSFZ.Daemon/PskReporter/PskReporterEngine.cs"
S = "src/OpenWSFZ.Abstractions/IPskReporterStatusSource.cs"
SKIP = "if (r.Path == DecodeResult.PathTemplate) { skippedTemplate = true; continue; }"
M = [
 ("Q01", A, SKIP, SKIP.replace("==", "!="), DAEMON, "answerer: template filter inverted"),
 ("Q02", A, SKIP, "", DAEMON, "answerer: template skip removed"),
 ("Q03", A, SKIP, "if (r.Path == DecodeResult.PathTemplate) { skippedTemplate = true; }", DAEMON, "answerer: template counted but still answered"),
 ("Q04", A, "return skippedTemplate ? LateOutcome.IgnoredTemplate : LateOutcome.NoMatch;", "return LateOutcome.NoMatch;", DAEMON, "answerer: skip not counted"),
 ("Q05", A, "return skippedTemplate ? LateOutcome.IgnoredTemplate : LateOutcome.NoMatch;", "return LateOutcome.IgnoredTemplate;", DAEMON, "answerer: always counted"),
 ("Q06", A, SKIP, SKIP.replace("DecodeResult.PathTemplate", "2"), DAEMON, "answerer: skips fallback rows (path 2) instead of template rows"),
 ("Q07", A, SKIP, SKIP.replace("continue; }", "return LateOutcome.IgnoredTemplate; }"), DAEMON, "answerer: a template row ends the scan (a later ordinary CQ is not answered)"),
 ("Q08", C, SKIP, "", DAEMON, "caller: template skip removed"),
 ("Q09", C, SKIP, SKIP.replace("==", "!="), DAEMON, "caller: template filter inverted"),
 ("Q10", C, "if (skippedTemplate) return LateOutcome.IgnoredTemplate;", "", DAEMON, "caller: skip not counted"),
 ("Q11", C, "if (skippedTemplate) return LateOutcome.IgnoredTemplate;", "if (skippedTemplate) return LateOutcome.NoMatch;", DAEMON, "caller: skip returns no-match"),
 ("Q12", C, SKIP, SKIP.replace("continue; }", "return LateOutcome.IgnoredTemplate; }"), DAEMON, "caller: a template row ends the scan (a later ordinary responder is not engaged)"),
 ("Q13", L, 'LateOutcome.IgnoredTemplate  => "ignored-template",', 'LateOutcome.IgnoredTemplate  => "ignored-stale",', DAEMON, "token collides with ignored-stale"),
 ("Q14", L, 'LateOutcome.IgnoredTemplate  => "ignored-template",', 'LateOutcome.IgnoredTemplate  => "ignored_template",', DAEMON, "token spelling changed"),
 ("D14", E, "_exDedup = _exDropped = _exAp = _exTemplate = 0;", "_exDedup = _exDropped = _exAp = 0;", DAEMON, "(42f6a390 survivor) datagram template count never reset"),
 ("D15", E, "_identityRefused = _exAp = _exTemplate = 0;", "_identityRefused = _exAp = 0;", DAEMON, "(42f6a390 survivor) template count not reset on engine reset"),
 ("D18", S, "int Dedup, int Ap = 0, int Template = 0);", "int Dedup, int Ap = 0, int Template = 1);", WEB, "(42f6a390 survivor) template default 1"),
]


def sh(args):
    return subprocess.run(args, cwd=TREE, capture_output=True, text=True)


def read(f):
    p = TREE + "\\" + f.replace("/", "\\")
    return p, open(p, encoding="utf-8", newline="").read()


def main(mode):
    if mode == "check":
        bad = 0
        for mid, f, old, new, tp, desc in M:
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
    for mid, f, old, new, tp, desc in M:
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
            r = sh(["dotnet", "test", tp[0], "-c", "Release", "--filter", tp[1]])
            txt = r.stdout + r.stderr
            if "error CS" in txt or "error CA" in txt or "Build FAILED" in txt:
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
