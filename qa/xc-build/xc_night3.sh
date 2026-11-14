#!/bin/bash
# XC-BUILD SECOND-NIGHT (40 m) replication (QA lead, 2026-11-14, Architect-directed: 40 m night, XC-SUP included; frozen build, frozen T_E from the first chain; NOT a spec arm). PREDICATE, registered before data: the replication HOLDS iff CI_lo(NET) >= 0.4 pp and SHADOW CI_hi <= 0.042 and LATE 0 after the budget; XC-SUP read by the Architect rule (SUP-CLEAN iff n(SUP-W) <= 4); every row cited per night, never pooled. Derived from xc_pc_chain.sh. (spec arch/cross-cycle-prior, Amendments 1 to 4; build f82b6432; QA record 2026-11-13-xc-build-pc-chain-state).
#
# usage:  bash xc_pc_chain.sh dry|full      PC EXCLUSIVE, station daemon stopped, WSJT-X idle.  Run detached:  nohup bash xc_pc_chain.sh full > chain.out 2>&1 & disown
#   dry   plumbing only, on the OLD night 20260930_1930 (3 cycles, the late-sub dry selection), outputs under xc-chain/dry, NEVER hibernates, reads nothing of the live window.
#   full  the real chain, in this order (every step logged, every arm validated; any failure halts the chain, saves what exists, and goes to the finish):
#           1 preflight   pins, selections, binaries, N24 files, no competing process, free disk
#           2 V-OFF       new build, both flags OFF, the 500 TRAIN cycles; compared with the stored N24 (matchedbatch, testb, per-cycle b1..b5 counts); capacity rule A4 (late round abandoned <= 1 %)
#           3 PRE100      pre-change build (bin_v2), the first 100 TRAIN cycles; text rows compared with V-OFF's first 100 (A1.2)
#           4 TR          new build, stage ON with T_E = +inf, shadow ON, the 500 TRAIN cycles; T_E frozen (K, FA*, V-TR-N) BEFORE OFF and ON
#           5 OFF         new build, both flags OFF, the first 1,000 cycles of the TEST night (20260808_0016)
#           6 ON          new build, stage ON, shadow ON, T_E frozen from TR, the same 1,000 cycles
#           7 finish      orphan and pin check, then HIBERNATE (below)
# HIBERNATE (the Captain, 2026-11-13: "hibernate it is"): after the finish the PC hibernates ONCE with shutdown.exe /h, whatever happened (a halt is logged first).
#   CANCEL: create the file  $ROOT/hibernate.cancel  (any content) at any time up to the last second: it is read at the start of the 120 s grace, every 5 s during it, and immediately before shutdown.exe.
#   STOP:   create $ROOT/chain.stop to stop the chain before the next arm (the finish and the hibernate then run unless cancelled).  No process is ever killed to cancel anything (Q67).
# GOAL (HK-020): decide the XC-BUILD rows (V-OFF, V-WIRE, V-TR-N, V-STORE, NET, SHADOW, LATE) on the PC, the station's platform.  CRITICAL CONFIG: ONE build (f82b6432 harness copy in $ROOT/bin_new), ONE libft8.dll
#   (the pin), the station stack flags below (identical in every arm), T_E from TR frozen before ON, 8 threads read back.
# Message text (nc.tsv) lives ONLY under _qa-scratch (HK-037); delete the arms' nc.tsv at job close.  Nothing is pushed or committed by this script.
MODE=${1:?dry|full}
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/xc-chain
BIN_NEW=$ROOT/bin_new
BIN_PRE=$SC/coh-res-cand-v2/bin_v2
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
TOOLS=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/xc-build
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
N24=$SC/nhard-ceil/arms/N24
SEL500=$SC/cq-ap/sel_500.json;                SEL500_SHA=c618a66e24bb0d129aa6f5df0ecdad978a53f4b0e9e991d308557378fef5de7f
SEL100=$SC/xc-build/sel_train_100.json;       SEL100_SHA=3d95b2d944cbd84784d6850072e7d1ec34a3cfbe91ddae85853bbfd93c9ec1e1
SEL_TEST=$SC/xc-build/sel_test3_1000.json;     SEL_TEST_SHA=1eaadbc0ae702bc99cfd93c072d1c46b1c25b4a3b7457639ed42cfeffc91621d
TE_JSON=$ROOT/full/te.json;                   TE_SHA=6e0fbc52b2e989dc
TRAIN=$WAVROOT/20261110_1817_cq-ap-live;      TRAIN_RUN=20261110_1817
TEST=$WAVROOT/20261028_2233_endurance_run-gathered;  TEST_RUN=20261028_2233
GRACE=${GRACE:-120}
K_SOURCE=${K_SOURCE:-tested}
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
R=$ROOT/night3
if [ -e "$R" ]; then mv "$R" "$R.$(date -u +%Y%m%dT%H%M%SZ).old"; fi
mkdir -p "$R"
LOG=$R/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }
HALTED=0

