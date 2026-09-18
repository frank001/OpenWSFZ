"""ARCHITECT verification of ROW 0k's baseline-mismatch bias direction (spec Sec.16.1).
Numbers only."""
import numpy as np
real =[0.8607,0.7440,0.5129,0.1643,0.1205]   # QA, n=111
bench=[0.7684,0.6769,0.4617,0.1586,0.1234]   # QA, n=150/dose, B_pre=1.5
dr=real[0]-real[-1]; db=bench[0]-bench[-1]
print("AS RUN: D_real=%.4f D_bench=%.4f ratio=%.4f (bar 0.20)"%(dr,db,abs(dr-db)/db))
for base in (0.8607,0.8400,0.8000,0.7684,0.7500):
    d=base-bench[-1]
    print("  bench baseline %.4f -> D_bench=%.4f ratio=%.4f %s"%(
        base,d,abs(dr-d)/d,"PASS" if abs(dr-d)/d<=0.20 else "FAIL"))
print("=> matched baseline gives ratio ~0.004; the mismatch made K1 HARDER, not easier.")
