#!/bin/sh
# usage: trap-reopen.sh <armname> <capture-tid> <wsjtx-pid>   (QA 2026-10-15)
# polls the capture thread read-syscall counter every ~10 ms; a burst of >= 10 reads between two polls (healthy: <= 2 per 20 ms; the reopen: 60 in 20 ms)
# freezes the whole WSJT-X (SIGSTOP), takes eu-stack of every thread, then continues it.
N=$1; T=$2; W=$3; O=$HOME/rr-run/$N/trap; mkdir -p $O
getr() { while read -r k v; do [ "$k" = "syscr:" ] && { R=$v; return; }; done < /proc/$T/io; }
getr; prev=$R
while [ -d /proc/$T ]; do
  getr
  if [ $((R - prev)) -ge 10 ]; then
    kill -STOP $W; date -u +%T.%N > $O/when.txt; echo "delta=$((R - prev)) syscr=$R" >> $O/when.txt
    cat /proc/$T/syscall >> $O/when.txt 2>&1
    eu-stack -p $W > $O/eu-stack-frozen.txt 2>&1
    cat /proc/$T/io > $O/io.txt; ls -l /proc/$W/fd > $O/fd.txt 2>&1
    kill -CONT $W; echo "$(date -u +%FT%TZ) TRAPPED: WSJT-X frozen and stacked (see $O)" >> $HOME/rr-run/$N.log
    exit 0
  fi
  prev=$R; sleep 0.01
done
