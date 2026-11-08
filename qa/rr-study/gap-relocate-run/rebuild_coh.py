import re,csv,sys
R=r"D:\Projects\claude\_qa-scratch\coh-gate-r-f4\raw\on"
rx=re.compile(r"Coherent fallback: eligible=(\d+), attempted=(\d+), crcOk=(\d+), f1bComputed=(\d+), gated=(\d+), published=(\d+), abandoned=(\d+), elapsedMs=(\d+), publishedEdge=(\d+), path=(\d+), workers=(\d+), fbStartMs=(-?\d+), fbWallMs=(-?\d+), batch=(\d+), batch4Published=([01]), batch4PublishMs=(-?\d+), sets=(on|off), walkEntered=(\d+), crcC1=(\d+), crcJ2=(\d+), crcJ3=(\d+), crcN1=(\d+)")
old=list(csv.reader(open(R+r"\coh.csv")))
hdr=old[0]; stamps=[r[0] for r in old[1:]]
lines=[rx.search(l) for l in open(R+r"\log.log",encoding="utf-8",errors="replace") if "Coherent fallback:" in l]
assert all(lines) and len(lines)==len(stamps)==1200,(len(lines),len(stamps))
import shutil; shutil.copy(R+r"\coh.csv",R+r"\coh.csv.harness_partial")
w=csv.writer(open(R+r"\coh.csv","w",newline=""))
w.writerow(hdr)
for st,m in zip(stamps,lines):
    g=m.groups(); w.writerow([st,1,g[0],g[1],g[2],g[3],g[4],g[5],g[6],g[7],g[8],g[10],g[11],g[12],g[13],g[14],g[15],g[16],g[17],g[18],g[19],g[20],g[21]])
print("rebuilt",len(stamps))
