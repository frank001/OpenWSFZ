#!/bin/bash
# XC-BUILD REMEDY chain (spec arch/cross-cycle-prior sections 13 and 14, Amendments 6 and 7; QA (k) review 0231; dev task 2026-11-14-xc-template-remedy).
# DRAFT: needs the Developer's build in $ROOT/bin_remedy, Replay81 with --xc-veto / --xc-tp and the new readback tokens, and a dry run.  Not started.
# usage: nohup bash xc_pc_chain_remedy.sh full > remedy.out 2>&1 & disown     PC EXCLUSIVE (station daemon stopped, WSJT-X idle).  NEVER hibernates (QA decides, once, at the very end).
#   STOP: create $ROOT/chain.stop (read before every arm).  Nothing is pushed; the only commit is te_v2.json, on the QA branch, before any OFF/ON arm (A6.3).
#   1 preflight   pins, selections (TRAIN 500, TEST 1000, 40 m night 1000), binaries, the reference OFF files, tools self-tests, no competing process
#   2 TR2         remedy build, stage ON, shadow ON, T_E = +inf, R14 veto OFF (replay setting), T_P = 0, TRAIN 500;  xc_tp.py: V-TE (T_E 3.076041980658299 to 1e-6 and 23,219 shadow tests), K1 join, K3 offset, V-TR-P, T_P = p10;  te_v2.json COMMITTED
#   3 T/OFF       both flags OFF, TEST 1000;  V-OFF against f82b6432's TEST OFF output (A3.3 identity: matchedbatch, testb, per-cycle counts, then the nc.tsv multiset); STOP on failure
#   4 T/ON        stage ON, shadow ON, T_E and T_P frozen (v2), R14 veto ON, TEST 1000;  analyses: xc_analyse (V-STORE, V-WIRE, NET, SHADOW, LATE, ABANDON), xc_sup (XC-SUP)
#   5 N/OFF, 6 N/ON   the same on the 40 m night 20261028_2233 (selection sha 1eaadbc0, registered before data);  per night, never pooled
#   7 finish      orphan and pin check.  No hibernate.
# GOAL (HK-020): decide the remedy build's rows on the PC on two nights.  CRITICAL CONFIG: ONE build, ONE libft8.dll (the pin), T_E and T_P frozen from TR2 (v2) before ON, R14 veto True in every OFF/ON arm (False only in TR2), 8 threads read back.
MODE=${1:?full}
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/xc-chain
BIN_NEW=$ROOT/bin_remedy
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
R=$ROOT/remedy
if [ -e "$R" ]; then mv "$R" "$R.$(date -u +%Y%m%dT%H%M%SZ).old"; fi
mkdir -p "$R"
LOG=$R/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }
HALTED=0

hibernate_step() { log "no hibernate: QA decides, once, at the very end"; }

finish() {
  busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
  if [ -f "$BIN_NEW/libft8.dll" ]; then [ "$(sha $BIN_NEW/libft8.dll)" = "$PIN" ] && log "END new-build libft8.dll pin OK" || log "END new-build libft8.dll pin FAIL"; fi
  log "chain $MODE finished; halted=$HALTED"
  hibernate_step
}
die() { log "CHAIN HALT: $*"; HALTED=1; finish; exit 9; }
stop_requested() { [ -e "$ROOT/chain.stop" ] && { log "chain.stop present: stopping before the next arm"; HALTED=1; finish; exit 8; }; }

# arm <name> <bin> <selection> <rows> <run> <wavdir> <wsjtx-alltxt> <xc: none|"P S TE VETO TP"> <nhard-token> [extra args]   (the REMEDY chain: R14 veto 0|1 and T_P go through --xc-veto and --xc-tp)
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
    XCARGS="--xc-prior $1 --xc-shadow $2 --xc-te $3 --xc-veto ${4:-1} --xc-tp ${5:-0}"
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


