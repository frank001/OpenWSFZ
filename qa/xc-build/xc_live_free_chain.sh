#!/bin/bash
# XC-LIVE-FREE regeneration chain (Captain's ACK required to START; unattended afterwards).  PC EXCLUSIVE for about 6 h: CTRL about 1.6 h, then OFF about 4.3 h.
# usage: bash xc_live_free_chain.sh preflight                       checks only, no decode, no load
#        nohup bash xc_live_free_chain.sh run > chain.out 2>&1 & disown
# STOP: create $ROOT/chain.stop (read before each arm).  NEVER hibernates by itself (QA does that once, at the very end, after the analysis).  Nothing is pushed or committed by this script.
# GOAL (HK-020): (1) CTRL = the first build f82b6432's ON arm on the TEST night (the spec's V-POS control; its nc.tsv was deleted at the 2026-11-14 job close, Q78) regenerated with
#                    EXACTLY the command of $SC/xc-chain/full/ON/status.txt (bin_new, sel_test_1000.json sha d12be505, --xc-prior 1 --xc-shadow 1 --xc-te 3.076041980658299, no veto, no T_P);
#                (2) OFF = the live night 20261114_2312's archived WAVs through the shipped build with XC OFF (bin_defaults), same selection as the ON replay (sha 8644488047fde86c).
# CRITICAL CONFIG: ONE libft8.dll pin in both binaries (bbde6eb6...), 8 threads, Deep, nhard 24, CQ-AP, multi-set, late round, residual candidates; the read-back at the start AND the end of every arm must show them.
# Message text (nc.tsv, matched.csv) lives ONLY under _qa-scratch (HK-037); the analysis reads it by code; it is KEPT, never deleted (Captain, 2026-11-16).
# Modes: preflight | run (CTRL then OFF) | off (OFF only, after a CTRL that is already valid).
MODE=${1:?preflight|run|off}
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/xc-live-free
BIN_FIRST=$SC/xc-chain/bin_new            # the first build f82b6432's harness (the control)
BIN_SHIP=$SC/xc-chain/bin_defaults        # the shipped build's harness (66b3ddf1 source)
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
TOOLS=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/xc-build
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
TE=3.076041980658299
TEST=$WAVROOT/20260808_live_run_0016-8080;  TEST_RUN=20260808_0016
SEL_TEST=$SC/xc-build/sel_test_1000.json;   SEL_TEST_SHA=d12be5054244247b73a92e0d32cd0acbd26a90b6b934ea0e6d831b5f832b7e73
NIGHT=$WAVROOT/20261114_2312_endurance_run-gathered; NIGHT_RUN=20261114_2312
SEL_NIGHT=$ROOT/sel_full.json;              SEL_NIGHT_SHA=8644488047fde86c
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81|dotnet'; }
mkdir -p "$ROOT"; LOG=$ROOT/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
finish() {
  busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
  for b in "$BIN_FIRST" "$BIN_SHIP"; do [ "$(sha $b/libft8.dll)" = "$PIN" ] && log "END pin OK ($(basename $b))" || log "END pin FAIL ($(basename $b))"; done
  log "chain $MODE finished; halted=$HALTED (no hibernate: QA decides at the very end)"
}
HALTED=0
die() { log "CHAIN HALT: $*"; HALTED=1; finish; exit 9; }

preflight() {
  for b in "$BIN_FIRST" "$BIN_SHIP"; do
    [ -f "$b/Ft8.FitProbe.exe" ] || die "no harness in $b"
    [ "$(sha $b/libft8.dll)" = "$PIN" ] || die "libft8.dll in $b is not the pin"
  done
  [ "$(sha $SEL_TEST)" = "$SEL_TEST_SHA" ] || die "sel_test_1000.json differs from its recorded hash"
  [ "$(sha $SEL_NIGHT | cut -c1-16)" = "$SEL_NIGHT_SHA" ] || die "the night selection differs from its registered hash"
  [ "$(ls $NIGHT/owsfz/wav | wc -l)" = 2834 ] || die "the night's WAV count is not 2834"
  [ -s "$TEST/wsjt-x/ALL.TXT" ] && [ -s "$NIGHT/wsjt-x/ALL.TXT" ] || die "a WSJT-X ALL.TXT is missing"
  grep -q "xc='1 1 $TE'" "$SC/xc-chain/full/ON/status.txt" || die "full/ON/status.txt no longer shows the control's command"
  busy && die "a competing process is running"
  [ "$(df -m /d | tail -1 | awk '{print $4}')" -gt 20000 ] || die "less than 20 GB free on D:"
  python -I "$TOOLS/xc_next_tx.py" selftest | grep -q "ALL PASS" || die "xc_next_tx selftest failed"
  log "preflight ok"
}

