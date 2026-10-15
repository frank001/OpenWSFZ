#!/bin/sh
# usage: stall-capture.sh <armname>   (QA 2026-10-15) what is WSJT-X waiting on, right now, while it is frozen. Read-only apart from ptrace attach (eu-stack, strace).
N=$1; O=$HOME/rr-run/$N/stallcap-$(date -u +%H%M%S); mkdir -p $O; cd $O
date -u > when.txt
W=$(pgrep -x wsjtx | head -1); D=$(pgrep -x OpenWSFZ.Daemon | head -1); echo "wsjtx=$W daemon=$D arecord=$(pgrep -x arecord | head -1)" >> when.txt
# 1 passive state first (nothing attached yet)
for P in $W $D $(pgrep -x arecord); do [ -n "$P" ] || continue; mkdir -p p$P
  for t in $(ls /proc/$P/task); do echo "$t $(cat /proc/$P/task/$t/comm) wchan=$(cat /proc/$P/task/$t/wchan 2>/dev/null) syscall=$(cut -d" " -f1-4 /proc/$P/task/$t/syscall 2>/dev/null) state=$(awk "{print \$3}" /proc/$P/task/$t/stat) cpu=$(awk "{print \$14+\$15}" /proc/$P/task/$t/stat)"; done > p$P/threads.txt
  ls -l /proc/$P/fd > p$P/fd.txt 2>&1
  for f in $(ls /proc/$P/fd 2>/dev/null); do l=$(readlink /proc/$P/fd/$f 2>/dev/null); case "$l" in /dev/snd/*|*alsa*|/dev/shm/*) echo "== fd $f $l"; cat /proc/$P/fdinfo/$f;; esac; done > p$P/snd-fdinfo.txt 2>&1
done
ipcs -a > ipcs.txt 2>&1; for s in $(ipcs -s | awk "NR>3 && \$2~/^[0-9]+$/ {print \$2}"); do echo "== sem $s"; ipcs -s -i $s; done > ipcs-sem.txt 2>&1
ls -l /dev/shm /tmp 2>&1 | head -60 > shm-tmp.txt; ss -xap 2>/dev/null | grep -i "alsa\|dsnoop\|wsjt\|OpenWSFZ" > ss-unix.txt
for f in status hw_params sw_params; do echo "== $f"; cat /proc/asound/card0/pcm0c/sub0/$f; done > alsa-capture.txt 2>&1; cat /proc/asound/card0/pcm0p/sub0/status >> alsa-capture.txt 2>&1
uptime > load.txt; ps -eo pid,etime,pcpu,state,wchan:20,comm --sort=-pcpu | head -15 >> load.txt
# 2 user-space stacks of every thread
[ -n "$W" ] && eu-stack -p $W > p$W/eu-stack.txt 2>&1
[ -n "$D" ] && eu-stack -p $D > p$D/eu-stack.txt 2>&1
for A in $(pgrep -x arecord); do eu-stack -p $A > p$A/eu-stack.txt 2>&1; tr "\0" " " < /proc/$A/cmdline > p$A/cmdline.txt; done
# 3 a live syscall trace of the frozen WSJT-X (only if strace is installed): 20 s, all its threads, timestamps and durations
if [ -n "$W" ] && command -v strace >/dev/null 2>&1; then
  A=""; for t in $(ls /proc/$W/task); do A="$A -p $t"; done
  timeout 20 strace -tt -T -s 64 $A -o p$W/strace-20s.txt 2> p$W/strace.err
fi
date -u >> when.txt; echo captured to $O
