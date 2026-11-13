#!/bin/bash
# XC-BUILD PC chain (spec arch/cross-cycle-prior, Amendments 1 to 4; build f82b6432; QA record 2026-11-13-xc-build-pc-chain-state).
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
SEL_TEST=$SC/xc-build/sel_test_1000.json;     SEL_TEST_SHA=d12be5054244247b73a92e0d32cd0acbd26a90b6b934ea0e6d831b5f832b7e73
TRAIN=$WAVROOT/20261110_1817_cq-ap-live;      TRAIN_RUN=20261110_1817
TEST=$WAVROOT/20260808_live_run_0016-8080;    TEST_RUN=20260808_0016
GRACE=${GRACE:-120}
K_SOURCE=${K_SOURCE:-tested}
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
if [ "$MODE" = dry ]; then R=$ROOT/dry; else R=$ROOT/full; fi
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
  [ "$(sha $SEL500)" = "$SEL500_SHA" ]     || die "sel_500.json differs from the frozen selection"
  [ "$(sha $SEL100)" = "$SEL100_SHA" ]     || die "sel_train_100.json differs from its recorded hash"
  [ "$(sha $SEL_TEST)" = "$SEL_TEST_SHA" ] || die "sel_test_1000.json differs from its recorded hash"
  for f in matchedbatch.csv testb.csv run.csv; do [ -s "$N24/$f" ] || die "stored N24 file missing: $f"; done
  python -I - <<PY || die "selected WAVs missing or the selections are not contiguous"
import json, os, datetime
def chk(sel, run, wdir, n):
    r = json.load(open(sel))["runs"][run]
    st = [r["warmup"]] + r["FULL"]
    assert len(r["FULL"]) == n, (sel, len(r["FULL"]))
    miss = [s for s in st if not os.path.exists(wdir + "/" + s + ".wav")]
    assert not miss, (sel, len(miss))
    t = [datetime.datetime.strptime(s, "%y%m%d_%H%M%S") for s in st]
    gaps = sum(1 for a, b in zip(t, t[1:]) if (b - a).total_seconds() != 15)
    return gaps
g1 = chk("$SEL500", "$TRAIN_RUN", "$TRAIN/owsfz/wav", 500)
g2 = chk("$SEL_TEST", "$TEST_RUN", "$TEST/owsfz/wav", 1000)
print("preflight: TRAIN 500 gaps of the 15 s grid:", g1, "; TEST 1000 gaps:", g2)
assert g2 == 0, "TEST segment is not contiguous"
PY
  python -I -c "
import json
r=json.load(open(r'$SEL100'))['runs']['$TRAIN_RUN']; open(r'$R/stamps100.txt','w').write(' '.join(r['FULL']))
" || die "could not write the first-100 stamp list"
  python -I "$TOOLS/xc_chain_selftest.py" > "$R/tools_selftest.txt" 2>&1 && log "tools self-test ALL PASS" || die "tools self-test FAILED"
  free=$(df -m /d | tail -1 | awk '{print $4}'); [ "$free" -gt 20000 ] || die "less than 20 GB free on D:"
fi
log "preflight ok"