hibernate_step() {
  [ "$MODE" = full ] || { log "dry: no hibernate"; return; }
  [ "${NOHIB:-0}" = 1 ] && { log "NOHIB=1: no hibernate"; return; }
  log "hibernating in $GRACE s unless $ROOT/hibernate.cancel exists (create it to cancel)"
  local i=0
  while [ $i -lt $GRACE ]; do
    [ -e "$ROOT/hibernate.cancel" ] && { log "HIBERNATE CANCELLED by the cancel file; the PC stays on"; return; }
    sleep 5; i=$((i + 5))
  done
  [ -e "$ROOT/hibernate.cancel" ] && { log "HIBERNATE CANCELLED by the cancel file (last check); the PC stays on"; return; }
  log "hibernate now"
  powershell -NoProfile -Command "shutdown.exe /h"
  log "shutdown.exe returned rc=$? (back up, or refused)"
}

finish() {
  busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
  if [ -f "$BIN_NEW/libft8.dll" ]; then [ "$(sha $BIN_NEW/libft8.dll)" = "$PIN" ] && log "END new-build libft8.dll pin OK" || log "END new-build libft8.dll pin FAIL"; fi
  log "chain $MODE finished; halted=$HALTED"
  hibernate_step
}
die() { log "CHAIN HALT: $*"; HALTED=1; finish; exit 9; }
stop_requested() { [ -e "$ROOT/chain.stop" ] && { log "chain.stop present: stopping before the next arm"; HALTED=1; finish; exit 8; }; }

# arm <name> <bin> <selection> <rows> <run> <wavdir> <wsjtx-alltxt> <xc: none|"P S TE"> <nhard-token> [extra args]
arm() {
  local NAME=$1 BIN=$2 SEL=$3 WANT=$4 RUNID=$5 WDIR=$6 WALL=$7 XC=$8 TOK=$9 O=$R/$1 ST=$R/$1/status.txt
  stop_requested
  busy && die "a competing process is running before $NAME"
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin before $NAME"
  mkdir -p "$O"
  tasklist 2>/dev/null | grep -qi 'wsjtx' && echo "wsjtx.exe present (open); idle is the Captain's word" >> "$ST" || echo "wsjtx.exe not running" >> "$ST"
  echo "start $(date -u +%FT%TZ) name=$NAME xc='$XC' dll=$(sha $BIN/libft8.dll) free_d=$(df -h /d | tail -1 | awk '{print $4}')" >> "$ST"
  log "arm $NAME start (xc: $XC)"
  local XCARGS=""
  if [ "$XC" != none ]; then
    set -- $XC
    XCARGS="--xc-prior $1 --xc-shadow $2 --xc-te $3"
    [ "$1" = 1 ] && XCARGS="$XCARGS --xc-out $(w $O/xc.csv) --xc-probe-out $(w $O/probe.csv)"
  fi
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUNID --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $WDIR)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 $XCARGS --cohfb-out "$(w $O/coh.csv)" \
    --label "xc-chain:$NAME" --wsjtx-alltxt "$(w $WALL)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  for tag in start end; do   # the arm's readback at the start and at the end of the process
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    local need
    for need in "decodingDepth=Deep" "nhard=24 " "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=True" "cohrescand=True" $TOK; do
      echo "$line" | grep -q -- "$need" || { ok=0; echo "READBACK $tag missing: $need" >> "$ST"; }
    done
  done
  echo "exit $rc end=$(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME process ended rc=$rc readback_ok=$ok"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc readback_ok=$ok)"
  local extra=""; [ "$XC" != none ] && [ "${XC%% *}" = 1 ] && extra="--xc"
  python -I "$TOOLS/xc_chain_tools.py" check "$(w $O)" "$(w $O/nc.tsv)" $WANT $extra $CHECK_LATE >> "$LOG" 2>&1 || die "arm $NAME is INVALID (see CHECK line above)"
  log "arm $NAME valid ($WANT rows)"
}