TRAIN=$WAVROOT/20261110_1817_cq-ap-live;      TRAIN_RUN=20261110_1817
TEST=$WAVROOT/20260808_live_run_0016-8080;    TEST_RUN=20260808_0016
NIGHT2=$WAVROOT/20261028_2233_endurance_run-gathered;  NIGHT2_RUN=20261028_2233
SEL_N2=$SC/xc-build/sel_test3_1000.json;      SEL_N2_SHA=1eaadbc0ae702bc99cfd93c072d1c46b1c25b4a3b7457639ed42cfeffc91621d
SEL_TEST=$SC/xc-build/sel_test_1000.json;     SEL_TEST_SHA=d12be5054244247b73a92e0d32cd0acbd26a90b6b934ea0e6d831b5f832b7e73
REF_OFF=$ROOT/ref_f82b6432_OFF
RES=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/xc-build/results
QAWT=/d/Projects/claude/OpenWSFZ/worktrees/qa
QABR=qa/same-chain
TOKS_BASE="clock=system"
log "xc_pc_chain_remedy $MODE start (as $(whoami)); goal: decide the remedy build's rows on two nights on the PC; config: bin_remedy + libft8.dll pin $PIN, T_E and T_P frozen from TR2 v2, 8 threads"
[ -e "$ROOT/chain.stop" ] && { rm -f "$ROOT/chain.stop"; log "removed a stale chain.stop"; }

# ---- 1 preflight
[ -f "$BIN_NEW/Ft8.FitProbe.exe" ] || die "no $BIN_NEW (copy the remedy harness build there)"
[ "$(sha $BIN_NEW/libft8.dll)" = "$PIN" ] || die "the remedy build's libft8.dll is not the pin"
busy && die "a competing process is running at start"
[ "$(sha $SEL500)" = "$SEL500_SHA" ]     || die "sel_500.json differs from the frozen selection"
[ "$(sha $SEL_TEST)" = "$SEL_TEST_SHA" ] || die "sel_test_1000.json differs from its recorded hash"
[ "$(sha $SEL_N2)" = "$SEL_N2_SHA" ]     || die "the 40 m selection differs from its registered hash"
for f in nc.tsv matchedbatch.csv testb.csv run.csv; do [ -s "$REF_OFF/$f" ] || die "reference OFF file missing: $f (V-OFF needs f82b6432's TEST OFF output)"; done
[ "$(sha $REF_OFF/nc.tsv | cut -c1-16)" = "353db31c54204a3a" ] || die "the reference OFF nc.tsv differs from its recorded hash"
python -I "$TOOLS/xc_tp.py" selftest > "$R/xc_tp_selftest.txt" 2>&1 && log "xc_tp self-test ALL PASS" || die "xc_tp self-test FAILED"
python -I "$TOOLS/xc_chain_selftest.py" > "$R/tools_selftest.txt" 2>&1 && log "tools self-test ALL PASS" || die "tools self-test FAILED"
free=$(df -m /d | tail -1 | awk '{print $4}'); [ "$free" -gt 20000 ] || die "less than 20 GB free on D:"
python -I -c "
import json
for sel, run, out in ((r'$(w $SEL_TEST)', '$TEST_RUN', r'$(w $R/stamps_test.txt)'), (r'$(w $SEL_N2)', '$NIGHT2_RUN', r'$(w $R/stamps_n2.txt)')):
    r = json.load(open(sel))['runs'][run]
    open(out, 'w').write(' '.join(r['FULL']))
" || die "could not write the stamp lists"
log "preflight ok"

