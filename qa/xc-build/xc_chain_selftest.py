#!/usr/bin/env python3
"""Self-test of xc_chain_tools.py on synthetic files (no replay, no text, no PC load).  Every check has a case that must PASS and a case that must FAIL (HK-021/026)."""
import contextlib
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xc_chain_tools as T  # noqa: E402

FAILS = []


def expect(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def run(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="\n").write(text)


def xc_line(stamp, tl, pl, ts, sab=0, outcome="ran"):
    return f"{stamp},1,:|outcome={outcome}|priorsLive={pl}|priorsShadow=5|testedLive={tl}|testedShadow={ts}|detected=0|shadowDetected=0|abandoned=0|shadowAbandoned={sab}|published=0|threshold=Infinity\n"


def arm(d, n=4, late=("ran", "ran", "ran", "ran"), b6=False, text="x"):
    hdr = "run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n,b3_n,tb2_ms,tb3_ms,b4_n,tb4_ms,b5_n,tb5_ms\n"
    w(d + "/run.csv", hdr + "".join(f"r,FULL,S{i},{i},DEEP,5000.0,{20 + i},,1.0,{10 + i},2,1,1.0,1.0,3,1.0,1,1.0\n" for i in range(n)))
    w(d + "/matchedbatch.csv", "stamp,b\n" + "".join(f"S{i},1:{i}\n" for i in range(n)))
    w(d + "/testb.csv", "run,stamp,kind,band,n,corroborated\n" + "".join(f"r,S{i},b1,A,{3 + i},{1 + i}\nr,S{i},ws,A,{4 + i},0\n" for i in range(n))
      + ("".join(f"r,S{i},b6,A,0,0\nr,S{i},b6,B,0,0\n" for i in range(n)) if b6 else ""))
    w(d + "/outcomes.csv", "o\n" * 3)
    w(d + "/late.csv", "stamp,outcome\n" + "".join(f"S{i},{late[i]}\n" for i in range(n)))
    w(d + "/nc.tsv", "".join(f"S{i}\t1\t{text}\n" for i in range(n)))


with tempfile.TemporaryDirectory() as tmp:
    # --- te
    tr = tmp + "/tr"
    w(tr + "/xc.csv", "".join(xc_line(f"S{i}", 10, 12, 10) for i in range(200)))          # K = 10 tested, 12 priors; 2,000 shadow tests
    w(tr + "/probe.csv", "stamp,kind,s_e_star,prior_age_cycles,argmax_df_hz,argmax_dt_s\n"
      + "".join(f"S{i % 200},shadow,{1.0 + (i / 2000):.6f},1,0,0\n" for i in range(2000))
      + "".join(f"S{i % 200},live,{1.2 + (i / 2000):.6f},2,0,0\n" for i in range(2000)))
    rc = run(T.cmd_te, tr, tmp + "/te.json")
    te = json.load(open(tmp + "/te.json"))
    fa = 0.021 / 10
    expect("te: K = 10 (tested) and FA* = 0.0021", te["K"] == 10 and abs(te["FA_star"] - fa) < 1e-12)
    expect("te: exceedance at T_E is within FA*  (<= 4 of 2000) and T_E is the SMALLEST such threshold", te["exceed_at_T_E"] <= int(2000 * fa + 1e-9) and te["exceed_at_T_E"] == 4)
    expect("te: V-TR-N passes at 2,000 shadow tests (needs 1,429) -> rc 0", rc == 0 and te["V_TR_N"] and abs(te["n_needed"] - 3 / fa) < 1e-6)
    w(tr + "/xc.csv", "".join(xc_line(f"S{i}", 10, 12, 10) for i in range(200)))
    w(tr + "/probe.csv", "stamp,kind,s_e_star,prior_age_cycles,argmax_df_hz,argmax_dt_s\n" + "".join(f"S{i},shadow,{1.0 + i / 100:.4f},1,0,0\n" for i in range(100)))
    rc = run(T.cmd_te, tr, tmp + "/te2.json")
    expect("te: V-TR-N fails with 100 shadow tests -> rc 3", rc == 3)
    rc = run(T.cmd_te, tr, tmp + "/te3.json", dry=True)
    expect("te: --dry accepts the same -> rc 0", rc == 0)
    w(tr + "/probe.csv", "stamp,kind,s_e_star,prior_age_cycles,argmax_df_hz,argmax_dt_s\n")
    expect("te: no shadow tests -> rc 4", run(T.cmd_te, tr, tmp + "/te4.json") == 4)
    w(tr + "/probe.csv", "stamp,kind,s_e_star,prior_age_cycles,argmax_df_hz,argmax_dt_s\n" + "".join(f"S{i},shadow,{1.0 + i / 100:.4f},1,0,0\n" for i in range(100)))
    w(tr + "/xc.csv", "".join(xc_line(f"S{i}", 0, 0, 10, outcome="skipped-no-residual") for i in range(200)))
    expect("te: K = 0 (no live tests anywhere) -> rc 4, no division by zero", run(T.cmd_te, tr, tmp + "/te5.json", dry=True) == 4)
    w(tr + "/xc.csv", "".join(xc_line(f"S{i}", 6, 12, 10) for i in range(200)))
    run(T.cmd_te, tr, tmp + "/te6.json", dry=True)
    te6 = json.load(open(tmp + "/te6.json"))
    run(T.cmd_te, tr, tmp + "/te7.json", dry=True, k_source="priors")
    te7 = json.load(open(tmp + "/te7.json"))
    expect("te: --k-source priors uses priorsLive (12), tested uses testedLive (6), and both are recorded", te6["K"] == 6 and te7["K"] == 12 and te6["K_priors"] == 12 and te7["K_tested"] == 6)

    # --- voff
    a, b = tmp + "/new", tmp + "/ref"
    arm(a); arm(b)
    expect("voff: identical arms PASS", run(T.cmd_voff, a, b, tmp + "/v.json", a + "/nc.tsv", b + "/nc.tsv", None) == 0)
    # text differs in one row
    arm(a, text="y")
    expect("voff: one text row differs -> FAIL (rc 5)", run(T.cmd_voff, a, b, tmp + "/v.json", a + "/nc.tsv", b + "/nc.tsv", None) == 5)
    arm(a)
    w(a + "/matchedbatch.csv", "stamp,b\nS0,1:0\nS1,1:9\nS2,1:2\nS3,1:3\n")
    expect("voff: matchedbatch differs -> FAIL", run(T.cmd_voff, a, b, tmp + "/v.json") == 5)
    arm(a)
    t = open(a + "/run.csv").read().replace(",21,,1.0,11,2,1,", ",21,,1.0,11,2,1,", 1)
    w(a + "/run.csv", open(a + "/run.csv").read().replace(",DEEP,5000.0,22,", ",DEEP,5000.0,23,", 1))
    expect("voff: one decode count differs -> FAIL", run(T.cmd_voff, a, b, tmp + "/v.json") == 5)
    arm(a)
    w(a + "/run.csv", open(a + "/run.csv").read().replace("5000.0", "9999.0"))                                  # timing only
    expect("voff: timing columns differ -> still PASS (timing excluded)", run(T.cmd_voff, a, b, tmp + "/v.json") == 0)
    arm(a)
    w(tmp + "/st.txt", "S0 S1\n")
    w(a + "/nc.tsv", "S0\t1\tx\nS1\t1\tx\nS2\t1\tDIFFERENT\nS3\t1\tx\n")
    expect("voff: a difference OUTSIDE the listed stamps is ignored (first-100 text leg)", run(T.cmd_voff, a, b, tmp + "/v.json", a + "/nc.tsv", b + "/nc.tsv", tmp + "/st.txt") == 0)
    expect("voff: the same difference INSIDE the listed stamps fails", run(T.cmd_voff, a, b, tmp + "/v.json", a + "/nc.tsv", b + "/nc.tsv", (w(tmp + "/st2.txt", "S2\n") or tmp + "/st2.txt")) == 5)
    w(tmp + "/e.tsv", "")
    expect("voff: an empty text file is not a pass (0 rows)", run(T.cmd_voff, a, b, tmp + "/v.json", tmp + "/e.tsv", tmp + "/e.tsv", None) == 5)

    # --- testb.csv: the batch-6 rows of the new harness
    arm(a, b6=True); arm(b)
    expect("voff: all-zero b6 rows in the new testb.csv are excluded -> PASS (the dry run's real case)", run(T.cmd_voff, a, b, tmp + "/v.json") == 0)
    w(a + "/testb.csv", open(a + "/testb.csv").read().replace("r,S1,b6,A,0,0", "r,S1,b6,A,2,1"))
    expect("voff: a NON-zero b6 row with the stage OFF -> FAIL", run(T.cmd_voff, a, b, tmp + "/v.json") == 5)
    arm(a, b6=True)
    w(a + "/testb.csv", open(a + "/testb.csv").read().replace("r,S1,b1,A,4,2", "r,S1,b1,A,4,3"))
    expect("voff: a real b1 difference is still a FAIL when b6 rows are present", run(T.cmd_voff, a, b, tmp + "/v.json") == 5)

    # --- nccmp (the 100-cycle text leg: the new build's first-100 rows against the pre-change run)
    def nc(path, *rows):
        w(path, "".join(f"{s}\t1\t{t}\n" for s, t in rows))
    arm(a); arm(b)
    w(tmp + "/st3.txt", "S0 S1 S2\n")
    expect("nccmp: identical rows PASS", run(T.cmd_nccmp, a + "/nc.tsv", b + "/nc.tsv", tmp + "/st3.txt", tmp + "/n.json") == 0)
    nc(a + "/nc.tsv", ("S0", "x"), ("S1", "CHANGED"), ("S2", "x"), ("S3", "x"))
    expect("nccmp: a changed row inside the stamps FAILS", run(T.cmd_nccmp, a + "/nc.tsv", b + "/nc.tsv", tmp + "/st3.txt", tmp + "/n.json") == 5)
    nc(a + "/nc.tsv", ("S0", "x"), ("S1", "x"), ("S2", "x"), ("S3", "CHANGED-OUTSIDE"))
    expect("nccmp: a changed row outside the stamps is ignored", run(T.cmd_nccmp, a + "/nc.tsv", b + "/nc.tsv", tmp + "/st3.txt", tmp + "/n.json") == 0)
    nc(a + "/nc.tsv", ("S0", "x"), ("S2", "x"))
    expect("nccmp: a MISSING row inside the stamps FAILS", run(T.cmd_nccmp, a + "/nc.tsv", b + "/nc.tsv", tmp + "/st3.txt", tmp + "/n.json") == 5)

    # --- check
    arm(a)
    expect("check: a good arm is valid", run(T.cmd_check, a, a + "/nc.tsv", 4) == 0)
    expect("check: wrong row count is invalid", run(T.cmd_check, a, a + "/nc.tsv", 5) == 6)
    w(a + "/run.csv", open(a + "/run.csv").read().replace("DEEP,5000.0,20,,", "DEEP,5000.0,-1,InvalidOperationException,", 1))
    expect("check: an exception row and a negative decode count are invalid (the vacuous-run guard)", run(T.cmd_check, a, a + "/nc.tsv", 4) == 6)
    arm(a); w(a + "/nc.tsv", "")
    expect("check: empty nc.tsv is invalid", run(T.cmd_check, a, a + "/nc.tsv", 4) == 6)
    arm(a, late=("ran", "ran", "ran", "abandoned"))
    expect("check: late round abandoned in 1 of 4 cycles fails the 1 % capacity rule", run(T.cmd_check, a, a + "/nc.tsv", 4, 0.01) == 6)
    arm(a, late=("ran", "ran", "no-new", "ran"))
    expect("check: late round never abandoned passes the capacity rule", run(T.cmd_check, a, a + "/nc.tsv", 4, 0.01) == 0)
    w(a + "/xc.csv", "".join(xc_line(f"S{i}", 5, 5, 5) for i in range(3)))
    expect("check --xc: a missing counts line (3 of 4 cycles) is invalid", run(T.cmd_check, a, a + "/nc.tsv", 4, None, True) == 6)
    w(a + "/xc.csv", "".join(xc_line(f"S{i}", 5, 5, 5) for i in range(4)))
    expect("check --xc: a counts line for every cycle is valid", run(T.cmd_check, a, a + "/nc.tsv", 4, None, True) == 0)

print("xc_chain_selftest:", "FAILED " + str(FAILS) if FAILS else "ALL PASS")
sys.exit(1 if FAILS else 0)