log "xc_pc_chain $MODE start (as $(whoami)); goal: decide the XC-BUILD rows on the PC; config: bin_new + libft8.dll pin $PIN, station stack, 8 threads, T_E frozen from TR before ON"
log "grace=$GRACE s; cancel file $ROOT/hibernate.cancel; stop file $ROOT/chain.stop; K source for FA*: $K_SOURCE (frozen analysis library: 'tested'; spec wording 'live-prior count')"
[ -e "$ROOT/hibernate.cancel" ] && { rm -f "$ROOT/hibernate.cancel"; log "removed a stale hibernate.cancel"; }
[ -e "$ROOT/chain.stop" ] && { rm -f "$ROOT/chain.stop"; log "removed a stale chain.stop"; }

# ---- 1 preflight
[ -f "$BIN_NEW/Ft8.FitProbe.exe" ] || die "no $BIN_NEW (copy the f82b6432 harness build there)"
[ "$(sha $BIN_NEW/libft8.dll)" = "$PIN" ] || die "new build's libft8.dll is not the pin"
[ "$(sha $BIN_PRE/libft8.dll)" = "$PIN" ] || die "pre-change build's libft8.dll is not the pin"
log "binaries: new Ft8.FitProbe.dll $(sha $BIN_NEW/Ft8.FitProbe.dll | cut -c1-16), OpenWSFZ.Ft8.dll $(sha $BIN_NEW/OpenWSFZ.Ft8.dll | cut -c1-16); pre-change (bin_v2) OpenWSFZ.Ft8.dll $(sha $BIN_PRE/OpenWSFZ.Ft8.dll | cut -c1-16)"
busy && die "a competing process is running at start"
if [ "$MODE" = full ]; then
  [ "$(sha $SEL_TEST)" = "$SEL_TEST_SHA" ] || die "sel_test3_1000.json differs from its recorded hash"
  [ "$(sha $TE_JSON | cut -c1-16)" = "$TE_SHA" ] || die "te.json (the frozen T_E) differs from the first chain's"
  python -I - <<PY || die "selected WAVs missing or the selection is not contiguous"
import json, os, datetime
r = json.load(open(r"$(w $SEL_TEST)"))["runs"]["$TEST_RUN"]
st = [r["warmup"]] + r["FULL"]
assert len(r["FULL"]) == 1000
assert not [s for s in st if not os.path.exists(r"$(w $TEST/owsfz/wav)" + "/" + s + ".wav")]
t = [datetime.datetime.strptime(s, "%y%m%d_%H%M%S") for s in st]
assert all((b - a).total_seconds() == 15 for a, b in zip(t, t[1:])), "not contiguous"
print("preflight: 40 m second night, 1000 FULL cycles contiguous, warmup 15 s before the first")
PY
  free=$(df -m /d | tail -1 | awk '{print $4}'); [ "$free" -gt 20000 ] || die "less than 20 GB free on D:"
fi
log "preflight ok"

TE=$(python -I -c "import json;print(repr(json.load(open(r'$(w $TE_JSON)'))['T_E']))")
[ "$TE" = 3.076041980658299 ] || die "T_E is not the frozen 3.076041980658299 (got $TE)"
log "T_E frozen (from the first chain): $TE"

# ---- 5 OFF, 6 ON on the TEST night
arm OFF $BIN_NEW $SEL_TEST 1000 $TEST_RUN $TEST/owsfz/wav $TEST/wsjt-x/ALL.TXT "0 0 inf" "xcprior=False xcshadow=False xcte=Infinity clock=system"
arm ON  $BIN_NEW $SEL_TEST 1000 $TEST_RUN $TEST/owsfz/wav $TEST/wsjt-x/ALL.TXT "1 1 $TE" "xcprior=True xcshadow=True xcte=$TE clock=system"

log "all arms done and valid; the analysis (V-WIRE, V-STORE, NET, SHADOW, LATE, ABANDON) is QA's, afterwards"
finish