# ---- 2 TR2 (R14 veto OFF, T_P 0), then T_E and T_P
arm TR2 $BIN_NEW $SEL500 500 $TRAIN_RUN $TRAIN/owsfz/wav $TRAIN/wsjt-x/ALL.TXT "1 1 inf 0 0" "xcprior=True xcshadow=True xcte=Infinity xcveto=False xctp=0 $TOKS_BASE"
python -I "$TOOLS/xc_tp.py" run "$(w $R/TR2)" "$(w $TRAIN/wsjt-x/ALL.TXT)" "$(w $R/te_v2.json)" "$(w $ROOT/full/te.json)" >> "$LOG" 2>&1 || die "TR2 is not valid (V-TE, the K1 join, the K3 offset or V-TR-P; see te_v2.json): STOP"
TE=$(python -I -c "import json;print(repr(json.load(open(r'$(w $R/te_v2.json)'))['T_E']))")
TP=$(python -I -c "import json;print(repr(json.load(open(r'$(w $R/te_v2.json)'))['T_P']))")
{ [ -n "$TE" ] && [ -n "$TP" ] && [ "$TP" != None ]; } || die "T_E or T_P is empty"
log "T_E $TE, T_P $TP frozen (te_v2.json sha256 $(sha $R/te_v2.json | cut -c1-16))"
cp "$R/te_v2.json" "$RES/xc_te_v2.json"
if [ "$(git -C $QAWT branch --show-current)" = "$QABR" ]; then
  git -C $QAWT add qa/xc-build/results/xc_te_v2.json && git -C $QAWT commit -q -m "QA(xc-build): te_v2.json frozen from TR2 (T_E $TE, T_P $TP), committed before any OFF or ON arm (spec A6.3)" && log "te_v2.json committed" || die "the te_v2.json commit failed (it must be committed before OFF/ON)"
else
  die "not on $QABR: te_v2.json cannot be committed here"
fi

# ---- 3 to 6: one night = OFF (and V-OFF against a reference when there is one), ON, analyses.  Arm dirs: $R/<label>/OFF and $R/<label>/ON, so xc_analyse reads <root>/ON and <root>/OFF.
night() {   # night <label> <wavdir> <run> <sel> <alltxt> <stamps file> <ref dir or none>
  local L=$1 W=$2 RUNID=$3 SEL=$4 ALL=$5 ST=$6 REF=$7
  arm $L/OFF $BIN_NEW $SEL 1000 $RUNID $W/owsfz/wav $ALL "0 0 inf 1 0" "xcprior=False xcshadow=False xcte=Infinity xcveto=True xctp=0 $TOKS_BASE"
  if [ "$REF" != none ]; then
    python -I "$TOOLS/xc_chain_tools.py" voff "$(w $R/$L/OFF)" "$(w $REF)" "$(w $R/$L/voff.json)" >> "$LOG" 2>&1 || die "V-OFF FAILS on $L against f82b6432's OFF (matchedbatch, testb or per-cycle counts): STOP"
    python -I "$TOOLS/xc_chain_tools.py" nccmp "$(w $R/$L/OFF/nc.tsv)" "$(w $REF/nc.tsv)" "$(w $ST)" "$(w $R/$L/voff_text.json)" >> "$LOG" 2>&1 || die "V-OFF text leg FAILS on $L: STOP"
    log "V-OFF $L against f82b6432's OFF: PASS (counts and text)"
  fi
  arm $L/ON $BIN_NEW $SEL 1000 $RUNID $W/owsfz/wav $ALL "1 1 $TE 1 $TP" "xcprior=True xcshadow=True xcte=$TE xcveto=True xctp=$TP $TOKS_BASE"
  python -I "$TOOLS/xc_analyse.py" "$(w $R/$L)" "$(w $R/$L/analysis.json)" "$(w $ALL)" "$(w $R/te_v2.json)" > "$R/$L/analysis.out" 2>&1 || log "analysis $L returned nonzero (see $R/$L/analysis.out)"
  python -I "$TOOLS/xc_sup.py" "$(w $R/$L/ON)" "$(w $ALL)" "$(w $R/$L/sup.json)" > "$R/$L/sup.out" 2>&1 || log "xc_sup $L returned nonzero (the offset assertion or the inputs; see $R/$L/sup.out)"
  log "night $L analysed ($R/$L/analysis.json, sup.json)"
}
night T $TEST   $TEST_RUN   $SEL_TEST $TEST/wsjt-x/ALL.TXT   $R/stamps_test.txt $REF_OFF
night N $NIGHT2 $NIGHT2_RUN $SEL_N2   $NIGHT2/wsjt-x/ALL.TXT $R/stamps_n2.txt   none

log "all arms done and valid; the per-night analyses are in $R/T and $R/N; the readings are QA's, afterwards"
finish