# arm <name> <bin> <selection> <run> <wavdir> <wsjtx ALL.TXT> <readback tokens> <xc args...>
arm() {
  local NAME=$1 BIN=$2 SEL=$3 RUNID=$4 WDIR=$5 WALL=$6 TOKS=$7; shift 7; local O=$ROOT/$NAME
  [ -e "$ROOT/chain.stop" ] && die "chain.stop present before $NAME"
  busy && die "a competing process is running before $NAME"
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin before $NAME"
  [ -e "$O" ] && mv "$O" "$O.$(date -u +%Y%m%dT%H%M%SZ).old"; mkdir -p "$O"
  log "arm $NAME start ($*) free_d=$(df -h /d | tail -1 | awk '{print $4}')"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUNID --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $WDIR)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 "$@" --cohfb-out "$(w $O/coh.csv)" \
    --label "xc-live-free:$NAME" --wsjtx-alltxt "$(w $WALL)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1 tag need line
  for tag in start end; do
    line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24 " "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=True" "cohrescand=True" "clock=system" $TOKS; do
      echo "$line" | grep -q -- "$need" || { ok=0; log "READBACK $tag missing: $need"; }
    done
  done
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; log "END dll pin mismatch"; }
  log "arm $NAME ended rc=$rc readback_ok=$ok rows_nc=$(wc -l < $O/nc.tsv 2>/dev/null)"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed"
}

preflight
[ "$MODE" = preflight ] && { log "preflight only: nothing was decoded"; exit 0; }
[ -e "$ROOT/chain.stop" ] && { rm -f "$ROOT/chain.stop"; log "removed the chain.stop left by the skip-OFF decision (Captain's ACK to run)"; }
log "start (as $(whoami)); order CTRL then OFF"

# 1 CTRL: the first build's ON arm on the TEST night, the command of full/ON/status.txt   (mode `run` only; mode `off` skips it, CTRL already done 2026-11-16)
if [ "$MODE" = run ]; then
arm CTRL "$BIN_FIRST" "$SEL_TEST" $TEST_RUN "$TEST/owsfz/wav" "$TEST/wsjt-x/ALL.TXT" "xcprior=True xcshadow=True xcte=$TE" \
  --xc-prior 1 --xc-shadow 1 --xc-te $TE --xc-out "$(w $ROOT/CTRL/xc.csv)" --xc-probe-out "$(w $ROOT/CTRL/probe.csv)"
# counts only from here (text stays inside the tools)
python -I "$TOOLS/xc_sup.py" "$(w $ROOT/CTRL)" "$(w $TEST/wsjt-x/ALL.TXT)" "$(w $ROOT/ctrl_sup.json)" > "$ROOT/ctrl_sup.out" 2>&1 && log "ctrl_sup.json written (the first chain had SUP-W 641, FREE 1018, COR 904, SUP-O 16, b6 2579: read the difference, do not assert it)" || log "xc_sup on CTRL returned nonzero (see ctrl_sup.out)"
python -I "$TOOLS/xc_next_tx.py" run "$(w $ROOT/ON)" "$(w $NIGHT/wsjt-x/ALL.TXT)" "$(w $ROOT/next_tx_with_ctrl.json)" "$(w $ROOT/CTRL)" "$(w $TEST/wsjt-x/ALL.TXT)" > "$ROOT/next_tx_with_ctrl.out" 2>&1 && log "next_tx_with_ctrl.json written" || log "xc_next_tx run returned nonzero (see next_tx_with_ctrl.out)"
fi

# 2 OFF: the live night, XC OFF, the shipped build
# (--xc-defaults 1 is REQUIRED here: this harness demands --xc-te unless the defaults flag is given; the first attempt without it died in 4 s, Q79)
arm OFF "$BIN_SHIP" "$SEL_NIGHT" $NIGHT_RUN "$NIGHT/owsfz/wav" "$NIGHT/wsjt-x/ALL.TXT" "xcprior=False xcshadow=False" --xc-prior 0 --xc-shadow 0 --xc-defaults 1

log "all arms done"
finish
