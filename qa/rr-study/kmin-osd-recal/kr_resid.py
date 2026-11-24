# KMIN-OSD-RECAL supplementary wiring probe (QA, descriptive, NOT the registered V-WIRE): the same native check as kr_wire.py on 10 STORED residual (R2) buffers of the 20260925_2010 night (SUB-COVER set). Counts only.
import ctypes as C, hashlib, os, sys, json
import numpy as np
RR='D:/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study'
sys.path.insert(0,RR+'/coh-fallback'); sys.path.insert(0,RR+'/gap-relocate-run')
import cf_native as N
PIN="1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
dll='D:/Projects/claude/_qa-scratch/kmin-osd-recal/bin/libft8.dll'
assert hashlib.sha256(open(dll,'rb').read()).hexdigest()==PIN
nat=N.Native(dll,PIN,expected_shim=20260071,nhard=24); d=nat.dll
d.ft8_get_last_candidate_counts.restype=C.c_int; d.ft8_get_last_candidate_counts.argtypes=[C.POINTER(C.c_int),C.c_int]
d.ft8_set_decode_params.argtypes=[C.c_int,C.c_float,C.c_int]
d.ft8_get_last_osd_diag.restype=C.c_int
d.ft8_get_last_osd_diag.argtypes=[C.c_int,C.POINTER(C.c_int),C.POINTER(C.c_float),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.c_int]
CAP='D:/Projects/claude/_qa-scratch/gap-residual/cap/off'
stamps=[l.split('\t')[0] for l in open(CAP+'/capture_index.tsv')][:10]
tot={'A':[0]*5,'B':[0]*5}; diff=0
for st in stamps:
    pcm=np.ascontiguousarray(np.fromfile(f'{CAP}/buffers/{st}_R2.f32',dtype=np.float32))
    row={}
    for name,k,o in (('A',10,0.10),('B',5,0.05)):
        d.ft8_set_decode_params(k,C.c_float(o),24)
        n,_=nat.decode_all(pcm); cc=(C.c_int*2)(); d.ft8_get_last_candidate_counts(cc,2)
        nh,cn,dp,bt=(C.c_int*256)(),(C.c_float*256)(),(C.c_int*256)(),(C.c_int*256)()
        total,rn,rc=C.c_int(0),(C.c_int*2)(),(C.c_int*2)()
        d.ft8_get_last_osd_diag(256,nh,cn,dp,bt,C.byref(total),rn,rc,2)
        row[name]=(cc[0],cc[1],n,total.value,rc[0]+rc[1])
        for i in range(5): tot[name][i]+=row[name][i]
    diff+= row['A']!=row['B']
    print(st[-6:],row)
print('totals (p0 cands, p1 cands, decodes, osd accepted, osd rejected by corr gate)',tot,'cycles where anything differs',diff,'of 10')