if [ "$MODE" = dry ]; then
  G=$WAVROOT/20260930_1930_endurance_run-gathered
  DSEL=$SC/late-sub/selection_3n_dry.json; DRUN=20260930_1930
  arm VOFFd $BIN_NEW $DSEL 3 $DRUN $G/owsfz/wav $G/wsjt-x/ALL.TXT "0 0 inf" "xcprior=False xcshadow=False xcte=Infinity clock=system"
  arm PREd  $BIN_PRE $DSEL 3 $DRUN $G/owsfz/wav $G/wsjt-x/ALL.TXT none ""
  python -I "$TOOLS/xc_chain_tools.py" voff "$(w $R/VOFFd)" "$(w $R/PREd)" "$(w $R/voff_dry.json)" --nc-new "$(w $R/VOFFd/nc.tsv)" --nc-ref "$(w $R/PREd/nc.tsv)" >> "$LOG" 2>&1 && log "dry: V-OFF comparison (new OFF vs pre-change) PASS" || die "dry: V-OFF comparison FAILED"
  arm TRd   $BIN_NEW $DSEL 3 $DRUN $G/owsfz/wav $G/wsjt-x/ALL.TXT "1 1 inf" "xcprior=True xcshadow=True xcte=Infinity clock=system"
  python -I "$TOOLS/xc_chain_tools.py" te "$(w $R/TRd)" "$(w $R/te_dry.json)" --dry --k-source $K_SOURCE >> "$LOG" 2>&1 || log "dry: te returned nonzero (expected with 3 cycles when no shadow tests exist)"
  arm ONd   $BIN_NEW $DSEL 3 $DRUN $G/owsfz/wav $G/wsjt-x/ALL.TXT "1 1 99.0" "xcprior=True xcshadow=True xcte=99 clock=system"
  log "dry done: plumbing only; outputs under $R (delete nc.tsv at job close, HK-037)"
  finish; exit 0
fi

# ---- 2 V-OFF
CHECK_LATE="--late-max 0.01"
arm VOFF $BIN_NEW $SEL500 500 $TRAIN_RUN $TRAIN/owsfz/wav $TRAIN/wsjt-x/ALL.TXT "0 0 inf" "xcprior=False xcshadow=False xcte=Infinity clock=system"
CHECK_LATE=""
python -I "$TOOLS/xc_chain_tools.py" voff "$(w $R/VOFF)" "$(w $N24)" "$(w $R/voff_vs_N24.json)" >> "$LOG" 2>&1 || die "V-OFF FAILS against N24 (spec section 4 row 1: STOP; back to the Developer)"
log "V-OFF vs N24: PASS (matchedbatch, testb and per-cycle counts identical, timing excluded)"

# ---- 3 PRE100 (text leg)
arm PRE100 $BIN_PRE $SEL100 100 $TRAIN_RUN $TRAIN/owsfz/wav $TRAIN/wsjt-x/ALL.TXT none ""
python -I "$TOOLS/xc_chain_tools.py" nccmp "$(w $R/VOFF/nc.tsv)" "$(w $R/PRE100/nc.tsv)" "$(w $R/stamps100.txt)" "$(w $R/voff_text100.json)" >> "$LOG" 2>&1 || die "V-OFF text leg FAILS (the new build's first 100 cycles differ from the pre-change build's text)"
log "V-OFF text leg (first 100 cycles, new OFF vs pre-change): PASS"

# ---- 4 TR, then T_E
arm TR $BIN_NEW $SEL500 500 $TRAIN_RUN $TRAIN/owsfz/wav $TRAIN/wsjt-x/ALL.TXT "1 1 inf" "xcprior=True xcshadow=True xcte=Infinity clock=system"
python -I "$TOOLS/xc_chain_tools.py" te "$(w $R/TR)" "$(w $R/te.json)" --k-source $K_SOURCE >> "$LOG" 2>&1 || die "T_E: V-TR-N fails or no shadow tests (spec section 4 row 2: VOID); see the TE line above"
TE=$(python -I -c "import json;print(repr(json.load(open(r'$R/te.json'))['T_E']))")
[ -n "$TE" ] && [ "$TE" != None ] || die "T_E is empty"
log "T_E frozen: $TE (te.json sha256 $(sha $R/te.json | cut -c1-16))"

# ---- 5 OFF, 6 ON on the TEST night
arm OFF $BIN_NEW $SEL_TEST 1000 $TEST_RUN $TEST/owsfz/wav $TEST/wsjt-x/ALL.TXT "0 0 inf" "xcprior=False xcshadow=False xcte=Infinity clock=system"
arm ON  $BIN_NEW $SEL_TEST 1000 $TEST_RUN $TEST/owsfz/wav $TEST/wsjt-x/ALL.TXT "1 1 $TE" "xcprior=True xcshadow=True xcte=$TE clock=system"

log "all arms done and valid; the analysis (V-WIRE, V-STORE, NET, SHADOW, LATE, ABANDON) is QA's, afterwards"
finish
